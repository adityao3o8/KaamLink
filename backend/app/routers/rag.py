from datetime import date

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.schemas import RagRequest, RagResponse
from app.services.rag import answer_question
from app.services.stt import transcribe_audio

router = APIRouter(prefix="/api/rag", tags=["rag"])


@router.post("/ask", response_model=RagResponse)
def ask(body: RagRequest):
    q = (body.question or "").strip()
    if not q:
        raise HTTPException(400, "question required")
    result = answer_question(q, language=body.language or "English", demo_mode=body.demo_mode)
    return RagResponse(**result)


@router.post("/ask/voice", response_model=RagResponse)
async def ask_voice(
    audio: UploadFile = File(...),
    language_hint: str = Form("auto"),
    language: str = Form("English"),
    demo_mode: bool = Form(False),
):
    raw = await audio.read()
    if not raw:
        raise HTTPException(400, "Empty audio")
    transcript = transcribe_audio(
        raw, audio.filename or "audio.webm", language=language_hint, demo_mode=demo_mode
    )
    result = answer_question(transcript, language=language, demo_mode=demo_mode)
    result["answer"] = f"[Heard: {transcript}]\n\n{result['answer']}"
    return RagResponse(**result)
