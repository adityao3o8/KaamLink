import io
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["tts"])
logger = logging.getLogger("kaamlink.tts")

VOICES = {
    "tamil": "ta-IN-PallaviNeural",
    "hindi": "hi-IN-SwaraNeural",
    "english": "en-IN-NeerjaNeural",
}


class TtsRequest(BaseModel):
    text: str
    language: str = "English"


@router.post("/tts")
async def synthesize(body: TtsRequest):
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(400, "text required")
    lang = (body.language or "English").split(",")[0].strip().lower()
    voice = VOICES.get(lang, VOICES["english"])
    try:
        import edge_tts

        communicate = edge_tts.Communicate(text, voice)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            out = Path(tmp.name)
        await communicate.save(str(out))
        data = out.read_bytes()
        out.unlink(missing_ok=True)
        return Response(content=data, media_type="audio/mpeg")
    except Exception as exc:
        logger.exception("TTS failed")
        raise HTTPException(500, f"TTS failed: {exc}") from exc
