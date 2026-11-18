"""Local RAG over docs_kb using multilingual-e5 + Groq answer."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from app.config import BASE_DIR, settings
from app.database import SessionLocal
from app.models import KbChunk
from app.services.embeddings import cosine_similarity, dumps_embedding, embed_query, embed_text
from app.services import groq_client

logger = logging.getLogger("kaamlink.rag")

DOCS_DIR = BASE_DIR.parent / "docs_kb"
# also allow /Users/.../nlp/docs_kb when BASE_DIR is backend/
if not DOCS_DIR.exists():
    DOCS_DIR = Path(__file__).resolve().parents[3] / "docs_kb"


def _chunk_text(text: str, size: int = 500) -> list[str]:
    parts = []
    buf = []
    count = 0
    for para in text.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if count + len(para) > size and buf:
            parts.append("\n\n".join(buf))
            buf = [para]
            count = len(para)
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


def retrieve(question: str, top_k: int = 3) -> list[KbChunk]:
    db = SessionLocal()
    try:
        q = embed_query(question)
        chunks = db.query(KbChunk).all()
        scored = [(cosine_similarity(q, c.embedding_vector()), c) for c in chunks]
        scored = [(s, c) for s, c in scored if s > 0.15]
        scored.sort(key=lambda x: x[0], reverse=True)
        # detach text/source for use after session close
        results = []
        for _, c in scored[:top_k]:
            results.append(KbChunk(id=c.id, source=c.source, text=c.text, embedding=c.embedding))
        return results
    finally:
        db.close()


def answer_question(question: str, language: str = "English", demo_mode: bool = False) -> dict:
    hits = retrieve(question, top_k=3)
    if not hits:
        return {
            "answer": "I do not know based on the available KaamLink sample documents.",
            "sources": [],
            "language": language,
        }
    context = "\n\n---\n\n".join(f"[{h.source}]\n{h.text}" for h in hits)
    sources = list(dict.fromkeys(h.source for h in hits))
    if demo_mode or settings.demo_mode or not settings.groq_api_key:
        # simple extractive demo answer
        snippet = hits[0].text.split("\n")[0][:240]
        return {
            "answer": f"(Demo) From {hits[0].source}: {snippet}",
            "sources": sources,
            "language": language,
        }
    system = (
        "You answer worker questions using ONLY the provided context from KaamLink sample docs. "
        "If the answer is not in the context, say you do not know. "
        f"Reply in {language}. Do not invent laws, section numbers, or exact legal figures. "
        'Return JSON {"answer":"..."}.'
    )
    try:
        data = groq_client.chat_json(
            system,
            f"Context:\n{context}\n\nQuestion: {question}",
            model=settings.groq_llm_model,
        )
        ans = data.get("answer") or "I do not know."
    except Exception as exc:
        logger.warning("RAG LLM failed: %s", exc)
        ans = f"From {hits[0].source}: {hits[0].text[:300]}"
    return {"answer": ans, "sources": sources, "language": language}
