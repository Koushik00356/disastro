"""REST API and dashboard server for Disastro.

Run with:  python main.py serve     (or: uvicorn backend.api:app)
"""

import threading
from collections import Counter

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

import config
from utils.helpers import load_json, now_iso


app = FastAPI(title="Disastro", description="Live disaster monitoring with RAG")


pipeline_state = {"running": False, "last_run": None, "last_ok": None}
pipeline_lock = threading.Lock()


class Question(BaseModel):
    question: str
    disaster_type: str | None = None
    severity: str | None = None


def load_events():

    return load_json(config.CLEANED_FILE)


def run_pipeline_job():

    from pipeline import run_pipeline

    try:
        pipeline_state["last_ok"] = run_pipeline()
    finally:
        pipeline_state["last_run"] = now_iso()
        pipeline_state["running"] = False


@app.get("/")
def dashboard():

    return FileResponse(config.FRONTEND_DIR / "index.html")


@app.get("/api/events")
def list_events(
    disaster_type: str | None = None,
    severity: str | None = None,
    source_type: str | None = None,
    limit: int = Query(200, ge=1, le=1000),
):

    events = load_events()

    for field, value in (
        ("disaster_type", disaster_type),
        ("severity", severity),
        ("source_type", source_type),
    ):
        if value:
            events = [event for event in events if event.get(field) == value]

    return {"count": len(events), "events": events[:limit]}


@app.get("/api/stats")
def stats():

    events = load_events()

    return {
        "total": len(events),
        "by_severity": Counter(event.get("severity") or "unclassified" for event in events),
        "by_type": Counter(event["disaster_type"] for event in events),
        "by_source_type": Counter(event["source_type"] for event in events),
        "latest": events[0]["published_at"] if events else None,
        "pipeline": pipeline_state,
    }


@app.get("/api/search")
def semantic_search(
    q: str = Query(..., min_length=2),
    n: int = Query(5, ge=1, le=25),
    disaster_type: str | None = None,
    severity: str | None = None,
):

    from vectordb.search import search

    return {"query": q, "results": search(q, n_results=n, disaster_type=disaster_type, severity=severity)}


@app.post("/api/ask")
def ask(body: Question):

    from rag.rag_pipeline import answer_question

    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question is empty.")

    return answer_question(
        body.question.strip(),
        disaster_type=body.disaster_type,
        severity=body.severity,
    )


@app.get("/api/report")
def latest_report():

    return load_json(config.REPORT_FILE, default={})


@app.get("/api/alerts")
def list_alerts(limit: int = Query(50, ge=1, le=500)):

    alerts = load_json(config.ALERTS_FILE)

    return {"count": len(alerts), "alerts": alerts[:limit]}


@app.post("/api/refresh")
def refresh():
    """Start a pipeline run in the background (one at a time)."""

    with pipeline_lock:

        if pipeline_state["running"]:
            return {"started": False, "detail": "Pipeline is already running."}

        pipeline_state["running"] = True

    threading.Thread(target=run_pipeline_job, daemon=True).start()

    return {"started": True}
