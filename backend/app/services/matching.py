from typing import Any

from app.models import Worker
from app.services.embeddings import cosine_similarity, embed_query


def job_profile_text(job: dict[str, Any]) -> str:
    return (
        f"{job.get('skill')} needed in {job.get('location')} "
        f"wage {job.get('wage_per_day')} date {job.get('date')} "
        f"language {job.get('language')}"
    )


def wage_fit(worker_wage: int, job_wage: int | None) -> float:
    if not job_wage or not worker_wage:
        return 0.5
    if worker_wage <= job_wage:
        return 1.0
    # soft penalty for asking more than offered
    over = (worker_wage - job_wage) / max(job_wage, 1)
    return max(0.0, 1.0 - over)


def area_match(worker_area: str, job_location: str | None) -> float:
    if not job_location:
        return 0.5
    wa = (worker_area or "").lower().strip()
    jl = (job_location or "").lower().strip()
    if wa == jl:
        return 1.0
    if wa in jl or jl in wa:
        return 0.85
    # same metro region heuristic
    chennai_side = {"chennai", "tambaram", "guindy", "porur", "omr", "ecr", "velachery", "chengalpattu"}
    if any(x in wa for x in chennai_side) and any(x in jl for x in chennai_side):
        return 0.7
    return 0.2


def score_worker(worker: Worker, job: dict[str, Any], job_embedding: list[float]) -> dict[str, float]:
    emb = cosine_similarity(job_embedding, worker.embedding_vector())
    # clamp to 0..1
    emb = max(0.0, min(1.0, (emb + 1) / 2 if emb < 0 else emb))
    reliability = max(0.0, min(1.0, (worker.reliability or 0) / 5.0))
    wage = wage_fit(worker.expected_wage or 0, job.get("wage_per_day"))
    area = area_match(worker.area or "", job.get("location"))
    total = 0.5 * emb + 0.25 * reliability + 0.15 * wage + 0.10 * area
    return {
        "embedding": round(emb, 4),
        "reliability": round(reliability, 4),
        "wage_fit": round(wage, 4),
        "area_match": round(area, 4),
        "total": round(total, 4),
    }


def match_workers(workers: list[Worker], job: dict[str, Any], top_k: int = 10) -> list[tuple[Worker, dict[str, float]]]:
    skill = (job.get("skill") or "").lower()
    date = job.get("date")
    filtered = []
    for w in workers:
        if (w.skill or "").lower() != skill:
            continue
        avail = w.availability_list()
        if date and avail and date not in avail:
            continue
        filtered.append(w)

    job_emb = embed_query(job_profile_text(job))
    scored = [(w, score_worker(w, job, job_emb)) for w in filtered]
    scored.sort(key=lambda x: x[1]["total"], reverse=True)
    return scored[:top_k]


def mask_phone(phone: str) -> str:
    phone = phone or ""
    if len(phone) < 4:
        return "****"
    return phone[:2] + "******" + phone[-2:]
