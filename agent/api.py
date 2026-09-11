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


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    async def index():
        return FileResponse(str(FRONTEND_DIR / "index.html"))
