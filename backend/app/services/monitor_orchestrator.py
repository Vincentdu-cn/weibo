"""Monitor orchestrator — connects all services into a monitoring loop.

Provides :class:`MonitorOrchestrator` which:
- Runs a periodic monitoring loop that fetches comments, analyzes hot status,
  tracks team members, and broadcasts real-time WebSocket updates.
- Provides dashboard statistics.

Design notes
------------
- The monitoring loop runs as a background ``asyncio.Task`` created by
  :meth:`start_monitoring` and cancelled by :meth:`stop_monitoring`.
- All services are injected — the orchestrator does not import or
  construct them directly, making it fully testable with mocks.
- WebSocket broadcasts use ``ws_manager.broadcast(message_type, data)``.
- DB access is optional — when ``db_session`` is ``None``, DB-dependent
  operations gracefully degrade.
- ``model_dump(mode="json")`` is used for all serialization to avoid
  ``datetime`` serialization errors with ``websocket.send_json``.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.services.anti_detection import AntiDetectionEngine
from app.services.comment_fetcher import CommentFetcher
from app.services.hot_analyzer import HotCommentAnalyzer
from app.services.member_tracker import TeamMemberTracker
from app.services.weibo_client import WeiboHttpClient
from app.services.ws_manager import WebSocketConnectionManager

logger = logging.getLogger(__name__)

# Maximum comments per competition session (enforced elsewhere, used for stats).
_COMMENT_LIMIT = 500

# Number of top comments to include in the hot_comments_update broadcast.
_TOP_N_BROADCAST = 20

# Number of comment pages to fetch per monitoring iteration (10 pages × ~20 = ~200 comments).
_MONITOR_MAX_PAGES = 10


class MonitorOrchestrator:
    """Orchestrates the real-time monitoring loop.

    Parameters
    ----------
    client
        :class:`WeiboHttpClient` for HTTP requests to Weibo.
    anti_detection
        :class:`AntiDetectionEngine` for rate limiting / delays.
    fetcher
        :class:`CommentFetcher` for paginated comment retrieval.
    analyzer
        :class:`HotCommentAnalyzer` for ranking and change detection.
    tracker
        :class:`TeamMemberTracker` for team member grid data.
    action_executor
        :class:`ActionExecutor` for like/comment actions (unused in monitoring
        loop but kept for potential manual actions).
    ws_manager
        :class:`WebSocketConnectionManager` for real-time broadcasts.
    db_session
        Optional SQLAlchemy session for persistence and queries.
    """

    def __init__(
        self,
        client: WeiboHttpClient,
        anti_detection: AntiDetectionEngine,
        fetcher: CommentFetcher,
        analyzer: HotCommentAnalyzer,
        tracker: TeamMemberTracker,
        action_executor: Any = None,
        ws_manager: WebSocketConnectionManager = None,
        db_session: Any = None,
    ) -> None:
        self.client = client
        self.anti_detection = anti_detection
        self.fetcher = fetcher
        self.analyzer = analyzer
        self.tracker = tracker
        self.action_executor = action_executor
        self.ws_manager = ws_manager
        self.db_session = db_session

        # Monitoring state.
        self._running: bool = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._weibo_url: Optional[str] = None
        self._prev_status: list[dict] = []
        self._start_time: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Monitoring lifecycle
    # ------------------------------------------------------------------

    async def start_monitoring(
        self,
        weibo_url: str,
        interval: int = 15,
    ) -> None:
        """Start the background monitoring loop.

        Parameters
        ----------
        weibo_url
            The target Weibo post URL to monitor.
        interval
            Seconds between monitoring iterations.  Default 15.
        """
        self._running = True
        self._weibo_url = weibo_url
        self._start_time = datetime.now(timezone.utc)
        self._monitor_task = asyncio.create_task(
            self._monitor_loop(weibo_url, interval)
        )

    async def stop_monitoring(self) -> None:
        """Stop the monitoring loop and cancel the background task."""
        self._running = False
        if self._monitor_task is not None:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None

    # ------------------------------------------------------------------
    # Monitoring loop
    # ------------------------------------------------------------------

    async def _monitor_loop(self, weibo_url: str, interval: int) -> None:
        """Execute the monitoring pipeline in a loop until stopped."""
        while self._running:
            try:
                await self._run_single_iteration(weibo_url)
            except Exception:
                logger.exception("Error during monitoring iteration")

            if not self._running:
                break

            await asyncio.sleep(interval)

    async def _run_single_iteration(self, weibo_url: str) -> None:
        """Execute one full pass of the monitoring pipeline.

        Steps:
        1. Get operator cookie from DB.
        2. Warmup cookie (get WBPSESS).
        3. Extract post author UID from URL.
        4. Fetch comments (max 10 pages).
        5. Get team UIDs from TeamMember table.
        6. Analyze comments (rank, hot flag, team member flag).
        7. Track team member comments.
        8. Build grid data for dashboard.
        9. Broadcast hot_comments_update (top N).
        10. Broadcast member_status_update.
        11. Broadcast stats_update.
        """
        # Step 1: Get operator cookie from DB.
        cookie = self._get_operator_cookie()
        if not cookie:
            logger.warning("No operator cookie available, skipping iteration")
            return

        # Step 2: Warmup cookie to get WBPSESS.
        warmed_cookie = await self.client.warmup_cookie(cookie)

        # Step 3: Extract post author UID from URL.
        post_author_uid = self._extract_post_author_uid(weibo_url)

        # Step 4: Fetch comments.
        comments = await self.fetcher.fetch_comments(
            weibo_url,
            cookie=warmed_cookie,
            max_pages=_MONITOR_MAX_PAGES,
            post_author_uid=post_author_uid,
        )

        # Step 5: Get team UIDs.
        team_uids = self.tracker.get_team_uids()

        # Step 6: Analyze (rank, flag hot, flag team member).
        analyzed = self.analyzer.analyze(comments, team_uids)

        # Step 7: Track team member comments.
        tracked = self.tracker.track_comments(analyzed, team_uids)

        # Step 8: Build grid data for dashboard.
        grid_data = self.tracker.get_member_grid_data(team_uids, tracked)

        # Step 9: Get current team hot status (used for stats).
        curr_status = self.analyzer.get_team_hot_status(analyzed, team_uids)

        # Step 10: Detect changes from previous status.
        self.analyzer.detect_changes(self._prev_status, curr_status)

        # Step 11: Broadcast hot comments update (top N).
        top_comments = [
            c.model_dump(mode="json") for c in analyzed[:_TOP_N_BROADCAST]
        ]
        await self.ws_manager.broadcast("hot_comments_update", {
            "comments": top_comments,
        })

        # Step 11: Broadcast member status update.
        await self.ws_manager.broadcast("member_status_update", grid_data)

        # Step 12: Broadcast stats update.
        stats = self.get_stats()
        await self.ws_manager.broadcast("stats_update", stats)

        # Step 13: Update previous status for stats.
        self._prev_status = curr_status

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return a statistics dictionary for the dashboard.

        Returns
        -------
        dict
            Keys: total_comments, team_hot_count, remaining_quota,
            elapsed_time, hot_ratio, team_online_count, executed_actions.
        """
        total_comments = 0
        executed_actions = 0
        team_hot_count = 0

        if self.db_session is not None:
            total_comments = self._get_total_comments()
            executed_actions = self._get_executed_actions()
            team_hot_count = self._get_team_hot_count()

        team_online_count = len(self.tracker.get_team_uids())

        remaining_quota = _COMMENT_LIMIT - total_comments

        elapsed_time = self._compute_elapsed_time()

        hot_ratio = 0.0
        if team_online_count > 0:
            hot_ratio = team_hot_count / team_online_count

        return {
            "total_comments": total_comments,
            "team_hot_count": team_hot_count,
            "remaining_quota": remaining_quota,
            "elapsed_time": elapsed_time,
            "hot_ratio": hot_ratio,
            "team_online_count": team_online_count,
            "executed_actions": executed_actions,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_operator_cookie(self) -> str:
        """Get the cookie string from the first active Account in DB."""
        if self.db_session is None:
            return ""

        from app.models.account import Account
        import json

        account = (
            self.db_session.query(Account)
            .filter(Account.status == "active")
            .first()
        )
        if account is None or not account.cookie_json:
            return ""

        try:
            cookie_dict = json.loads(account.cookie_json)
            if isinstance(cookie_dict, dict):
                return "; ".join(f"{k}={v}" for k, v in cookie_dict.items())
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
        return account.cookie_json

    @staticmethod
    def _extract_post_author_uid(weibo_url: str) -> str:
        """Extract the post author UID from a weibo.com URL.

        URL format: https://weibo.com/{uid}/{base62_mid} or
                     https://weibo.com/{uid}/{base62_mid}?type=comment
        """
        import re

        match = re.search(r"weibo\.com/(\d+)", weibo_url)
        if match:
            return match.group(1)
        return ""

    def _get_total_comments(self) -> int:
        """Get total_comments from the current CompetitionSession."""
        from app.models.competition_session import CompetitionSession

        session = (
            self.db_session.query(CompetitionSession)
            .order_by(CompetitionSession.id.desc())
            .first()
        )
        return session.total_comments if session else 0

    def _get_executed_actions(self) -> int:
        """Count ActionLog entries with status='success'."""
        from app.models.action_log import ActionLog

        return (
            self.db_session.query(ActionLog)
            .filter(ActionLog.status == "success")
            .count()
        )

    def _get_team_hot_count(self) -> int:
        """Count team members currently in hot comments."""
        return sum(1 for s in self._prev_status if s.get("is_hot", False))

    def _compute_elapsed_time(self) -> str:
        """Compute elapsed time since monitoring started as a human string."""
        if self._start_time is None:
            return "0s"

        delta = datetime.now(timezone.utc) - self._start_time
        total_seconds = int(delta.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}m{seconds}s"
        else:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h{minutes}m"
