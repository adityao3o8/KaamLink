import json
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.config import BASE_DIR

router = APIRouter(prefix="/api/eval", tags=["eval"])

EVAL_DIR = BASE_DIR.parent / "eval"
RESULTS = EVAL_DIR / "results.json"
_running = {"busy": False}


@router.get("/results")
def get_results():
    if not RESULTS.exists():
        return {"status": "empty", "results": None}
    return {"status": "ok", "results": json.loads(RESULTS.read_text(encoding="utf-8"))}


def _run_eval_job():
    _running["busy"] = True
    try:
        py = sys.executable
        script = EVAL_DIR / "run_eval.py"
        subprocess.run([py, str(script)], cwd=str(EVAL_DIR.parent), check=False, timeout=600)
    finally:
        _running["busy"] = False


@router.post("/run")
def run_eval(background_tasks: BackgroundTasks):
    if _running["busy"]:
        raise HTTPException(409, "Evaluation already running")
    if not (EVAL_DIR / "run_eval.py").exists():
        raise HTTPException(500, "eval/run_eval.py missing")
    background_tasks.add_task(_run_eval_job)
    return {"status": "started", "message": "Evaluation started. Refresh results in a minute."}


@router.get("/status")
def eval_status():
    return {"busy": _running["busy"], "has_results": RESULTS.exists()}
