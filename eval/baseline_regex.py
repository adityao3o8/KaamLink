"""Rule-based job request extractor for KaamLink eval baseline."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Optional

SKILLS = frozenset({"mason", "painter", "plumber", "electrician", "helper", "carpenter"})

SKILL_PATTERNS: list[tuple[str, str]] = [
    (r"\b(raj\s*mistri|raj\s*mestri|mestri|mistri|masons?)\b", "mason"),
    (r"\b(colou?r\s*wala|painters?|paint)\b", "painter"),
    (r"\b(pipe\s*wala|plumbers?|plumbing)\b", "plumber"),
    (r"\b(wiremen|wireman|wire\s*wala|electricians?|electric)\b", "electrician"),
    (r"\b(mazdoor|helpers?|labou?r|coolie)\b", "helper"),
    (r"\b(wood\s*wala|carpenters?|carpentry)\b", "carpenter"),
]

LOCATIONS: list[tuple[str, str]] = [
    ("chengalpattu", "Chengalpattu"),
    ("chennai", "Chennai"),
    ("tambaram", "Tambaram"),
    ("guindy", "Guindy"),
    ("porur", "Porur"),
    ("omr", "OMR"),
    ("ecr", "ECR"),
    ("velachery", "Velachery"),
]

TAMIL_SCRIPT_SKILL: list[tuple[str, str]] = [
    ("மேஸ்திரி", "mason"),
    ("மேஸ்திரிகள்", "mason"),
    ("எலக்ட்ரீஷியன்", "electrician"),
    ("பெயின்டர்", "painter"),
    ("பிளம்பர்", "plumber"),
    ("திண்ணர்", "helper"),
    ("மரத்தொழில்", "carpenter"),
]


def _detect_skill(text: str) -> Optional[str]:
    lower = text.lower()
    for pattern, skill in SKILL_PATTERNS:
        if re.search(pattern, lower, re.I):
            return skill
    for hint, skill in TAMIL_SCRIPT_SKILL:
        if hint in text:
            return skill
    for skill in SKILLS:
        if re.search(rf"\b{skill}\b", lower):
            return skill
    return None


def _detect_count(text: str, skill: Optional[str]) -> Optional[int]:
    lower = text.lower()
    tokens = (
        r"masons?|painter|painters?|plumber|plumbers?|electrician|electricians?|"
        r"helper|helpers?|carpenter|carpenters?|"
        r"mestri|mistri|mazdoor|pipe\s*wala|colour\s*wala|colou?r\s*wala|"
        r"wireman|wiremen|wood\s*wala|raj\s*mistri|workers?|people|log|jana|"
        r"மேஸ்திரி|மேஸ்திரிகள்|பெயின்டர்|எலக்ட்ரீஷியன்|திண்ணர்"
    )

    def _valid_headcount(n: int) -> bool:
        return 1 <= n <= 50

    m = re.search(rf"\b(\d+)\s*({tokens})", lower)
    if m and _valid_headcount(int(m.group(1))):
        return int(m.group(1))
    for chunk in re.finditer(rf"({tokens})", text, re.I):
        tail = text[chunk.end() : chunk.end() + 24]
        m_tail = re.search(r"\D*(\d+)\b", tail)
        if m_tail and _valid_headcount(int(m_tail.group(1))):
            return int(m_tail.group(1))
        head = text[max(0, chunk.start() - 12) : chunk.start()]
        m_head = re.search(r"(\d+)\s*$", head)
        if m_head and _valid_headcount(int(m_head.group(1))):
            return int(m_head.group(1))
    m2 = re.search(r"\b(\d+)\s*(?:no\.?|nos\.?|number of)\b", lower)
    if m2 and _valid_headcount(int(m2.group(1))):
        return int(m2.group(1))
    for pat in (
        r"(?:need(?:ed)?|chahiye|venum|வேணும்)\s*(\d+)",
        r"(?:need(?:ed)?|chahiye|venum|வேணும்).{0,20}?(\d+)\b",
    ):
        m3 = re.search(pat, lower if "வே" not in pat else text)
        if m3 and _valid_headcount(int(m3.group(1))):
            return int(m3.group(1))
    m4 = re.search(r"^(\d+)\s", text.strip())
    if m4 and _valid_headcount(int(m4.group(1))):
        return int(m4.group(1))
    mx = re.search(r"\bx\s*(\d+)\b", lower)
    if mx and _valid_headcount(int(mx.group(1))):
        return int(mx.group(1))
    if skill:
        return 1
    return None


def _detect_wage(text: str) -> Optional[int]:
    lower = text.lower()
    patterns = [
        r"(?:₹|rs\.?|inr|rupees?)\s*(\d{3,5})",
        r"(\d{3,5})\s*(?:per\s*day|/day|/din|/naal|rupees?|rs)",
        r"(?:wage|salary|pay)\s*(?:is\s*)?(\d{3,5})",
        r"\b(\d{3,5})\s*$",
    ]
    for pat in patterns:
        m = re.search(pat, lower)
        if m:
            val = int(m.group(1))
            if 300 <= val <= 5000:
                return val
    return None


def _detect_location(text: str) -> Optional[str]:
    lower = text.lower()
    for key, canonical in LOCATIONS:
        if key in lower:
            return canonical
    return None


def _detect_date(text: str, today_iso: str) -> Optional[str]:
    lower = text.lower()
    today = datetime.strptime(today_iso, "%Y-%m-%d").date()
    if any(w in lower for w in ["parso", "day after tomorrow", "day after"]) or "நாளைக்கு அப்புறம்" in text:
        return (today + timedelta(days=2)).isoformat()
    if (
        re.search(r"\bkal\b", lower)
        or any(w in lower for w in ["tomorrow", "naalai", "naale", "repu"])
        or "நாளை" in text
    ):
        return (today + timedelta(days=1)).isoformat()
    if any(w in lower for w in ["aaj", "today", "inniki", "inniku", "inru"]) or "இன்று" in text:
        return today.isoformat()
    dm = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if dm:
        return dm.group(1)
    return None


def _detect_language(text: str) -> str:
    lower = text.lower()
    if re.search(r"[\u0B80-\u0BFF]", text):
        return "Tamil"
    if any(w in lower for w in ["chahiye", "mein", "kaam", "kal ", "din", "rupee", "hai"]):
        return "Hindi"
    if any(w in lower for w in ["venum", "la ", "pannunga", "iruku", "naalai", "sollunga"]):
        return "Tamil"
    return "English"


def extract_job_regex(text: str, today_iso: str) -> dict[str, Any]:
    skill = _detect_skill(text)
    count = _detect_count(text, skill)
    return {
        "skill": skill,
        "count": count,
        "date": _detect_date(text, today_iso),
        "location": _detect_location(text),
        "wage_per_day": _detect_wage(text),
        "language": _detect_language(text),
    }