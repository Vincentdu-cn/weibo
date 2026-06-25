"""CompetitionManager — central authority for competition lifecycle + comment count.

Enforces the 500-comment hard limit and coordinates with MonitorOrchestrator
(which may be None in tests or when monitoring is not yet available).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from app.models import CompetitionSession
from app.services.comment_fetcher import CommentFetcher


class CompetitionManager:
    """Manage competition sessions and enforce the 500-comment limit."""

    _COMMENT_LIMIT = 500

    # ── Lifecycle ────────────────────────────────────────────────────────

    def __init__(
        self,
        db_session: Any = None,
        monitor_orchestrator: Any = None,
    ) -> None:
        self.db_session = db_session
        self.monitor_orchestrator = monitor_orchestrator
        self.session_id: Optional[int] = None

    # ── Public API ───────────────────────────────────────────────────────

    async def start_competition(
        self,
        weibo_url: str,
        team_uids: list[str] | None = None,
    ) -> dict:
        """Create a new CompetitionSession and optionally start monitoring.

        Returns:
            ``{"status": "running", "session_id": int}``
        """
        if self.db_session is None:
            raise RuntimeError("db_session is required to start a competition")

        mid = self._url_to_mid(weibo_url)
        session = CompetitionSession(
            target_weibo_url=weibo_url,
            target_weibo_mid=mid,
            started_at=datetime.utcnow(),
            total_comments=0,
            status="running",
        )
        self.db_session.add(session)
        self.db_session.commit()
        self.db_session.refresh(session)
        self.session_id = session.id

        if self.monitor_orchestrator is not None:
            await self.monitor_orchestrator.start_monitoring(weibo_url)

        return {"status": "running", "session_id": session.id}

    async def pause_competition(self) -> dict:
        """Pause the active competition session."""
        session = self._get_active_session()
        session.status = "paused"
        self.db_session.commit()

        if self.monitor_orchestrator is not None:
            await self.monitor_orchestrator.stop_monitoring()

        return {"status": "paused"}

    async def resume_competition(self) -> dict:
        """Resume a paused competition session."""
        session = self._get_active_session()
        session.status = "running"
        self.db_session.commit()

        if self.monitor_orchestrator is not None:
            await self.monitor_orchestrator.start_monitoring(session.target_weibo_url)

        return {"status": "running"}

    async def end_competition(self) -> dict:
        """End the active competition session."""
        session = self._get_active_session()
        session.status = "ended"
        session.ended_at = datetime.utcnow()
        self.db_session.commit()

        if self.monitor_orchestrator is not None:
            await self.monitor_orchestrator.stop_monitoring()

        return {"status": "ended", "total_comments": session.total_comments}

    async def get_status(self) -> dict:
        """Return the current session status.

        Returns ``{"status": "idle"}`` when no session is active.
        """
        session = self._get_session()
        if session is None:
            return {"status": "idle"}

        return {
            "status": session.status,
            "session_id": session.id,
            "total_comments": session.total_comments,
            "remaining_quota": self._COMMENT_LIMIT - session.total_comments,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "target_weibo_url": session.target_weibo_url,
        }

    async def increment_comment_count(self) -> bool:
        """Increment total_comments by 1.

        Returns:
            True if the increment succeeded.
            False if the increment would exceed the 500-comment limit,
            or if there is no active session.
        """
        session = self._get_session()
        if session is None:
            return False
        if session.total_comments >= self._COMMENT_LIMIT:
            return False

        session.total_comments += 1
        self.db_session.commit()
        return True

    async def get_remaining_quota(self) -> int:
        """Return the number of comments remaining in the quota."""
        session = self._get_session()
        if session is None:
            return 0
        return self._COMMENT_LIMIT - session.total_comments

    async def can_post_comment(self) -> bool:
        """Return True if more comments can be posted."""
        session = self._get_session()
        if session is None:
            return False
        return session.total_comments < self._COMMENT_LIMIT

    # ── Internal helpers ─────────────────────────────────────────────────

    def _get_session(self) -> CompetitionSession | None:
        """Return the current session by session_id, or None."""
        if self.session_id is None or self.db_session is None:
            return None
        return (
            self.db_session.query(CompetitionSession)
            .filter(CompetitionSession.id == self.session_id)
            .first()
        )

    def _get_active_session(self) -> CompetitionSession:
        """Return the current session or raise if there is none."""
        session = self._get_session()
        if session is None:
            raise RuntimeError("No active competition session")
        return session

    @staticmethod
    def _url_to_mid(url: str) -> str:
        """Convert a Weibo URL to a numeric mid string.

        Delegates to CommentFetcher's proven base62 conversion logic.
        """
        fetcher = CommentFetcher.__new__(CommentFetcher)
        return fetcher.get_weibo_mid(url)
