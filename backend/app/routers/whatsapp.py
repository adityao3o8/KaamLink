"""Optional Twilio WhatsApp sandbox webhook. Disabled unless ENABLE_TWILIO=true."""
from __future__ import annotations

import logging
from datetime import date

import httpx
from fastapi import APIRouter, Depends, Form, Request, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Alert, Job
from app.routers.alerts import _alert_response, create_alerts, reply_alert
from app.schemas import AlertReplyRequest
from app.services.llm import extract_job_safe
from app.services.matching import match_workers, mask_phone
from app.services.stt import transcribe_audio
from app.models import Worker

router = APIRouter(tags=["whatsapp"])
logger = logging.getLogger("kaamlink.whatsapp")

# map phone -> last job id for contractor sessions
_sessions: dict[str, int] = {}


def _twilio_enabled() -> bool:
    return bool(
        settings.enable_twilio
        and settings.twilio_account_sid
        and settings.twilio_auth_token
    )


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
    From: str = Form(""),
    Body: str = Form(""),
    NumMedia: int = Form(0),
    MediaUrl0: str = Form(""),
    MediaContentType0: str = Form(""),
):
    if not _twilio_enabled():
        return Response(
            content="<?xml version='1.0' encoding='UTF-8'?><Response><Message>Twilio disabled</Message></Response>",
            media_type="application/xml",
        )

    body = (Body or "").strip()
    reply_text = "Send a job voice note or text like: Kal 3 mason chahiye Chengalpattu 800"

    # worker YES/NO against recent alerts by phone
    phone_digits = "".join(ch for ch in From if ch.isdigit())[-10:]
    lower = body.lower()
    if lower in {"yes", "haan", "ha", "no", "nahi", "illai", "illa"}:
        worker = db.query(Worker).filter(Worker.phone.contains(phone_digits[-10:] if phone_digits else "___")).first()
        if worker:
            alert = (
                db.query(Alert)
                .filter(Alert.worker_id == worker.id, Alert.status == "sent")
                .order_by(Alert.id.desc())
                .first()
            )
            if alert:
                resp = "yes" if lower in {"yes", "haan", "ha"} else "no"
                reply_alert(alert.id, AlertReplyRequest(response=resp), db)
                reply_text = f"Recorded: {resp.upper()}. Thanks!"
                return _twiml(reply_text)

    transcript = body
    if NumMedia and MediaUrl0:
        try:
            auth = (settings.twilio_account_sid, settings.twilio_auth_token)
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.get(MediaUrl0, auth=auth)
                r.raise_for_status()
                ext = ".ogg"
                if "mpeg" in (MediaContentType0 or ""):
                    ext = ".mp3"
                transcript = transcribe_audio(r.content, f"wa{ext}", language="auto")
        except Exception as exc:
            logger.exception("WA media download failed")
            reply_text = f"Could not download voice note: {exc}"
            return _twiml(reply_text)

    if not transcript:
        return _twiml(reply_text)

    extracted = extract_job_safe(transcript, date.today().isoformat())
    job = Job(
        transcript=transcript,
        skill=extracted.get("skill"),
        count=extracted.get("count") or 1,
        date=extracted.get("date"),
        location=extracted.get("location"),
        wage_per_day=extracted.get("wage_per_day"),
        language=extracted.get("language") or "English",
        missing_fields=__import__("json").dumps(extracted.get("missing_fields") or []),
        clarifying_question=extracted.get("clarifying_question"),
        status="ready" if not extracted.get("missing_fields") else "needs_clarification",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    _sessions[From] = job.id

    if extracted.get("missing_fields"):
        reply_text = extracted.get("clarifying_question") or "Please add missing details."
        return _twiml(reply_text)

    workers = db.query(Worker).all()
    scored = match_workers(
        workers,
        {
            "skill": job.skill,
            "date": job.date,
            "location": job.location,
            "wage_per_day": job.wage_per_day,
            "language": job.language,
        },
        top_k=5,
    )
    lines = [f"Shortlist for {job.count} {job.skill} @ {job.location}:"]
    for i, (w, br) in enumerate(scored, 1):
        lines.append(
            f"{i}. {w.name} ({w.area}) ★{w.reliability} score={br['total']} phone={mask_phone(w.phone)}"
        )
    lines.append("Open KaamLink web UI to send wave alerts.")
    reply_text = "\n".join(lines)
    return _twiml(reply_text)


def _twiml(text: str) -> Response:
    safe = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    xml = f"<?xml version='1.0' encoding='UTF-8'?><Response><Message>{safe}</Message></Response>"
    return Response(content=xml, media_type="application/xml")
