"""FastAPI routes for competition lifecycle management.

Endpoints:
  POST /api/competition/start   — start a new competition
  POST /api/competition/pause   — pause the active competition
  POST /api/competition/resume  — resume a paused competition
  POST /api/competition/end     — end the active competition
  GET  /api/competition/status  — get current competition status
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.database import SessionLocal
from app.services.competition_manager import CompetitionManager

router = APIRouter(prefix="/api/competition", tags=["competition"])


# ── Request / response models ────────────────────────────────────────────────


class StartRequest(BaseModel):
    weibo_url: str
    team_uids: list[str] | None = None


# ── Module-level singleton ──────────────────────────────────────────────────
# Uses a lazy DB session — created per-request from SessionLocal.
# MonitorOrchestrator is optional and wired later (T15 integration).

_manager: CompetitionManager | None = None


def _get_manager() -> CompetitionManager:
    """Return (or lazily create) the module-level CompetitionManager."""
    global _manager
    if _manager is None:
        _manager = CompetitionManager(db_session=SessionLocal())
    return _manager


def reset_manager() -> None:
    """Reset the singleton — used in tests."""
    global _manager
    _manager = None


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.post("/start")
async def start_competition(body: StartRequest) -> dict:
    """Start a new competition session."""
    manager = _get_manager()
    try:
        return await manager.start_competition(body.weibo_url, body.team_uids)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/pause")
async def pause_competition() -> dict:
    """Pause the active competition."""
    manager = _get_manager()
    try:
        return await manager.pause_competition()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/resume")
async def resume_competition() -> dict:
    """Resume a paused competition."""
    manager = _get_manager()
    try:
        return await manager.resume_competition()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/end")
async def end_competition() -> dict:
    """End the active competition."""
    manager = _get_manager()
    try:
        return await manager.end_competition()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/status")
async def get_competition_status() -> dict:
    """Get the current competition status."""
    manager = _get_manager()
    return await manager.get_status()
