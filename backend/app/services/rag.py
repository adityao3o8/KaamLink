"""Hybrid Q&A: KaamLink RAG when relevant, otherwise general Groq chat."""
from __future__ import annotations

import logging
import re
from pathlib import Path

from app.config import BASE_DIR, settings
from app.database import SessionLocal
from app.models import KbChunk
from app.services import groq_client
from app.services.embeddings import cosine_similarity, dumps_embedding, embed_query, embed_text

logger = logging.getLogger("kaamlink.rag")

DOCS_DIR = BASE_DIR.parent / "docs_kb"
if not DOCS_DIR.exists():
    DOCS_DIR = Path(__file__).resolve().parents[3] / "docs_kb"

DOMAIN_TERMS = {
    "kaamlink", "worker", "contractor", "job", "wage", "salary", "pay", "unpaid",
    "mason", "mestri", "painter", "plumber", "electrician", "helper", "carpenter",
    "mazdoor", "safety", "helmet", "hire", "alert", "whatsapp", "match", "shortlist",
    "chennai", "chengalpattu", "tamil", "hindi", "profile", "reliability", "rating",
    "browse", "available", "kaam", "velai", "din", "naal", "chahiye", "venum",
    "labour", "labor", "site", "construction", "rights", "overtime", "travel",
}

# Only hard-block clearly harmful asks; other "random" questions go to general chat
HARD_BLOCK = [
    r"\b(child\s*porn|csam|underage\s*sex)\b",
    r"\b(how to make (a )?bomb|build a bomb|make explosives)\b",
    r"\b(credit card (fraud|dump)|steal (otp|password))\b",
]


def _chunk_text(text: str, size: int = 450) -> list[str]:
    parts, buf, count = [], [], 0
    for para in text.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if count + len(para) > size and buf:
            parts.append("\n\n".join(buf))
            buf, count = [para], len(para)
        else:
            buf.append(para)
            count += len(para)
    if buf:
        parts.append("\n\n".join(buf))
    return parts or [text[:size]]


def ingest_kb(force: bool = False) -> int:
    db = SessionLocal()
    try:
        existing = db.query(KbChunk).count()
        if existing and not force:
            return existing
        if force:
            db.query(KbChunk).delete()
            db.commit()
        if not DOCS_DIR.exists():
            logger.warning("docs_kb missing at %s", DOCS_DIR)
            return 0
        n = 0
        for path in sorted(DOCS_DIR.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            for chunk in _chunk_text(text):
                emb = embed_text(chunk)
                db.add(KbChunk(source=path.name, text=chunk, embedding=dumps_embedding(emb)))
                n += 1
        db.commit()
        logger.info("Ingested %s KB chunks from %s", n, DOCS_DIR)
        return n
    finally:
        db.close()


def _is_hard_blocked(question: str) -> bool:
    q = (question or "").lower()
    return any(re.search(pat, q, re.I) for pat in HARD_BLOCK)


def _looks_domain(question: str) -> bool:
    q = (question or "").lower()
    return any(term in q for term in DOMAIN_TERMS)


def _keyword_boost(question: str, chunk_text: str) -> float:
    qwords = set(re.findall(r"[a-zA-Z\u0900-\u097F\u0B80-\u0BFF]+", (question or "").lower()))
    c = (chunk_text or "").lower()
    boost = 0.0
    for term in DOMAIN_TERMS:
        if term in qwords and term in c:
            boost += 0.03
    overlap = sum(1 for w in qwords if len(w) > 3 and w in c)
    boost += min(0.12, overlap * 0.02)
    return min(0.25, boost)


def retrieve(question: str, top_k: int = 4, min_score: float = 0.32) -> list[tuple[float, KbChunk]]:
    db = SessionLocal()
    try:
        if db.query(KbChunk).count() == 0:
            ingest_kb(force=True)
        qvec = embed_query(question)
        scored = []
        for c in db.query(KbChunk).all():
            score = cosine_similarity(qvec, c.embedding_vector()) + _keyword_boost(question, c.text)
            scored.append((score, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        out = []
        for score, c in scored[:top_k]:
            if score < min_score:
                continue
            out.append((score, KbChunk(id=c.id, source=c.source, text=c.text, embedding=c.embedding)))
        return out
    finally:
        db.close()


def _clean_extract(text: str) -> str:
    lines = []
    for ln in (text or "").split("\n"):
        s = ln.strip()
        if not s or s.startswith("#") or s.startswith(">"):
            continue
        lines.append(s.lstrip("#*- ").strip())
    return " ".join(lines)


def _hard_block_msg(language: str) -> str:
    msgs = {
        "Hindi": "Is request mein main madad nahi kar sakta. Kuch aur poochho — general sawal ya KaamLink ke baare mein.",
        "Tamil": "Indha request-ku naan help panna mudiyathu. Vera kelvi kelunga — general topic or KaamLink.",
        "English": "I can't help with that request. Ask me anything else — general questions or KaamLink / construction work.",
    }
    return msgs.get(language, msgs["English"])


def _general_answer(question: str, language: str, demo_mode: bool = False) -> dict:
    """Answer random / non-KaamLink questions with the Groq LLM."""
    if demo_mode or settings.demo_mode or not settings.groq_api_key:
        return {
            "answer": (
                f"(Demo general mode) You asked: “{question}”. "
                "Turn off Demo mode and ensure GROQ_API_KEY is set for a full AI answer. "
                "For KaamLink help, try: How do I hire workers? / What if wages are unpaid?"
            ),
            "sources": [],
            "language": language,
            "mode": "general_demo",
        }

    system = f"""You are KaamLink Assistant — a friendly helper for a construction labour app in India,
but you ALSO answer general everyday questions (fun facts, explanations, advice, jokes, study help, etc.).

Reply in {language}. Keep answers clear and useful (short paragraphs or bullets).
Be witty when the question is silly, but stay respectful.
If the user asks about hiring people for sexual services or anything illegal/exploitative,
politely refuse and suggest they use KaamLink for construction workers (mason, painter, plumber, etc.) instead.
Do not provide illegal instructions.
Return JSON: {{"answer": "..."}}
"""
    try:
        data = groq_client.chat_json(
            system,
            f"User question: {question}",
            model=settings.groq_llm_model,
        )
        ans = (data.get("answer") or "").strip() or "Sorry, I could not generate an answer. Try again."
    except Exception as exc:
        logger.warning("general chat failed: %s", exc)
        ans = "I hit a temporary AI error. Please try again in a moment."
    return {"answer": ans, "sources": [], "language": language, "mode": "general"}


def _rag_answer(question: str, language: str, hits: list[tuple[float, KbChunk]], demo_mode: bool) -> dict:
    context = "\n\n---\n\n".join(f"[{h.source}]\n{h.text}" for _, h in hits)
    sources = list(dict.fromkeys(h.source for _, h in hits))

    if demo_mode or settings.demo_mode or not settings.groq_api_key:
        body = _clean_extract(hits[0][1].text)[:420]
        return {
            "answer": f"Based on {hits[0][1].source}: {body}",
            "sources": sources[:3],
            "language": language,
            "mode": "kaamlink_demo",
        }

    system = f"""You are KaamLink Assistant. Answer using the provided KaamLink docs context.
Reply in {language}. Be practical and clear (bullets OK).
Do not invent laws or exact legal figures.
If context is incomplete, say what you know and what is missing.
Return JSON: {{"answer": "..."}}
"""
    try:
        data = groq_client.chat_json(
            system,
            f"Context:\n{context}\n\nQuestion: {question}",
            model=settings.groq_llm_model,
        )
        ans = (data.get("answer") or "").strip()
        if not ans:
            ans = _clean_extract(hits[0][1].text)[:400]
    except Exception as exc:
        logger.warning("RAG LLM failed: %s", exc)
        ans = _clean_extract(hits[0][1].text)[:400]
    return {"answer": ans, "sources": sources, "language": language, "mode": "kaamlink"}


def answer_question(question: str, language: str = "English", demo_mode: bool = False) -> dict:
    q = (question or "").strip()
    language = language or "English"

    try:
        groq_client.list_available_models()
    except Exception:
        pass

    if len(q) < 2:
        return {
            "answer": "Ask me anything — KaamLink hiring/wages/safety, or a random general question.",
            "sources": [],
            "language": language,
            "mode": "empty",
        }

    if _is_hard_blocked(q):
        return {"answer": _hard_block_msg(language), "sources": [], "language": language, "mode": "blocked"}

    # Prefer docs when the question looks domain-related and retrieval is strong
    hits = retrieve(q, top_k=4, min_score=0.32) if _looks_domain(q) else []
    if not hits and _looks_domain(q):
        hits = retrieve(q, top_k=3, min_score=0.28)

    if hits and hits[0][0] >= 0.38:
        return _rag_answer(q, language, hits, demo_mode)

    # Everything else → general AI chat (random questions welcome)
    return _general_answer(q, language, demo_mode=demo_mode)
