import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Job, MetricEvent, Worker
from app.schemas import MatchCard, MatchResponse, ScoreBreakdown
from app.services.matching import mask_phone, match_workers

router = APIRouter(prefix="/api", tags=["matching"])


@router.post("/match/{job_id}", response_model=MatchResponse)
def match_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if not job.skill or not job.date:
        raise HTTPException(400, "Job is incomplete. Answer the clarifying question first.")

    job_dict = {
        "skill": job.skill,
        "count": job.count,
        "date": job.date,
        "location": job.location,
        "wage_per_day": job.wage_per_day,
        "language": job.language,
    }
    workers = db.query(Worker).all()
    t0 = time.perf_counter()
    scored = match_workers(workers, job_dict, top_k=10)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    job.shortlist_ms = elapsed_ms
    job.status = "matched"
    db.add(
        MetricEvent(
            event_type="time_to_shortlist",
            value=float(elapsed_ms),
            meta=f'{{"job_id": {job.id}}}',
        )
    )
    db.commit()

    matches = []
    for worker, breakdown in scored:
        matches.append(
            MatchCard(
                worker_id=worker.id,
                name=worker.name,
                skill=worker.skill,
                area=worker.area,
                experience_years=worker.experience_years,
                expected_wage=worker.expected_wage,
                reliability=worker.reliability,
                languages=worker.languages_list(),
                phone_masked=mask_phone(worker.phone),
                score=ScoreBreakdown(**breakdown),
            )
        )
    return MatchResponse(job_id=job.id, matches=matches, shortlist_ms=elapsed_ms)
