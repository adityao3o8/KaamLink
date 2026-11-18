import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import SessionLocal, init_db
from app.models import HistoricalJob, Worker
from app.routers import (
    alerts,
    analytics,
    eval_api,
    jobs,
    matching,
    metrics,
    rag,
    ratings,
    tts,
    wage,
    whatsapp,
    workers,
)
from app.services import groq_client
from app.services.rag import ingest_kb

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kaamlink")

app = FastAPI(title="KaamLink", version="2.0.0", description="Groq Whisper + Llama labour matching")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router)
app.include_router(workers.router)
app.include_router(matching.router)
app.include_router(alerts.router)
app.include_router(ratings.router)
app.include_router(metrics.router)
app.include_router(wage.router)
app.include_router(tts.router)
app.include_router(rag.router)
app.include_router(eval_api.router)
app.include_router(analytics.router)
app.include_router(whatsapp.router)

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def _seed_if_empty():
    if not settings.auto_seed:
        return
    db = SessionLocal()
    try:
        if db.query(Worker).count() == 0:
            logger.info("No workers found — running seed.py")
            from seed import seed

            seed(reset=False)
        if db.query(HistoricalJob).count() < 50:
            from seed import seed_historical

            seed_historical(db, n=200)
            db.commit()
    except Exception as exc:
        logger.warning("Auto-seed failed: %s", exc)
    finally:
        db.close()


@app.on_event("startup")
def on_startup():
    init_db()
    groq_client.list_available_models()
    try:
        ingest_kb(force=False)
    except Exception as exc:
        logger.warning("KB ingest: %s", exc)
    _seed_if_empty()


@app.get("/health")
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "app": "KaamLink",
        "provider": "Groq (Whisper + Llama)",
        "llm_model": settings.groq_llm_model,
        "stt_model": settings.groq_stt_model,
        "twilio": settings.enable_twilio,
        "demo_mode": settings.demo_mode,
    }


if FRONTEND_DIST.exists():
    assets = FRONTEND_DIST / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        # don't swallow API
        if full_path.startswith("api") or full_path.startswith("whatsapp"):
            return {"detail": "Not Found"}
        index = FRONTEND_DIST / "index.html"
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)
