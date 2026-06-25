"""Monitor orchestrator — connects all Wave 1-2 services into a monitoring loop.

Provides :class:`MonitorOrchestrator` which:
- Runs a periodic monitoring loop that fetches comments, analyzes hot status,
  tracks team members, detects changes, generates alerts, and broadcasts
  real-time WebSocket updates.
- Executes semi-automatic alert actions (like + comment) with human-confirmed
  parameters.
- Provides dashboard statistics.

Design notes
------------
- The monitoring loop runs as a background ``asyncio.Task`` created by
  :meth:`start_monitoring` and cancelled by :meth:`stop_monitoring`.
- All Wave 1-2 services are injected — the orchestrator does not import or
  construct them directly, making it fully testable with mocks.
- WebSocket broadcasts use ``ws_manager.broadcast(message_type, data)``.
- DB access is optional — when ``db_session`` is ``None``, DB-dependent
  operations gracefully degrade (e.g., stats return zeros, cookies can't be
  fetched from DB).
- The monitoring loop follows the 14-step pipeline defined in Task 15:
  fetch → uids → analyze → track → grid → status → changes → alerts →
  broadcast (hot_comments, member_status, stats, alert_new) → sleep.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.services.action_executor import ActionExecutor
from app.services.alert_engine import AlertEngine
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


class MonitorOrchestrator:
    """Orchestrates the real-time monitoring loop and alert action execution.

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
    alert_engine
        :class:`AlertEngine` for alert generation and lifecycle.
    action_executor
        :class:`ActionExecutor` for like/comment actions.
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
        alert_engine: AlertEngine,
        action_executor: ActionExecutor,
        ws_manager: WebSocketConnectionManager,
        db_session: Any = None,
    ) -> None:
        self.client = client
        self.anti_detection = anti_detection
        self.fetcher = fetcher
        self.analyzer = analyzer
        self.tracker = tracker
        self.alert_engine = alert_engine
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

        Creates an :class:`asyncio.Task` that runs :meth:`_monitor_loop`
        indefinitely until :meth:`stop_monitoring` is called.

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
        """Stop the monitoring loop and cancel the background task.

        Safe to call when monitoring is not active.
        """
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
        """Execute the 14-step monitoring pipeline in a loop.

        Steps:
        1.  Fetch comments via ``fetcher.fetch_comments``.
        2.  Get team UIDs via ``tracker.get_team_uids``.
        3.  Analyze comments via ``analyzer.analyze``.
        4.  Track team comments via ``tracker.track_comments``.
        5.  Build grid data via ``tracker.get_member_grid_data``.
        6.  Get team hot status via ``analyzer.get_team_hot_status``.
        7.  Detect changes via ``analyzer.detect_changes``.
        8.  Process changes via ``alert_engine.process_changes`` (async).
        9.  Broadcast ``hot_comments_update`` with top N comments.
        10. Broadcast ``member_status_update`` with grid data.
        11. Broadcast ``stats_update`` with current stats.
        12. Broadcast ``alert_new`` for each new alert.
        13. Update ``_prev_status``.
        14. Sleep for ``interval`` seconds.
        """
        while self._running:
            try:
                await self._run_single_iteration(weibo_url)
            except Exception:
                logger.exception("Error during monitoring iteration")

            if not self._running:
                break

            await asyncio.sleep(interval)

    async def _run_single_iteration(self, weibo_url: str) -> None:
        """Execute one full pass of the monitoring pipeline."""
        # Step 1: Fetch comments.
        comments = await self.fetcher.fetch_comments(weibo_url)

        # Step 2: Get team UIDs.
        team_uids = self.tracker.get_team_uids()

        # Step 3: Analyze (rank, flag hot, flag team member).
        analyzed = self.analyzer.analyze(comments, team_uids)

        # Step 4: Track team member comments.
        tracked = self.tracker.track_comments(analyzed, team_uids)

        # Step 5: Build grid data for dashboard.
        grid_data = self.tracker.get_member_grid_data(team_uids, tracked)

        # Step 6: Get current team hot status.
        curr_status = self.analyzer.get_team_hot_status(analyzed, team_uids)

        # Step 7: Detect changes from previous status.
        changes = self.analyzer.detect_changes(self._prev_status, curr_status)

        # Step 8: Process changes into alerts.
        new_alerts = await self.alert_engine.process_changes(changes)

        # Step 9: Broadcast hot comments update (top N).
        top_comments = [
            c.model_dump() for c in analyzed[:_TOP_N_BROADCAST]
        ]
        await self.ws_manager.broadcast("hot_comments_update", {
            "comments": top_comments,
        })

        # Step 10: Broadcast member status update.
        await self.ws_manager.broadcast("member_status_update", grid_data)

        # Step 11: Broadcast stats update.
        stats = self.get_stats()
        await self.ws_manager.broadcast("stats_update", stats)

        # Step 12: Broadcast alert_new for each new alert.
        for alert in new_alerts:
            await self.ws_manager.broadcast("alert_new", {
                "alert_id": alert.id,
                "alert_type": alert.alert_type,
                "account_uid": alert.account_uid,
                "message": alert.message,
                "status": alert.status,
            })

        # Step 13: Update previous status.
        self._prev_status = curr_status

    # ------------------------------------------------------------------
    # Alert action execution
    # ------------------------------------------------------------------

    async def execute_alert_action(
        self,
        alert_id: int,
        comment_content: str,
        selected_account_ids: list[int],
    ) -> dict[str, Any]:
        """Execute a semi-automatic alert action (like + comment).

        1. Retrieves the alert (from ``alert_engine`` or DB).
        2. Retrieves cookies for the selected accounts from the DB.
        3. Calls ``action_executor.batch_like`` for the alert's comment.
        4. Calls ``action_executor.batch_comment`` for the target Weibo post.
        5. Resolves the alert via ``alert_engine.resolve_alert``.
        6. Broadcasts ``action_result`` via WebSocket.
        7. Returns a result summary dict.

        Parameters
        ----------
        alert_id
            The ID of the alert to execute.
        comment_content
            The comment text to post.
        selected_account_ids
            List of Account IDs to use for the action.

        Returns
        -------
        dict
            Result summary with keys: ``alert_id``, ``like_results``,
            ``comment_results``, ``resolved``, and optionally ``error``.
        """
        # Step 1: Find the alert.
        alert = self._find_alert(alert_id)
        if alert is None:
            result = {
                "alert_id": alert_id,
                "like_results": [],
                "comment_results": [],
                "resolved": False,
                "error": f"Alert {alert_id} not found",
            }
            await self.ws_manager.broadcast("action_result", result)
            return result

        # Step 2: Get cookies for selected accounts.
        cookies = self._get_cookies(selected_account_ids)

        # Step 3: Get comment_id and weibo_mid.
        comment_id = getattr(alert, "comment_id", None) or ""
        weibo_mid = self._get_weibo_mid()

        # Step 4: Execute batch like.
        like_results: list[dict] = await self.action_executor.batch_like(
            comment_id, cookies
        )

        # Step 5: Execute batch comment.
        comment_results: list[dict] = []
        if comment_content:
            comment_results = await self.action_executor.batch_comment(
                weibo_mid, comment_content, cookies
            )

        # Step 6: Resolve the alert.
        resolved = await self.alert_engine.resolve_alert(alert_id, "executed")

        # Step 7: Build and broadcast result.
        result = {
            "alert_id": alert_id,
            "like_results": like_results,
            "comment_results": comment_results,
            "resolved": resolved,
        }
        await self.ws_manager.broadcast("action_result", result)

        return result

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return a StatsDTO-compatible statistics dictionary.

        Queries the DB (when available) for:
        - ``total_comments`` from CompetitionSession.
        - ``executed_actions`` from ActionLog (status='success').
        - ``pending_alerts`` from AlertEngine.
        - ``team_online_count`` from TeamMemberTracker.

        Returns
        -------
        dict
            Keys: total_comments, team_hot_count, remaining_quota,
            elapsed_time, hot_ratio, team_online_count, pending_alerts,
            executed_actions.
        """
        total_comments = 0
        executed_actions = 0
        team_hot_count = 0

        if self.db_session is not None:
            total_comments = self._get_total_comments()
            executed_actions = self._get_executed_actions()
            team_hot_count = self._get_team_hot_count()

        pending_alerts = len(self.alert_engine.get_pending_alerts())
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
            "pending_alerts": pending_alerts,
            "executed_actions": executed_actions,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_alert(self, alert_id: int):
        """Find an alert by ID from the alert engine or DB.

        Returns the Alert object or ``None`` if not found.
        """
        # Try alert_engine first.
        pending = self.alert_engine.get_pending_alerts()
        for alert in pending:
            if getattr(alert, "id", None) == alert_id:
                return alert

        # Fall back to DB query.
        if self.db_session is not None:
            from app.models.alert import Alert
            return (
                self.db_session.query(Alert)
                .filter(Alert.id == alert_id)
                .first()
            )

        return None

    def _get_cookies(self, account_ids: list[int]) -> list[tuple[str, str]]:
        """Retrieve (uid, cookie_str) tuples for the given Account IDs.

        Queries the Account table when a DB session is available.
        Returns an empty list when no DB session or no accounts found.
        """
        if self.db_session is None or not account_ids:
            return []

        from app.models.account import Account

        accounts = (
            self.db_session.query(Account)
            .filter(Account.id.in_(account_ids))
            .all()
        )

        cookies: list[tuple[str, str]] = []
        for acc in accounts:
            if acc.cookie_json:
                cookies.append((acc.weibo_uid, acc.cookie_json))

        return cookies

    def _get_weibo_mid(self) -> str:
        """Get the Weibo MID for the current monitoring session.

        Reads from CompetitionSession when DB is available, otherwise
        returns an empty string.
        """
        if self.db_session is None:
            return ""

        from app.models.competition_session import CompetitionSession

        session = (
            self.db_session.query(CompetitionSession)
            .filter(CompetitionSession.status == "running")
            .first()
        )
        if session is not None:
            return session.target_weibo_mid

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
        """Count team members currently in hot comments.

        Uses ``_prev_status`` which is updated each monitoring iteration.
        """
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
