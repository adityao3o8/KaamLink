from datetime import date, timedelta

from app.services.llm import JobExtractModel, extract_job_offline, extract_job_safe
from app.services.matching import area_match, score_worker, wage_fit
from app.models import Worker


def test_job_schema_validation():
    m = JobExtractModel(
        skill="Mason",
        count=3,
        date="2026-01-01",
        location="Chengalpattu",
        wage_per_day=800,
        language="Hindi",
        missing_fields=[],
    )
    assert m.skill == "mason"


def test_offline_extraction_hinglish():
    today = date.today().isoformat()
    data = extract_job_offline("Kal 3 mason chahiye, Chengalpattu mein, 800 per day", today)
    assert data["skill"] == "mason"
    assert data["count"] == 3
    assert data["wage_per_day"] == 800
    assert "Chengalpattu" in data["location"]
    assert data["date"] == (date.today() + timedelta(days=1)).isoformat()
    assert data["missing_fields"] == []


def test_clarifying_question():
    today = date.today().isoformat()
    data = extract_job_safe("Kal mason chahiye", today, demo_mode=True)
    assert len(data["missing_fields"]) > 0
    assert data["clarifying_question"]


def test_wage_fit_and_lowball_threshold():
    assert wage_fit(700, 800) == 1.0
    assert wage_fit(1000, 800) < 1.0
    median = 800
    offered = 600
    assert offered < 0.85 * median


def test_area_match():
    assert area_match("Chengalpattu", "Chengalpattu") == 1.0
    assert area_match("Chennai", "Tambaram") >= 0.7


def test_matching_score_bounds():
    w = Worker(
        name="Test",
        phone="9000000000",
        skill="mason",
        experience_years=5,
        area="Chengalpattu",
        languages="Hindi",
        expected_wage=750,
        availability="[]",
        reliability=5.0,
        profile_text="mason Chengalpattu",
        embedding="[]",
    )
    job = {"skill": "mason", "location": "Chengalpattu", "wage_per_day": 800, "date": None, "language": "Hindi"}
    s = score_worker(w, job, [])
    assert 0 <= s["total"] <= 1
    assert set(s) >= {"embedding", "reliability", "wage_fit", "area_match", "total"}
