import json
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Worker
from app.schemas import ConfirmWorkerRequest, TextWorkerRequest, WorkerExtracted, WorkerResponse
from app.services.embeddings import dumps_embedding, embed_text
from app.services.llm import extract_worker_safe
from app.services.stt import transcribe_audio

router = APIRouter(prefix="/api/worker", tags=["workers"])


def _build_profile_text(data: dict) -> str:
    if data.get("profile_text"):
        return data["profile_text"]
    return (
        f"{data.get('name')} is a {data.get('skill')} with {data.get('experience_years')} years "
        f"in {data.get('area')}, wage {data.get('expected_wage')}"
    )


@router.post("/voice", response_model=WorkerResponse)
async def worker_from_voice(
    audio: UploadFile = File(...),
    phone: str = Form("9000000000"),
    language_hint: str = Form("auto"),
    demo_mode: bool = Form(False),
    db: Session = Depends(get_db),
):
    raw = await audio.read()
    if not raw:
        raise HTTPException(400, "Empty audio. Please type your profile.")
    try:
        transcript = transcribe_audio(
            raw,
            audio.filename or "audio.webm",
            language=language_hint,
            demo_mode=demo_mode,
            kind="worker",
        )
    except Exception as exc:
        raise HTTPException(400, f"Transcription failed: {exc}. Please type instead.") from exc
    extracted = extract_worker_safe(transcript, date.today().isoformat(), demo_mode=demo_mode)
    if not extracted.get("phone"):
        extracted["phone"] = phone
    return WorkerResponse(
        transcript=transcript,
        extracted=WorkerExtracted(**extracted),
        saved=False,
        message="Review and confirm to save.",
        demo_mode=demo_mode,
    )


@router.post("/text", response_model=WorkerResponse)
async def worker_from_text(body: TextWorkerRequest, db: Session = Depends(get_db)):
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(400, "Please describe yourself.")
    extracted = extract_worker_safe(text, date.today().isoformat(), demo_mode=body.demo_mode)
    if body.phone:
        extracted["phone"] = body.phone
    return WorkerResponse(
        transcript=text,
        extracted=WorkerExtracted(**extracted),
        saved=False,
        message="Review and confirm to save.",
        demo_mode=body.demo_mode,
    )


@router.post("/confirm", response_model=WorkerResponse)
async def confirm_worker(body: ConfirmWorkerRequest, db: Session = Depends(get_db)):
    if not body.name or not body.skill or not body.area:
        raise HTTPException(400, "Name, skill and area are required.")
    data = body.model_dump()
    profile = _build_profile_text(data)
    emb = embed_text(profile)
    worker = Worker(
        name=body.name,
        phone=body.phone or "9000000000",
        skill=body.skill.lower(),
        experience_years=body.experience_years,
        area=body.area,
        languages=body.languages,
        expected_wage=body.expected_wage,
        availability=json.dumps(body.availability or []),
        reliability=4.0,
        profile_text=profile,
        embedding=dumps_embedding(emb),
    )
    db.add(worker)
    db.commit()
    db.refresh(worker)
    return WorkerResponse(
        worker_id=worker.id,
        transcript=body.transcript,
        extracted=WorkerExtracted(
            name=worker.name,
            skill=worker.skill,
            experience_years=worker.experience_years,
            area=worker.area,
            availability=worker.availability_list(),
            languages=worker.languages,
            expected_wage=worker.expected_wage,
            phone=worker.phone,
            profile_text=worker.profile_text,
            missing_fields=[],
        ),
        saved=True,
        message="Worker saved and ready for matching.",
    )


@router.get("")
def list_workers(
    skill: str | None = None,
    area: str | None = None,
    available_on: str | None = None,
    db: Session = Depends(get_db),
):
    """List workers for contractors. Optional filters: skill, area, available_on (YYYY-MM-DD)."""
    q = db.query(Worker)
    if skill:
        q = q.filter(Worker.skill == skill.lower().strip())
    workers = q.order_by(Worker.reliability.desc(), Worker.id).all()
    results = []
    for w in workers:
        avail = w.availability_list()
        if available_on and avail and available_on not in avail:
            continue
        if area and area.lower() not in (w.area or "").lower():
            continue
        phone = w.phone or ""
        masked = phone[:2] + "******" + phone[-2:] if len(phone) >= 4 else "****"
        results.append(
            {
                "id": w.id,
                "name": w.name,
                "skill": w.skill,
                "area": w.area,
                "experience_years": w.experience_years,
                "reliability": w.reliability,
                "expected_wage": w.expected_wage,
                "languages": w.languages_list(),
                "availability": avail[:7],
                "phone_masked": masked,
                "available_now": (not avail) or (available_on in avail if available_on else True),
            }
        )
    return {"count": len(results), "workers": results}
