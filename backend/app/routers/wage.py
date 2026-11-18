import statistics
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import HistoricalJob
from app.schemas import WageSuggestResponse

router = APIRouter(prefix="/api/wage", tags=["wage"])


def _percentile(sorted_vals: list[int], p: float) -> int:
    if not sorted_vals:
        return 0
    k = (len(sorted_vals) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return int(sorted_vals[f])
    return int(sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f))


@router.get("/suggest", response_model=WageSuggestResponse)
def suggest_wage(
    skill: str = Query(...),
    area: str = Query(...),
    offered: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    skill_l = skill.lower().strip()
    area_l = area.strip()
    rows = (
        db.query(HistoricalJob)
        .filter(HistoricalJob.skill == skill_l)
        .all()
    )
    # prefer same area, else any for skill
    same = [r.wage for r in rows if r.area.lower() == area_l.lower()]
    wages = sorted(same or [r.wage for r in rows])
    if not wages:
        # defaults
        wages = [700, 750, 800, 850, 900]
    median = int(statistics.median(wages))
    p25 = _percentile(wages, 0.25)
    p75 = _percentile(wages, 0.75)
    is_lowball = False
    message = f"Typical wage: ₹{p25}–{p75} (median ₹{median})"
    if offered is not None and median > 0 and offered < 0.85 * median:
        is_lowball = True
        message = f"⚠️ Offered ₹{offered} is below 85% of median ₹{median}. Typical: ₹{p25}–{p75}."
    return WageSuggestResponse(
        skill=skill_l,
        area=area_l,
        median=median,
        p25=p25,
        p75=p75,
        sample_size=len(wages),
        offered=offered,
        is_lowball=is_lowball,
        message=message,
    )
