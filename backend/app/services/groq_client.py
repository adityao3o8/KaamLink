"""Shared Groq client: chat + STT with cache, semaphore, and 429 backoff."""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from typing import Any, Optional

from groq import Groq, RateLimitError, APIStatusError

from app.config import settings
from app.database import SessionLocal
from app.models import ApiCache

logger = logging.getLogger("kaamlink.groq")

_sem = threading.Semaphore(2)
_client: Optional[Groq] = None
_available_models: set[str] = set()
_models_checked = False


def get_client() -> Groq:
    global _client
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not set.")
    if _client is None:
        _client = Groq(api_key=settings.groq_api_key, timeout=60.0)
    return _client


def _cache_key(model: str, prompt: str, audio_hash: str = "") -> str:
    raw = f"{model}|{prompt}|{audio_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def cache_get(key: str) -> Optional[str]:
    db = SessionLocal()
    try:
        row = db.get(ApiCache, key)
        return row.response if row else None
    finally:
        db.close()


def cache_set(key: str, response: str, kind: str = "chat") -> None:
    db = SessionLocal()
    try:
        row = db.get(ApiCache, key)
        if row:
            row.response = response
            row.kind = kind
        else:
            db.add(ApiCache(id=key, response=response, kind=kind))
        db.commit()
    except Exception as exc:  # pragma: no cover
        logger.warning("cache write failed: %s", exc)
        db.rollback()
    finally:
        db.close()


def _pick_fallback(preferred: str, pool: set[str], kind: str) -> str:
    if preferred in pool:
        return preferred
    # fuzzy contains
    for m in sorted(pool):
        if preferred.split("/")[-1] in m:
            return m
    if kind == "stt":
        for m in sorted(pool):
            if "whisper" in m:
                return m
    else:
        # prefer larger then smaller general chat models
        for needle in ("120b", "70b", "20b", "8b", "instant", "gpt-oss"):
            for m in sorted(pool):
                if needle in m and "whisper" not in m and "prompt-guard" not in m:
                    return m
        for m in sorted(pool):
            if "whisper" not in m and "prompt-guard" not in m:
                return m
    return preferred


def list_available_models() -> set[str]:
    global _available_models, _models_checked
    if _models_checked:
        return _available_models
    _models_checked = True
    if not settings.groq_api_key:
        logger.warning("GROQ_API_KEY missing — skipping model list.")
        return _available_models
    try:
        client = get_client()
        models = client.models.list()
        _available_models = {m.id for m in getattr(models, "data", []) or []}
        # auto-correct configured models when missing
        llm = _pick_fallback(settings.groq_llm_model, _available_models, "llm")
        fast = _pick_fallback(settings.groq_fast_model, _available_models, "llm")
        stt = _pick_fallback(settings.groq_stt_model, _available_models, "stt")
        if llm != settings.groq_llm_model:
            logger.warning("GROQ_LLM_MODEL=%s unavailable → using %s", settings.groq_llm_model, llm)
            settings.groq_llm_model = llm
        else:
            logger.info("Using GROQ_LLM_MODEL=%s", llm)
        if fast != settings.groq_fast_model:
            logger.warning("GROQ_FAST_MODEL=%s unavailable → using %s", settings.groq_fast_model, fast)
            settings.groq_fast_model = fast
        else:
            logger.info("Using GROQ_FAST_MODEL=%s", fast)
        if stt != settings.groq_stt_model:
            logger.warning("GROQ_STT_MODEL=%s unavailable → using %s", settings.groq_stt_model, stt)
            settings.groq_stt_model = stt
        else:
            logger.info("Using GROQ_STT_MODEL=%s", stt)
    except Exception as exc:
        logger.warning("Could not list Groq models: %s", exc)
    return _available_models


def _retry_after_seconds(exc: Exception, attempt: int) -> float:
    headers = getattr(exc, "headers", None) or {}
    if hasattr(headers, "get"):
        ra = headers.get("retry-after") or headers.get("Retry-After")
        if ra:
            try:
                return float(ra)
            except ValueError:
                pass
    return min(2 ** attempt, 16)


def chat_json(
    system: str,
    user: str,
    *,
    model: Optional[str] = None,
    temperature: float = 0.0,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Chat completion forcing JSON object response."""
    model = model or settings.groq_llm_model
    prompt = f"SYSTEM:\n{system}\nUSER:\n{user}"
    key = _cache_key(model, prompt)
    if use_cache:
        cached = cache_get(key)
        if cached:
            return json.loads(cached)

    client = get_client()
    last_err: Exception | None = None
    for attempt in range(4):
        acquired = _sem.acquire(timeout=30)
        if not acquired:
            raise RuntimeError("Groq semaphore timeout")
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=temperature,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            content = resp.choices[0].message.content or "{}"
            data = json.loads(content)
            if use_cache:
                cache_set(key, content, kind="chat")
            return data
        except RateLimitError as exc:
            last_err = exc
            delay = _retry_after_seconds(exc, attempt)
            logger.warning("Groq 429 — retry in %.1fs", delay)
            time.sleep(delay)
        except APIStatusError as exc:
            last_err = exc
            if getattr(exc, "status_code", 0) == 429:
                delay = _retry_after_seconds(exc, attempt)
                time.sleep(delay)
                continue
            raise
        except json.JSONDecodeError as exc:
            last_err = exc
            # one soft retry with stricter prompt handled by caller usually
            raise
        finally:
            _sem.release()
    raise RuntimeError(f"Groq chat failed after retries: {last_err}")


def chat_text(
    system: str,
    user: str,
    *,
    model: Optional[str] = None,
    temperature: float = 0.2,
    use_cache: bool = True,
) -> str:
    model = model or settings.groq_fast_model
    prompt = f"SYSTEM:\n{system}\nUSER:\n{user}"
    key = _cache_key(model, prompt)
    if use_cache:
        cached = cache_get(key)
        if cached:
            return cached
    client = get_client()
    for attempt in range(4):
        acquired = _sem.acquire(timeout=30)
        if not acquired:
            raise RuntimeError("Groq semaphore timeout")
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            content = (resp.choices[0].message.content or "").strip()
            if use_cache:
                cache_set(key, content, kind="chat_text")
            return content
        except RateLimitError as exc:
            time.sleep(_retry_after_seconds(exc, attempt))
        finally:
            _sem.release()
    raise RuntimeError("Groq chat_text failed")


def transcribe(
    audio_bytes: bytes,
    filename: str = "audio.webm",
    *,
    language: Optional[str] = None,
    prompt: Optional[str] = None,
) -> str:
    model = settings.groq_stt_model
    audio_hash = hashlib.sha256(audio_bytes).hexdigest()
    key = _cache_key(model, f"{language}|{prompt}|{filename}", audio_hash)
    cached = cache_get(key)
    if cached:
        return cached

    client = get_client()
    kwargs: dict[str, Any] = {
        "file": (filename, audio_bytes),
        "model": model,
        "response_format": "text",
    }
    if language and language.lower() not in {"auto", "", "none"}:
        # Whisper expects ISO-639-1
        lang_map = {"hindi": "hi", "tamil": "ta", "english": "en", "hi": "hi", "ta": "ta", "en": "en"}
        kwargs["language"] = lang_map.get(language.lower(), language.lower()[:2])
    if prompt:
        kwargs["prompt"] = prompt

    for attempt in range(4):
        acquired = _sem.acquire(timeout=30)
        if not acquired:
            raise RuntimeError("Groq semaphore timeout")
        try:
            result = client.audio.transcriptions.create(**kwargs)
            text = result.strip() if isinstance(result, str) else str(getattr(result, "text", result)).strip()
            cache_set(key, text, kind="stt")
            return text
        except RateLimitError as exc:
            time.sleep(_retry_after_seconds(exc, attempt))
        finally:
            _sem.release()
    raise RuntimeError("Groq STT failed")
