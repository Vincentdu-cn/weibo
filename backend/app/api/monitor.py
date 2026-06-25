"""FastAPI routes for monitor control, alert execution, and stats.

Endpoints:
    POST /api/monitor/start           — start the monitoring loop
    POST /api/monitor/stop            — stop the monitoring loop
    POST /api/alerts/{alert_id}/execute — execute a semi-automatic alert action
    GET  /api/alerts/pending          — list pending alerts
    GET  /api/stats                   — dashboard statistics

The orchestrator instance is stored as a module-level singleton
(``_orchestrator``).  In production, it is lazily initialised with all
Wave 1-2 service dependencies.  In tests, the singleton can be replaced
with a mock instance.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.monitor_orchestrator import MonitorOrchestrator

router = APIRouter(tags=["monitor"])

# Module-level singleton — lazily initialised or set by tests.
_orchestrator: Optional[MonitorOrchestrator] = None


def get_orchestrator() -> MonitorOrchestrator:
    """Return the module-level orchestrator singleton.

    Lazily creates a default instance with all Wave 1-2 services when
    called for the first time and no instance has been set.
    """
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = _create_default_orchestrator()
    return _orchestrator


def set_orchestrator(orch: MonitorOrchestrator) -> None:
    """Replace the module-level orchestrator (for testing)."""
    global _orchestrator
    _orchestrator = orch


def _create_default_orchestrator() -> MonitorOrchestrator:
    """Create a MonitorOrchestrator with default Wave 1-2 service instances."""
    from app.services.action_executor import ActionExecutor
    from app.services.alert_engine import AlertEngine
    from app.services.anti_detection import AntiDetectionEngine
    from app.services.comment_fetcher import CommentFetcher
    from app.services.hot_analyzer import HotCommentAnalyzer
    from app.services.member_tracker import TeamMemberTracker
    from app.services.weibo_client import WeiboHttpClient
    from app.services.ws_manager import WebSocketConnectionManager
    from app.api.ws import ws_manager

    client = WeiboHttpClient()
    anti_detection = AntiDetectionEngine()
    fetcher = CommentFetcher(client, anti_detection)
    analyzer = HotCommentAnalyzer()
    tracker = TeamMemberTracker()
    alert_engine = AlertEngine(ws_manager=ws_manager)
    action_executor = ActionExecutor(client, anti_detection)

    return MonitorOrchestrator(
        client=client,
        anti_detection=anti_detection,
        fetcher=fetcher,
        analyzer=analyzer,
        tracker=tracker,
        alert_engine=alert_engine,
        action_executor=action_executor,
        ws_manager=ws_manager,
    )


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class StartMonitorRequest(BaseModel):
    """Request body for ``POST /api/monitor/start``."""

    weibo_url: str
    interval: int = 15


class ExecuteAlertRequest(BaseModel):
    """Request body for ``POST /api/alerts/{alert_id}/execute``."""

    comment: str
    account_ids: list[int]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/api/monitor/start")
async def start_monitor(req: StartMonitorRequest) -> dict:
    """Start the monitoring loop for a Weibo post.

    Returns ``{"status": "running"}``.
    """
    orch = get_orchestrator()
    await orch.start_monitoring(req.weibo_url, interval=req.interval)
    return {"status": "running"}


@router.post("/api/monitor/stop")
async def stop_monitor() -> dict:
    """Stop the monitoring loop.

    Returns ``{"status": "stopped"}``.
    """
    orch = get_orchestrator()
    await orch.stop_monitoring()
    return {"status": "stopped"}


@router.post("/api/alerts/{alert_id}/execute")
async def execute_alert(
    alert_id: int,
    req: ExecuteAlertRequest,
) -> dict:
    """Execute a semi-automatic alert action (like + comment).

    Returns the result summary dict from the orchestrator.
    """
    orch = get_orchestrator()
    return await orch.execute_alert_action(
        alert_id=alert_id,
        comment_content=req.comment,
        selected_account_ids=req.account_ids,
    )


@router.get("/api/alerts/pending")
async def get_pending_alerts() -> list[dict[str, Any]]:
    """Return all pending alerts as a list of dicts."""
    orch = get_orchestrator()
    alerts = orch.alert_engine.get_pending_alerts()
    return [
        {
            "id": a.id,
            "account_uid": a.account_uid,
            "comment_id": a.comment_id,
            "alert_type": a.alert_type,
            "message": a.message,
            "status": a.status,
        }
        for a in alerts
    ]


@router.get("/api/stats")
async def get_stats() -> dict[str, Any]:
    """Return dashboard statistics."""
    orch = get_orchestrator()
    return orch.get_stats()
