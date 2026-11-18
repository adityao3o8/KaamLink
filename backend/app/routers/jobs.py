import json
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Job
from app.schemas import JobExtracted, JobResponse, TextJobRequest
from app.services.llm import extract_job_safe
from app.services.stt import transcribe_audio

router = APIRouter(prefix="/api/job", tags=["jobs"])


def _save_job(db: Session, transcript: str, extracted: dict, demo_mode: bool = False) -> Job:
    job = Job(
        transcript=transcript,
        skill=extracted.get("skill"),
        count=extracted.get("count") or 1,
        date=extracted.get("date"),
        location=extracted.get("location"),
        wage_per_day=extracted.get("wage_per_day"),
        language=extracted.get("language") or "English",
        missing_fields=json.dumps(extracted.get("missing_fields") or []),
        clarifying_question=extracted.get("clarifying_question"),
        status="needs_clarification" if extracted.get("missing_fields") else "ready",
        demo_mode=demo_mode,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _to_response(job: Job, extracted: dict, demo_mode: bool = False) -> JobResponse:
    missing = extracted.get("missing_fields") or []
    return JobResponse(
        job_id=job.id,
        transcript=job.transcript,
        language=job.language or "English",
        extracted=JobExtracted(**{**extracted, "missing_fields": missing}),
        needs_clarification=bool(missing),
        demo_mode=demo_mode,
        provider="Groq (Whisper + Llama)",
    )


@router.post("/voice", response_model=JobResponse)
async def job_from_voice(
    audio: UploadFile = File(...),
    language_hint: str = Form("auto"),
    demo_mode: bool = Form(False),
    db: Session = Depends(get_db),
):
    raw = await audio.read()
    if not raw:
        raise HTTPException(400, "Empty audio upload. Try the text box.")
    try:
        transcript = transcribe_audio(
            raw,
            audio.filename or "audio.webm",
            language=language_hint,
            demo_mode=demo_mode,
        )
    except Exception as exc:
        raise HTTPException(400, f"Transcription failed: {exc}. Please type your request instead.") from exc
    if not transcript:
        raise HTTPException(400, "Could not hear anything. Please type your request.")
    extracted = extract_job_safe(transcript, date.today().isoformat(), demo_mode=demo_mode)
    job = _save_job(db, transcript, extracted, demo_mode=demo_mode)
    return _to_response(job, extracted, demo_mode=demo_mode)


@router.post("/text", response_model=JobResponse)
async def job_from_text(body: TextJobRequest, db: Session = Depends(get_db)):
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(400, "Please enter a job request.")
    extracted = extract_job_safe(text, date.today().isoformat(), demo_mode=body.demo_mode)
    job = _save_job(db, text, extracted, demo_mode=body.demo_mode)
    return _to_response(job, extracted, demo_mode=body.demo_mode)


@router.get("/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {
        "job_id": job.id,
        "transcript": job.transcript,
        "language": job.language,
        "skill": job.skill,
        "count": job.count,
        "date": job.date,
        "location": job.location,
        "wage_per_day": job.wage_per_day,
        "status": job.status,
        "missing_fields": job.missing_fields_list(),
        "clarifying_question": job.clarifying_question,
        "demo_mode": job.demo_mode,
    }
