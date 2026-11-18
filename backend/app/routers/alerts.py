"""Alert simulation with wave-based auto-fallback matching."""
from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, get_db
from app.models import Alert, Job, MetricEvent, TimelineEvent, Worker
from app.schemas import AlertBubble, AlertReplyRequest, AlertResponse
from app.services.llm import write_alert
from app.services.matching import match_workers

router = APIRouter(prefix="/api", tags=["alerts"])
logger = logging.getLogger("kaamlink.alerts")

# in-memory wave runners
_wave_tasks: dict[int, asyncio.Task] = {}


def _bubble(alert: Alert, worker: Optional[Worker]) -> AlertBubble:
    return AlertBubble(
        alert_id=alert.id,
        worker_id=alert.worker_id,
        worker_name=worker.name if worker else "Worker",
        language=alert.language,
        message=alert.message,
        response=alert.response,
        status=alert.status or "sent",
        confirmed=alert.confirmed,
        phone=worker.phone if alert.confirmed and worker else None,
        score=alert.score,
        wave=alert.wave or 1,
    )


def _add_timeline(db: Session, job_id: int, message: str) -> None:
    db.add(TimelineEvent(job_id=job_id, message=message))


def _timeline(db: Session, job_id: int) -> list[dict]:
    rows = (
        db.query(TimelineEvent)
        .filter(TimelineEvent.job_id == job_id)
        .order_by(TimelineEvent.id)
        .all()
    )
    return [{"id": r.id, "message": r.message, "at": r.created_at.isoformat() if r.created_at else None} for r in rows]


def _alert_response(db: Session, job: Job) -> AlertResponse:
    alerts = db.query(Alert).filter(Alert.job_id == job.id).order_by(Alert.id).all()
    bubbles = []
    for a in alerts:
        w = db.get(Worker, a.worker_id)
        bubbles.append(_bubble(a, w))
    confirmed = sum(1 for a in alerts if a.confirmed)
    return AlertResponse(
        job_id=job.id,
        alerts=bubbles,
        timeline=_timeline(db, job.id),
        confirmed_count=confirmed,
        needed=job.count or 1,
    )


def _create_alert_for_worker(db: Session, job: Job, worker: Worker, breakdown: dict, wave: int) -> Alert:
    lang = worker.languages_list()[0] if worker.languages_list() else "English"
    message = write_alert(
        worker_name=worker.name,
        worker_language=lang,
        skill=job.skill or "",
        date=job.date or "",
        location=job.location or "",
        wage=job.wage_per_day or 0,
        count=job.count or 1,
    )
    alert = Alert(
        job_id=job.id,
        worker_id=worker.id,
        message=message,
        language=lang,
        score=breakdown.get("total", 0),
        score_breakdown=json.dumps(breakdown),
        status="sent",
        wave=wave,
        sent_at=datetime.utcnow(),
    )
    db.add(alert)
    db.flush()
    _add_timeline(db, job.id, f"Alerted {worker.name} (wave {wave})")
    return alert


async def _wave_watchdog(job_id: int) -> None:
    """Poll alerts; on timeout mark timed_out and alert next ranked workers."""
    timeout = settings.alert_timeout_seconds
    try:
        while True:
            await asyncio.sleep(min(5, max(2, timeout // 4)))
            db = SessionLocal()
            try:
                job = db.get(Job, job_id)
                if not job:
                    return
                needed = job.count or 1
                confirmed = db.query(Alert).filter(Alert.job_id == job_id, Alert.confirmed.is_(True)).count()
                if confirmed >= needed:
                    job.status = "confirmed"
                    db.commit()
                    return

                now = datetime.utcnow()
                pending = (
                    db.query(Alert)
                    .filter(Alert.job_id == job_id, Alert.status == "sent")
                    .all()
                )
                timed_any = False
                for a in pending:
                    sent = a.sent_at or a.created_at or now
                    if now - sent >= timedelta(seconds=timeout):
                        a.status = "timed_out"
                        w = db.get(Worker, a.worker_id)
                        _add_timeline(db, job_id, f"{w.name if w else 'Worker'} timed out → next wave")
                        timed_any = True
                if timed_any:
                    db.commit()
                    _launch_next_wave(db, job)
                    db.commit()

                # stop if pool exhausted and no pending
                still_pending = db.query(Alert).filter(Alert.job_id == job_id, Alert.status == "sent").count()
                total_alerts = db.query(Alert).filter(Alert.job_id == job_id).count()
                workers = db.query(Worker).filter(Worker.skill == job.skill).count()
                if still_pending == 0 and total_alerts >= workers:
                    _add_timeline(db, job_id, "Pool exhausted — no more workers to alert")
                    db.commit()
                    return
            finally:
                db.close()
    except asyncio.CancelledError:
        return
    except Exception as exc:  # pragma: no cover
        logger.exception("wave watchdog error: %s", exc)


def _ranked_pool(db: Session, job: Job) -> list[tuple[Worker, dict]]:
    job_dict = {
        "skill": job.skill,
        "count": job.count,
        "date": job.date,
        "location": job.location,
        "wage_per_day": job.wage_per_day,
        "language": job.language,
    }
    workers = db.query(Worker).all()
    return match_workers(workers, job_dict, top_k=50)


def _launch_next_wave(db: Session, job: Job, wave_size: int = 5) -> list[Alert]:
    needed = job.count or 1
    confirmed = db.query(Alert).filter(Alert.job_id == job.id, Alert.confirmed.is_(True)).count()
    if confirmed >= needed:
        return []
    already = {a.worker_id for a in db.query(Alert).filter(Alert.job_id == job.id).all()}
    pending_sent = db.query(Alert).filter(Alert.job_id == job.id, Alert.status == "sent").count()
    if pending_sent > 0:
        return []
    ranked = _ranked_pool(db, job)
    remaining_slots = max(0, needed - confirmed)
    to_send = min(wave_size, max(remaining_slots, 1) * 2)  # buffer
    wave_num = 1 + (db.query(Alert).filter(Alert.job_id == job.id).count() // wave_size)
    created = []
    for worker, breakdown in ranked:
        if worker.id in already:
            continue
        alert = _create_alert_for_worker(db, job, worker, breakdown, wave_num)
        created.append(alert)
        if len(created) >= min(wave_size, to_send):
            break
    if created:
        _add_timeline(db, job.id, f"Wave {wave_num}: alerted {len(created)} workers")
    return created


@router.post("/alert/{job_id}", response_model=AlertResponse)
async def create_alerts(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if not job.skill:
        raise HTTPException(400, "Job incomplete")

    # reset
    db.query(Alert).filter(Alert.job_id == job_id).delete()
    db.query(TimelineEvent).filter(TimelineEvent.job_id == job_id).delete()
    db.commit()

    _add_timeline(db, job.id, f"Starting alerts for {job.count} {job.skill}(s)")
    created = _launch_next_wave(db, job, wave_size=5)
    if not created:
        _add_timeline(db, job.id, "No matching workers available")
    job.status = "alerted"
    db.commit()

    # start watchdog
    old = _wave_tasks.pop(job_id, None)
    if old and not old.done():
        old.cancel()
    _wave_tasks[job_id] = asyncio.create_task(_wave_watchdog(job_id))

    return _alert_response(db, job)


@router.post("/alert/{alert_id}/reply", response_model=AlertBubble)
def reply_alert(alert_id: int, body: AlertReplyRequest, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    resp = (body.response or "").strip().lower()
    yes_words = {"yes", "haan", "ha", "ok", "ஆம்", "ama", "amaa"}
    no_words = {"no", "nahi", "illa", "illai", "இல்லை", "nope"}
    if resp in yes_words:
        resp = "yes"
    elif resp in no_words:
        resp = "no"
    if resp not in {"yes", "no"}:
        raise HTTPException(400, "Response must be yes or no")

    alert.response = resp
    alert.confirmed = resp == "yes"
    alert.status = "accepted" if resp == "yes" else "declined"
    worker = db.get(Worker, alert.worker_id)
    job = db.get(Job, alert.job_id)

    db.add(
        MetricEvent(
            event_type="alert_reply",
            value=1.0 if resp == "yes" else 0.0,
            meta=json.dumps({"alert_id": alert.id, "job_id": alert.job_id, "response": resp}),
        )
    )
    if worker:
        verb = "accepted" if resp == "yes" else "declined"
        _add_timeline(db, alert.job_id, f"{worker.name} {verb}")
    db.flush()

    if job and alert.confirmed:
        confirmed_count = db.query(Alert).filter(Alert.job_id == job.id, Alert.confirmed.is_(True)).count()
        if confirmed_count >= (job.count or 1):
            job.status = "confirmed"
            _add_timeline(db, job.id, f"Need met — {confirmed_count}/{job.count} confirmed")
        else:
            # if no pending sent, launch next wave
            pending = db.query(Alert).filter(Alert.job_id == job.id, Alert.status == "sent").count()
            if pending == 0:
                _add_timeline(db, job.id, "Still need more — alerting next workers")
                _launch_next_wave(db, job)
    elif job and resp == "no":
        pending = db.query(Alert).filter(Alert.job_id == job.id, Alert.status == "sent").count()
        if pending == 0:
            _add_timeline(db, job.id, f"{worker.name if worker else 'Worker'} declined → alerting next")
            _launch_next_wave(db, job)

    db.commit()
    db.refresh(alert)
    return _bubble(alert, worker)


@router.get("/alert/{job_id}", response_model=AlertResponse)
def list_alerts(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return _alert_response(db, job)


@router.post("/alert/{job_id}/simulate", response_model=AlertResponse)
def simulate_replies(job_id: int, db: Session = Depends(get_db)):
    """Auto accept/decline pending alerts randomly for demo."""
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    pending = db.query(Alert).filter(Alert.job_id == job_id, Alert.status == "sent").all()
    needed = job.count or 1
    confirmed = db.query(Alert).filter(Alert.job_id == job_id, Alert.confirmed.is_(True)).count()
    for a in pending:
        if confirmed >= needed:
            # remaining decline
            choice = "no"
        else:
            choice = "yes" if random.random() < 0.55 else "no"
        a.response = choice
        a.confirmed = choice == "yes"
        a.status = "accepted" if choice == "yes" else "declined"
        w = db.get(Worker, a.worker_id)
        _add_timeline(db, job_id, f"[Sim] {w.name if w else 'Worker'} → {choice.upper()}")
        db.add(
            MetricEvent(
                event_type="alert_reply",
                value=1.0 if choice == "yes" else 0.0,
                meta=json.dumps({"alert_id": a.id, "simulated": True}),
            )
        )
        if choice == "yes":
            confirmed += 1
    if confirmed >= needed:
        job.status = "confirmed"
        _add_timeline(db, job_id, "Simulation complete — need met")
    else:
        _launch_next_wave(db, job)
        _add_timeline(db, job_id, "Simulation: still short — next wave queued")
    db.commit()
    return _alert_response(db, job)
