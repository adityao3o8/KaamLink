"""Job/worker extraction and alerts via Groq Llama (with offline demo fallback)."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.config import settings
from app.models import SKILLS
from app.services import groq_client

logger = logging.getLogger("kaamlink.llm")

TAXONOMY = ", ".join(SKILLS)

JOB_SYSTEM = f"""You extract structured construction job requests from Hinglish/Tanglish/English voice notes in India.
Return a JSON object with keys:
skill (one of [{TAXONOMY}] or null), count (int or null), date (YYYY-MM-DD or null),
location (string or null), wage_per_day (int INR or null),
language ("Hindi"|"Tamil"|"English"),
missing_fields (array from ["skill","count","date","location","wage_per_day"]),
clarifying_question (string in user's language if missing else null).
Normalize slang: mestri/raj mistri->mason; colour wala->painter; pipe wala->plumber;
wireman->electrician; mazdoor->helper; wood wala->carpenter.
Resolve kal/naalai=tomorrow, parso=day after tomorrow using the provided today date.
JSON keys must be English. User-facing clarifying_question in the user's language.
"""

WORKER_SYSTEM = f"""Extract a construction worker profile. Return JSON with keys:
name, skill (one of [{TAXONOMY}]), experience_years, area, availability (YYYY-MM-DD array),
languages (comma string), expected_wage, profile_text, missing_fields (from name/skill/area),
clarifying_question (user language or null). JSON keys English.
"""

ALERT_SYSTEM = """Write a short WhatsApp-style job alert. Return JSON {"message":"..."}.
Under 2 sentences. Include skill, date, location, wage. Ask Yes/No.
Write in the specified language (Tamil/Hindi/English). Simple everyday words."""


class JobExtractModel(BaseModel):
    skill: Optional[str] = None
    count: Optional[int] = None
    date: Optional[str] = None
    location: Optional[str] = None
    wage_per_day: Optional[int] = None
    language: Optional[str] = "English"
    missing_fields: list[str] = Field(default_factory=list)
    clarifying_question: Optional[str] = None

    @field_validator("skill", mode="before")
    @classmethod
    def lower_skill(cls, v):
        if v is None:
            return v
        return str(v).lower().strip() or None


class WorkerExtractModel(BaseModel):
    name: Optional[str] = None
    skill: Optional[str] = None
    experience_years: Optional[int] = 1
    area: Optional[str] = None
    availability: list[str] = Field(default_factory=list)
    languages: Optional[str] = "Hindi"
    expected_wage: Optional[int] = 700
    profile_text: Optional[str] = None
    missing_fields: list[str] = Field(default_factory=list)
    clarifying_question: Optional[str] = None


def normalize_skill(text: str) -> Optional[str]:
    lowered = (text or "").lower()
    local_map = {
        "mason": "mason", "mestri": "mason", "mistri": "mason", "raj": "mason",
        "painter": "painter", "colour": "painter", "color": "painter",
        "plumber": "plumber", "pipe": "plumber",
        "electrician": "electrician", "wire": "electrician",
        "helper": "helper", "mazdoor": "helper",
        "carpenter": "carpenter", "wood": "carpenter",
    }
    for key, skill in local_map.items():
        if key in lowered:
            return skill
    if not settings.groq_api_key or settings.demo_mode:
        return None
    try:
        data = groq_client.chat_json(
            f'Map trade slang to one of: {TAXONOMY}. Return {{"skill":"..."}}.',
            f"Trade text: {text}",
            model=settings.groq_fast_model,
        )
        skill = (data.get("skill") or "").lower().strip()
        return skill if skill in SKILLS else None
    except Exception:
        return None


def _finalize_job(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("skill"):
        data["skill"] = normalize_skill(str(data["skill"])) or (
            data["skill"].lower() if data["skill"].lower() in SKILLS else None
        )
    required = ["skill", "count", "date", "location", "wage_per_day"]
    missing = [f for f in required if data.get(f) is None or data.get(f) == ""]
    data["missing_fields"] = missing
    if missing:
        lang = data.get("language") or "English"
        qs = {
            "Hindi": "Kripya missing details batayein: " + ", ".join(missing),
            "Tamil": "Dayavu se missing details sollunga: " + ", ".join(missing),
            "English": "Please provide the missing details: " + ", ".join(missing),
        }
        data["clarifying_question"] = data.get("clarifying_question") or qs.get(lang, qs["English"])
    else:
        data["clarifying_question"] = None
    return data


def _call_validated_json(system: str, user: str, model_cls: type[BaseModel], model: Optional[str] = None) -> dict:
    raw = groq_client.chat_json(system, user, model=model or settings.groq_llm_model)
    try:
        return model_cls.model_validate(raw).model_dump()
    except ValidationError as exc:
        logger.warning("JSON validation failed, retrying once: %s", exc)
        raw2 = groq_client.chat_json(
            system + "\nFix validation errors and return valid JSON only.",
            user + f"\n\nValidation error:\n{exc}\nPrevious JSON:\n{raw}",
            model=model or settings.groq_llm_model,
            use_cache=False,
        )
        return model_cls.model_validate(raw2).model_dump()


def extract_job(transcript: str, today_iso: str) -> dict[str, Any]:
    data = _call_validated_json(
        JOB_SYSTEM,
        f"Today is {today_iso}. Extract the job from this voice note:\n{transcript}",
        JobExtractModel,
    )
    return _finalize_job(data)


def extract_worker(transcript: str, today_iso: str) -> dict[str, Any]:
    data = _call_validated_json(
        WORKER_SYSTEM,
        f"Today is {today_iso}. Extract the worker profile from:\n{transcript}",
        WorkerExtractModel,
    )
    if data.get("skill"):
        data["skill"] = normalize_skill(str(data["skill"]))
    required = ["name", "skill", "area"]
    missing = [f for f in required if not data.get(f)]
    data["missing_fields"] = missing
    data["clarifying_question"] = (
        None if not missing else (data.get("clarifying_question") or "Please share: " + ", ".join(missing))
    )
    return data


def write_alert(
    worker_name: str,
    worker_language: str,
    skill: str,
    date: str,
    location: str,
    wage: int,
    count: int,
) -> str:
    lang = worker_language.split(",")[0].strip() if worker_language else "English"
    if settings.demo_mode or not settings.groq_api_key:
        return _fallback_alert(lang, skill, date, location, wage)
    try:
        data = groq_client.chat_json(
            ALERT_SYSTEM,
            (
                f"Language: {lang}\nWorker name: {worker_name}\n"
                f"Job: {count} {skill} needed on {date} at {location}, ₹{wage}/day."
            ),
            model=settings.groq_fast_model,
        )
        return data.get("message") or _fallback_alert(lang, skill, date, location, wage)
    except Exception:
        return _fallback_alert(lang, skill, date, location, wage)


def _fallback_alert(lang: str, skill: str, date: str, location: str, wage: int) -> str:
    if lang.lower().startswith("tamil"):
        return f"Vanakkam! {location}-il {date} {skill} velai, ₹{wage}/naal. Yes/No reply pannunga."
    if lang.lower().startswith("hindi"):
        return f"Namaste! {location} mein {date} ko {skill} ka kaam hai, ₹{wage}/din. Yes/No reply karein."
    return f"Hi! {skill} job on {date} at {location}, ₹{wage}/day. Reply Yes or No."


def extract_job_offline(transcript: str, today_iso: str) -> dict[str, Any]:
    text = transcript.lower()
    skill = normalize_skill(transcript)
    count = None
    m = re.search(
        r"(\d+)\s*(mason|painter|plumber|electrician|helper|carpenter|mestri|mistri|mazdoor|colour|pipe)",
        text,
    )
    if m:
        count = int(m.group(1))
        skill = skill or normalize_skill(m.group(2))
    else:
        m2 = re.search(r"(\d+)\s*(log|workers?|people|jana|per)", text)
        if m2:
            count = int(m2.group(1))
        elif skill:
            count = 1

    wage = None
    wm = re.search(r"(?:₹|rs\.?|inr)?\s*(\d{3,5})\s*(?:per\s*day|/day|/din|/naal|rupees?)?", text)
    if wm:
        wage = int(wm.group(1))

    location = None
    for place in ["chengalpattu", "chennai", "tambaram", "guindy", "porur", "omr", "ecr", "velachery"]:
        if place in text:
            location = place.title() if place != "omr" else "OMR"
            if place == "ecr":
                location = "ECR"
            break

    today = datetime.strptime(today_iso, "%Y-%m-%d").date()
    date_val = None
    if any(w in text for w in ["kal", "tomorrow", "naalai", "naalai"]):
        date_val = (today + timedelta(days=1)).isoformat()
    elif "parso" in text or "day after" in text:
        date_val = (today + timedelta(days=2)).isoformat()
    elif any(w in text for w in ["aaj", "today", "inniki"]):
        date_val = today.isoformat()
    else:
        dm = re.search(r"(\d{4}-\d{2}-\d{2})", transcript)
        if dm:
            date_val = dm.group(1)

    language = "English"
    if any(w in text for w in ["chahiye", "mein", "kaam", "hai", "kal", "din"]):
        language = "Hindi"
    if any(w in text for w in ["venum", "iruku", "naal", "pannunga", "vanakkam", "sollunga", "நா"]):
        language = "Tamil"

    return _finalize_job(
        {
            "skill": skill,
            "count": count,
            "date": date_val,
            "location": location,
            "wage_per_day": wage,
            "language": language,
        }
    )


def extract_worker_offline(transcript: str, today_iso: str) -> dict[str, Any]:
    text = transcript.lower()
    skill = normalize_skill(transcript)
    name = None
    nm = re.search(r"(?:main|i am|i'm|naam|peru)\s+([A-Za-z\u0900-\u097F\u0B80-\u0BFF]+)", transcript, re.I)
    if nm:
        name = nm.group(1).strip().title()
    else:
        nm2 = re.search(r"^([A-Za-z]+)", transcript.strip())
        if nm2:
            name = nm2.group(1).title()

    years = 1
    ym = re.search(r"(\d+)\s*(?:years?|saal|varusham|yrs?)", text)
    if ym:
        years = int(ym.group(1))

    area = None
    for place in ["chengalpattu", "chennai", "tambaram", "guindy", "porur", "omr", "ecr", "velachery"]:
        if place in text:
            area = place.title()
            break

    wage = 700
    wm = re.search(r"(\d{3,5})", text)
    if wm:
        wage = int(wm.group(1))

    today = datetime.strptime(today_iso, "%Y-%m-%d").date()
    availability = [(today + timedelta(days=i)).isoformat() for i in range(1, 8)]
    languages = "Hindi"
    if any(w in text for w in ["tamil", "tamizh"]):
        languages = "Tamil"
    elif "english" in text:
        languages = "English"

    data = {
        "name": name,
        "skill": skill,
        "experience_years": years,
        "area": area,
        "availability": availability,
        "languages": languages,
        "expected_wage": wage,
        "profile_text": transcript.strip(),
    }
    missing = [f for f in ["name", "skill", "area"] if not data.get(f)]
    data["missing_fields"] = missing
    data["clarifying_question"] = ("Please share: " + ", ".join(missing)) if missing else None
    return data


CANNED_TRANSCRIPTS = {
    "hi": "Kal 3 mason chahiye, Chengalpattu mein, 800 per day",
    "ta": "Naalai 2 mestri venum Chengalpattu la, 850 rupees",
    "en": "Need 3 masons tomorrow in Chengalpattu, 800 per day",
    "auto": "Kal 3 mason chahiye, Chengalpattu mein, 800 per day",
}

CANNED_WORKER_TRANSCRIPTS = {
    "hi": "Main Ravi, 8 saal ka raj mistri, Chengalpattu area, 850 per day, Tamil Hindi bolta hoon",
    "ta": "Naan Ravi, 8 varusham mestri, Chengalpattu, 850 rupees, Tamil Hindi",
    "en": "I am Ravi, 8 years mason in Chengalpattu, 850 per day, Tamil and Hindi",
    "auto": "Main Ravi, 8 saal ka raj mistri, Chengalpattu area, 850 per day, Tamil Hindi bolta hoon",
}


def extract_job_safe(transcript: str, today_iso: str, demo_mode: bool = False) -> dict[str, Any]:
    force_demo = demo_mode or settings.demo_mode or not settings.groq_api_key
    if force_demo:
        return extract_job_offline(transcript, today_iso)
    try:
        return extract_job(transcript, today_iso)
    except Exception as exc:
        logger.warning("Groq extraction failed, using offline: %s", exc)
        return extract_job_offline(transcript, today_iso)


def extract_worker_safe(transcript: str, today_iso: str, demo_mode: bool = False) -> dict[str, Any]:
    force_demo = demo_mode or settings.demo_mode or not settings.groq_api_key
    if force_demo:
        return extract_worker_offline(transcript, today_iso)
    try:
        return extract_worker(transcript, today_iso)
    except Exception as exc:
        logger.warning("Groq worker extract failed, offline: %s", exc)
        return extract_worker_offline(transcript, today_iso)
