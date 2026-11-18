import json
from typing import Optional

import numpy as np

_model = None
_model_error: Optional[str] = None


def get_model():
    global _model, _model_error
    if _model is not None:
        return _model
    if _model_error:
        return None
    try:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer("intfloat/multilingual-e5-small")
        return _model
    except Exception as exc:  # pragma: no cover
        _model_error = str(exc)
        return None


def embed_text(text: str) -> list[float]:
    """Embed text with E5 (query/passage prefix). Falls back to hash bag-of-chars vector."""
    model = get_model()
    cleaned = (text or "").strip()
    if not cleaned:
        cleaned = "empty"

    if model is not None:
        # E5 expects "query: " / "passage: " prefixes; use passage for profiles/jobs
        vec = model.encode([f"passage: {cleaned}"], normalize_embeddings=True)[0]
        return [float(x) for x in vec]

    return _fallback_embed(cleaned)


def embed_query(text: str) -> list[float]:
    model = get_model()
    cleaned = (text or "").strip() or "empty"
    if model is not None:
        vec = model.encode([f"query: {cleaned}"], normalize_embeddings=True)[0]
        return [float(x) for x in vec]
    return _fallback_embed(cleaned)


def _fallback_embed(text: str, dim: int = 384) -> list[float]:
    """Deterministic bag-of-ngrams style vector for offline demo."""
    vec = np.zeros(dim, dtype=np.float64)
    lowered = text.lower()
    for i, ch in enumerate(lowered):
        vec[ord(ch) % dim] += 1.0
        if i + 1 < len(lowered):
            bigram = (ord(ch) * 31 + ord(lowered[i + 1])) % dim
            vec[bigram] += 0.5
    # sprinkle skill keywords
    keywords = {
        "mason": 0,
        "mestri": 0,
        "painter": 40,
        "colour": 40,
        "plumber": 80,
        "electrician": 120,
        "helper": 160,
        "carpenter": 200,
        "chengalpattu": 240,
        "chennai": 280,
    }
    for word, idx in keywords.items():
        if word in lowered:
            vec[idx : idx + 10] += 2.0
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return [float(x) for x in vec]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    va = np.asarray(a, dtype=np.float64)
    vb = np.asarray(b, dtype=np.float64)
    n = min(len(va), len(vb))
    va, vb = va[:n], vb[:n]
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def dumps_embedding(vec: list[float]) -> str:
    return json.dumps(vec)
