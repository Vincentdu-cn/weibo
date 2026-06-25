"""FastAPI routes for replay/review of past competition sessions.

Endpoints:
  GET /api/replay/sessions                    — list all sessions
  GET /api/replay/{session_id}/timeline       — timeline data for a session
  GET /api/replay/{session_id}/alerts         — alert history for a session
  GET /api/replay/{session_id}/actions        — action history for a session
  GET /api/replay/{session_id}/summary        — summary report for a session
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.database import SessionLocal
from app.services.replay_service import ReplayService

router = APIRouter(prefix="/api/replay", tags=["replay"])


# ── Module-level singleton ──────────────────────────────────────────────────


_service: ReplayService | None = None


def _get_service() -> ReplayService:
    """Return (or lazily create) the module-level ReplayService."""
    global _service
    if _service is None:
        _service = ReplayService(db_session=SessionLocal())
    return _service


def reset_service() -> None:
    """Reset the singleton — used in tests."""
    global _service
    _service = None


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.get("/sessions")
async def get_sessions() -> dict:
    """List all competition sessions available for replay."""
    service = _get_service()
    sessions = await service.get_sessions()
    return {"sessions": sessions}


@router.get("/{session_id}/timeline")
async def get_session_timeline(session_id: int) -> dict:
    """Get the timeline of comment snapshots for a session."""
    service = _get_service()
    return await service.get_session_timeline(session_id)


@router.get("/{session_id}/alerts")
async def get_session_alerts(session_id: int) -> dict:
    """Get all alerts for a session."""
    service = _get_service()
    return await service.get_session_alerts(session_id)


@router.get("/{session_id}/actions")
async def get_session_actions(session_id: int) -> dict:
    """Get all action logs within a session's time range."""
    service = _get_service()
    return await service.get_session_actions(session_id)


@router.get("/{session_id}/summary")
async def get_session_summary(session_id: int) -> dict:
    """Get aggregated summary metrics for a session."""
    service = _get_service()
    return await service.get_session_summary(session_id)
