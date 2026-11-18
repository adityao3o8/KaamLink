from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Job, Rating, Worker
from app.schemas import RatingRequest

router = APIRouter(prefix="/api", tags=["ratings"])


@router.post("/rate")
def rate_worker(body: RatingRequest, db: Session = Depends(get_db)):
    if body.stars < 1 or body.stars > 5:
        raise HTTPException(400, "Stars must be 1-5")
    job = db.get(Job, body.job_id)
    worker = db.get(Worker, body.worker_id)
    if not job or not worker:
        raise HTTPException(404, "Job or worker not found")

    rating = Rating(job_id=job.id, worker_id=worker.id, stars=body.stars)
    db.add(rating)

    # blend new rating into reliability (simple running average with prior)
    prior = worker.reliability or 4.0
    worker.reliability = round((prior * 0.7) + (body.stars * 0.3), 2)
    job.status = "rated"
    db.commit()

    return {
        "ok": True,
        "worker_id": worker.id,
        "new_reliability": worker.reliability,
        "stars": body.stars,
    }
