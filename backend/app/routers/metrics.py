import json
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import BASE_DIR
from app.database import get_db
from app.models import Alert, Job, MetricEvent
from app.schemas import MetricsResponse
from app.services.eval_set import EVAL_SAMPLES, field_matches
from app.services.llm import extract_job_safe

router = APIRouter(prefix="/api", tags=["metrics"])
RESULTS = BASE_DIR.parent / "eval" / "results.json"


@router.get("/metrics", response_model=MetricsResponse)
def get_metrics(db: Session = Depends(get_db)):
    details = []
    total_fields = 0
    correct_fields = 0
    today = date.today().isoformat()

    for sample in EVAL_SAMPLES:
        extracted = extract_job_safe(sample["text"], today, demo_mode=True)
        expected = sample["expected"]
        row = {"text": sample["text"], "fields": {}}
        for field, exp_val in expected.items():
            total_fields += 1
            pred = extracted.get(field)
            ok = field_matches(field, pred, exp_val)
            if ok:
                correct_fields += 1
            row["fields"][field] = {"expected": exp_val, "predicted": pred, "ok": ok}
        details.append(row)

    accuracy = (correct_fields / total_fields) if total_fields else 0.0

    avg_ms = (
        db.query(func.avg(MetricEvent.value))
        .filter(MetricEvent.event_type == "time_to_shortlist")
        .scalar()
    )
    if avg_ms is None:
        avg_job_ms = db.query(func.avg(Job.shortlist_ms)).scalar()
        avg_ms = float(avg_job_ms or 0)

    total_alerts = db.query(Alert).filter(Alert.response.isnot(None)).count()
    total_accepts = db.query(Alert).filter(Alert.response == "yes").count()
    acceptance = (total_accepts / total_alerts) if total_alerts else 0.0

    eval_results = None
    if RESULTS.exists():
        try:
            eval_results = json.loads(RESULTS.read_text(encoding="utf-8"))
        except Exception:
            eval_results = None

    return MetricsResponse(
        extraction_accuracy=round(accuracy, 4),
        extraction_details=details,
        avg_time_to_shortlist_ms=round(float(avg_ms or 0), 2),
        match_acceptance_rate=round(acceptance, 4),
        total_jobs=db.query(Job).count(),
        total_alerts=total_alerts,
        total_accepts=total_accepts,
        eval_results=eval_results,
    )
