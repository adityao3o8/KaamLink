#!/usr/bin/env python3
"""Compare regex baseline vs LLM job extraction on labelled eval set."""
from __future__ import annotations

import json
import logging
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from tqdm import tqdm

EVAL_DIR = Path(__file__).resolve().parent
BACKEND_DIR = EVAL_DIR.parent / "backend"
sys.path.insert(0, str(EVAL_DIR))
sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings  # noqa: E402
from app.services.llm import extract_job_safe  # noqa: E402

from baseline_regex import extract_job_regex  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("kaamlink.eval")

FIELDS = ("skill", "count", "date", "location", "wage_per_day")


def load_dataset(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list) or len(data) != 50:
        raise ValueError(f"dataset must be a list of 50 items, got {type(data)} len={len(data)}")
    return data


def resolve_expected_date(date_relative: str | None, today_iso: str) -> str | None:
    if date_relative is None:
        return None
    today = datetime.strptime(today_iso, "%Y-%m-%d").date()
    mapping = {
        "today": today,
        "tomorrow": today + timedelta(days=1),
        "day_after": today + timedelta(days=2),
    }
    if date_relative not in mapping:
        raise ValueError(f"unknown date_relative: {date_relative}")
    return mapping[date_relative].isoformat()


def normalize_skill(value) -> str | None:
    if value is None:
        return None
    s = str(value).lower().strip()
    return s or None


def location_match(expected: str | None, predicted: str | None) -> bool:
    if expected is None and (predicted is None or predicted == ""):
        return True
    if expected is None or predicted is None:
        return False
    e = expected.lower().strip()
    p = predicted.lower().strip()
    return e in p or p in e


def field_correct(field: str, expected: dict, predicted: dict, today_iso: str) -> bool:
    if field == "skill":
        return normalize_skill(predicted.get("skill")) == normalize_skill(expected.get("skill"))
    if field == "count":
        return predicted.get("count") == expected.get("count")
    if field == "wage_per_day":
        return predicted.get("wage_per_day") == expected.get("wage_per_day")
    if field == "date":
        exp_iso = resolve_expected_date(expected.get("date_relative"), today_iso)
        pred = predicted.get("date")
        if exp_iso is None:
            return pred is None or pred == ""
        return pred == exp_iso
    if field == "location":
        return location_match(expected.get("location"), predicted.get("location"))
    raise ValueError(field)


def exact_match(expected: dict, predicted: dict, today_iso: str) -> bool:
    return all(field_correct(f, expected, predicted, today_iso) for f in FIELDS)


def summarize(rows: list[dict], key: str) -> dict:
    n = len(rows)
    per_field = {f: sum(1 for r in rows if r[f"{key}_{f}"]) / n for f in FIELDS}
    exact = sum(1 for r in rows if r[f"{key}_exact"]) / n
    latencies = [r[f"{key}_latency_ms"] for r in rows]
    avg_lat = sum(latencies) / n if latencies else 0.0
    return {
        "per_field": {k: round(v, 4) for k, v in per_field.items()},
        "exact_match": round(exact, 4),
        "avg_latency_ms": round(avg_lat, 2),
    }


def main() -> None:
    today_iso = date.today().isoformat()
    dataset_path = EVAL_DIR / "dataset.json"
    items = load_dataset(dataset_path)

    logger.info("GROQ_LLM_MODEL=%s", settings.groq_llm_model)
    logger.info("Evaluating %d examples (today=%s)", len(items), today_iso)

    details: list[dict] = []

    for item in tqdm(items, desc="regex"):
        text = item["text"]
        expected = item["expected"]
        t0 = time.perf_counter()
        pred = extract_job_regex(text, today_iso)
        regex_ms = (time.perf_counter() - t0) * 1000
        row = {
            "id": item["id"],
            "text": text,
            "expected": expected,
            "regex_pred": pred,
            "regex_latency_ms": round(regex_ms, 2),
        }
        for f in FIELDS:
            row[f"regex_{f}"] = field_correct(f, expected, pred, today_iso)
        row["regex_exact"] = exact_match(expected, pred, today_iso)
        details.append(row)

    for row in tqdm(details, desc="llm"):
        text = row["text"]
        expected = row["expected"]
        t0 = time.perf_counter()
        pred = extract_job_safe(text, today_iso, demo_mode=False)
        llm_ms = (time.perf_counter() - t0) * 1000
        time.sleep(0.3)
        llm_pred = {
            "skill": pred.get("skill"),
            "count": pred.get("count"),
            "date": pred.get("date"),
            "location": pred.get("location"),
            "wage_per_day": pred.get("wage_per_day"),
            "language": pred.get("language"),
        }
        row["llm_pred"] = llm_pred
        row["llm_latency_ms"] = round(llm_ms, 2)
        for f in FIELDS:
            row[f"llm_{f}"] = field_correct(f, expected, llm_pred, today_iso)
        row["llm_exact"] = exact_match(expected, llm_pred, today_iso)

    results = {
        "model": settings.groq_llm_model,
        "n": len(items),
        "regex": summarize(details, "regex"),
        "llm": summarize(details, "llm"),
        "details": details,
    }

    out_path = EVAL_DIR / "results.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    logger.info("Wrote %s", out_path)
    logger.info("Regex exact match: %.2f%%", results["regex"]["exact_match"] * 100)
    logger.info("LLM exact match: %.2f%%", results["llm"]["exact_match"] * 100)


if __name__ == "__main__":
    main()