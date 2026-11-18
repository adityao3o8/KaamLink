import json
import random
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Alert, HistoricalJob, Job, MetricEvent, Worker
from app.services.embeddings import dumps_embedding, embed_text
from app.services.llm import extract_job_safe
from app.models import SKILLS

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

AREAS = ["Chengalpattu", "Chennai", "Tambaram", "Guindy", "Porur", "OMR", "ECR", "Velachery"]


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    jobs = db.query(Job).all()
    by_trade = Counter((j.skill or "unknown") for j in jobs)
    jobs_per_trade = [{"skill": k, "count": v} for k, v in by_trade.most_common()]

    # acceptance over time (by day)
    alerts = db.query(Alert).filter(Alert.response.isnot(None)).all()
    by_day = defaultdict(lambda: {"yes": 0, "total": 0})
    for a in alerts:
        day = (a.created_at or datetime.utcnow()).date().isoformat()
        by_day[day]["total"] += 1
        if a.response == "yes":
            by_day[day]["yes"] += 1
    acceptance_over_time = [
        {"date": d, "rate": (v["yes"] / v["total"] if v["total"] else 0), "total": v["total"]}
        for d, v in sorted(by_day.items())
    ]

    ms_events = db.query(MetricEvent).filter(MetricEvent.event_type == "time_to_shortlist").all()
    avg_shortlist = sum(e.value for e in ms_events) / len(ms_events) if ms_events else 0
    shortlist_series = [
        {"job_meta": e.meta, "ms": e.value, "at": e.created_at.isoformat() if e.created_at else None}
        for e in ms_events[-30:]
    ]

    top_workers = (
        db.query(Worker).order_by(Worker.reliability.desc()).limit(10).all()
    )
    top10 = [
        {"id": w.id, "name": w.name, "skill": w.skill, "reliability": w.reliability, "area": w.area}
        for w in top_workers
    ]

    lang_dist = Counter((j.language or "English") for j in jobs)
    languages = [{"language": k, "count": v} for k, v in lang_dist.most_common()]

    return {
        "jobs_per_trade": jobs_per_trade,
        "acceptance_over_time": acceptance_over_time,
        "avg_time_to_shortlist_ms": round(avg_shortlist, 2),
        "shortlist_series": shortlist_series,
        "top_workers": top10,
        "language_distribution": languages,
        "totals": {
            "jobs": len(jobs),
            "workers": db.query(Worker).count(),
            "alerts": db.query(Alert).count(),
        },
    }


@router.post("/generate-demo")
def generate_demo(db: Session = Depends(get_db)):
    """Simulate 100 jobs (+ some alerts/metrics) for dashboard demo."""
    random.seed()
    today = date.today()
    created = 0
    for i in range(100):
        skill = random.choice(SKILLS)
        area = random.choice(AREAS)
        wage = random.choice([550, 600, 650, 700, 750, 800, 850, 900, 950, 1000])
        count = random.randint(1, 5)
        lang = random.choice(["Hindi", "Tamil", "English"])
        day = today - timedelta(days=random.randint(0, 20))
        text = f"{count} {skill} needed in {area}, {wage} per day"
        extracted = extract_job_safe(text, day.isoformat(), demo_mode=True)
        job = Job(
            transcript=text,
            skill=extracted.get("skill") or skill,
            count=extracted.get("count") or count,
            date=extracted.get("date") or (day + timedelta(days=1)).isoformat(),
            location=extracted.get("location") or area,
            wage_per_day=extracted.get("wage_per_day") or wage,
            language=lang,
            status="matched",
            shortlist_ms=random.randint(40, 400),
            demo_mode=True,
            created_at=datetime.combine(day, datetime.min.time()) + timedelta(hours=random.randint(8, 18)),
        )
        db.add(job)
        db.flush()
        db.add(
            MetricEvent(
                event_type="time_to_shortlist",
                value=float(job.shortlist_ms),
                meta=json.dumps({"job_id": job.id}),
                created_at=job.created_at,
            )
        )
        # fake alert replies
        workers = db.query(Worker).filter(Worker.skill == skill).limit(3).all()
        for w in workers:
            yes = random.random() < 0.5
            db.add(
                Alert(
                    job_id=job.id,
                    worker_id=w.id,
                    message=f"Demo alert for {w.name}",
                    language=w.languages_list()[0] if w.languages_list() else "English",
                    response="yes" if yes else "no",
                    status="accepted" if yes else "declined",
                    confirmed=yes,
                    score=round(random.uniform(0.5, 0.95), 3),
                    created_at=job.created_at,
                )
            )
        created += 1
    db.commit()
    return {"ok": True, "jobs_created": created}
