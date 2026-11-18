"""Speech-to-text via Groq Whisper with language hints and optional ffmpeg convert."""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from app.config import settings
from app.services import groq_client
from app.services.llm import CANNED_TRANSCRIPTS, CANNED_WORKER_TRANSCRIPTS

logger = logging.getLogger("kaamlink.stt")

TRADE_PROMPT = (
    "Construction labour voice note. Trade words: mason, mestri, raj mistri, painter, "
    "colour wala, plumber, pipe wala, electrician, wireman, helper, mazdoor, carpenter, "
    "Chengalpattu, Chennai, Tambaram, wage per day, kal, naalai, chahiye, venum."
)

SUPPORTED_EXT = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm", ".ogg", ".flac"}


def _ffmpeg_convert(audio_bytes: bytes, src_suffix: str) -> tuple[bytes, str]:
    if not shutil.which("ffmpeg"):
        return audio_bytes, f"audio{src_suffix or '.webm'}"
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / f"in{src_suffix or '.webm'}"
        dst = Path(td) / "out.wav"
        src.write_bytes(audio_bytes)
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(src), "-ar", "16000", "-ac", "1", str(dst)],
                check=True,
                capture_output=True,
                timeout=30,
            )
            return dst.read_bytes(), "audio.wav"
        except Exception as exc:
            logger.warning("ffmpeg convert failed: %s", exc)
            return audio_bytes, f"audio{src_suffix or '.webm'}"


def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "audio.webm",
    *,
    language: Optional[str] = None,
    demo_mode: bool = False,
    kind: str = "job",
) -> str:
    if demo_mode or settings.demo_mode:
        lang = (language or "auto").lower()
        key = lang if lang in {"hi", "ta", "en", "auto"} else lang[:2]
        bucket = CANNED_WORKER_TRANSCRIPTS if kind == "worker" else CANNED_TRANSCRIPTS
        return bucket.get(key, bucket["auto"])

    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not set. Enable Demo mode or type instead.")

    suffix = Path(filename).suffix.lower() or ".webm"
    data, out_name = audio_bytes, filename
    if suffix not in SUPPORTED_EXT:
        data, out_name = _ffmpeg_convert(audio_bytes, suffix)
    elif suffix in {".webm", ".ogg"} and shutil.which("ffmpeg"):
        # prefer wav for broader compatibility
        data, out_name = _ffmpeg_convert(audio_bytes, suffix)

    try:
        return groq_client.transcribe(
            data,
            out_name,
            language=language,
            prompt=TRADE_PROMPT,
        )
    except Exception as exc:
        logger.warning("STT failed, canned fallback: %s", exc)
        lang = (language or "auto").lower()
        key = lang if lang in {"hi", "ta", "en", "auto"} else lang[:2]
        bucket = CANNED_WORKER_TRANSCRIPTS if kind == "worker" else CANNED_TRANSCRIPTS
        return bucket.get(key, bucket["auto"])
