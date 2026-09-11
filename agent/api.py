"""Thin HTTP layer over ClaimChecker — serves the demo frontend and the
POST /check endpoint it calls.

Run with: .venv/Scripts/python.exe -m uvicorn agent.api:app --port 8000
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent.claim_checker import ClaimChecker
from query_layer import hotdata_query

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

app = FastAPI(title="Self-Improving Research Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_checker: ClaimChecker | None = None


def get_checker() -> ClaimChecker:
    global _checker
    if _checker is None:
        _checker = ClaimChecker()
    return _checker


class CheckRequest(BaseModel):
    statement: str


@app.post("/api/check")
async def check_claim(req: CheckRequest):
    checker = get_checker()
    result = await checker.check(req.statement)
    return result


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/trends")
async def trends():
    """Live SQL read straight from hotdata.dev — bypasses needing to
    navigate hotdata's own dashboard for the demo. Same client/database the
    checker already writes to (get_checker() lazily creates it on first
    use, same as /api/check)."""
    checker = get_checker()
    topic_summary = hotdata_query.topic_trend_query(checker.hotdata, checker.hotdata_db)
    recent = hotdata_query.recent_claims_query(checker.hotdata, checker.hotdata_db)
    return {
        "database_id": checker.hotdata_db.id,
        "database_description": checker.hotdata_db.description,
        "topic_summary": {"columns": topic_summary.columns, "rows": topic_summary.rows},
        "recent_claims": {"columns": recent.columns, "rows": recent.rows},
    }


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    async def index():
        return FileResponse(str(FRONTEND_DIR / "index.html"))

    @app.get("/feed")
    async def feed():
        return FileResponse(str(FRONTEND_DIR / "feed.html"))

    @app.get("/trends")
    async def trends_page():
        return FileResponse(str(FRONTEND_DIR / "trends.html"))
