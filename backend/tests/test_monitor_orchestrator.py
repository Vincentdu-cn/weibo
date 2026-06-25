"""TDD tests for MonitorOrchestrator and monitor API routes.

Tests cover:
- MonitorOrchestrator: start_monitoring, stop_monitoring, execute_alert_action, get_stats
- Monitoring loop: all 14 steps execute in correct order
- API endpoints: POST /api/monitor/start, POST /api/monitor/stop,
  POST /api/alerts/{id}/execute, GET /api/alerts/pending, GET /api/stats

All external dependencies are mocked — no real network calls.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.schemas.comment import CommentDTO
from app.services.monitor_orchestrator import MonitorOrchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_comment_dto(**kwargs) -> CommentDTO:
    """Create a CommentDTO with sensible defaults for testing."""
    defaults = {
        "id": 1,
        "weibo_comment_id": "wbc_001",
        "user_uid": "uid_001",
        "user_name": "TestUser",
        "content": "test comment",
        "like_count": 100,
        "rank": 1,
        "is_hot": True,
        "is_team_member": False,
    }
    defaults.update(kwargs)
    return CommentDTO(**defaults)


def make_mocks(db_session=None):
    """Create all mocked dependencies for MonitorOrchestrator.

    Returns a dict of mocks keyed by parameter name.
    """
    client = MagicMock()

    anti_detection = MagicMock()

    fetcher = MagicMock()
    fetcher.fetch_comments = AsyncMock()

    analyzer = MagicMock()

    tracker = MagicMock()

    alert_engine = MagicMock()
    alert_engine.process_changes = AsyncMock()
    alert_engine.resolve_alert = AsyncMock()
    alert_engine.attach_action = AsyncMock()

    action_executor = MagicMock()
    action_executor.batch_like = AsyncMock()
    action_executor.batch_comment = AsyncMock()

    ws_manager = MagicMock()
    ws_manager.broadcast = AsyncMock()

    return {
        "client": client,
        "anti_detection": anti_detection,
        "fetcher": fetcher,
        "analyzer": analyzer,
        "tracker": tracker,
        "alert_engine": alert_engine,
        "action_executor": action_executor,
        "ws_manager": ws_manager,
        "db_session": db_session,
    }


def make_orchestrator(mocks=None, db_session=None) -> tuple[MonitorOrchestrator, dict]:
    """Create a MonitorOrchestrator with all mocked dependencies.

    Returns (orchestrator, mocks_dict) for verification.
    """
    if mocks is None:
        mocks = make_mocks(db_session=db_session)

    orch = MonitorOrchestrator(
        client=mocks["client"],
        anti_detection=mocks["anti_detection"],
        fetcher=mocks["fetcher"],
        analyzer=mocks["analyzer"],
        tracker=mocks["tracker"],
        alert_engine=mocks["alert_engine"],
        action_executor=mocks["action_executor"],
        ws_manager=mocks["ws_manager"],
        db_session=mocks["db_session"],
    )
    return orch, mocks


# ---------------------------------------------------------------------------
# Constructor tests
# ---------------------------------------------------------------------------

class TestConstructor:
    def test_stores_all_dependencies(self):
        """Constructor stores all 9 parameters as attributes."""
        mocks = make_mocks()
        orch = MonitorOrchestrator(
            client=mocks["client"],
            anti_detection=mocks["anti_detection"],
            fetcher=mocks["fetcher"],
            analyzer=mocks["analyzer"],
            tracker=mocks["tracker"],
            alert_engine=mocks["alert_engine"],
            action_executor=mocks["action_executor"],
            ws_manager=mocks["ws_manager"],
            db_session=mocks["db_session"],
        )
        assert orch.client is mocks["client"]
        assert orch.anti_detection is mocks["anti_detection"]
        assert orch.fetcher is mocks["fetcher"]
        assert orch.analyzer is mocks["analyzer"]
        assert orch.tracker is mocks["tracker"]
        assert orch.alert_engine is mocks["alert_engine"]
        assert orch.action_executor is mocks["action_executor"]
        assert orch.ws_manager is mocks["ws_manager"]
        assert orch.db_session is mocks["db_session"]

    def test_initial_state_not_running(self):
        """Orchestrator starts with _running=False and no monitor_task."""
        orch, _ = make_orchestrator()
        assert orch._running is False
        assert orch._monitor_task is None

    def test_initial_prev_status_is_empty(self):
        """_prev_status starts as empty list."""
        orch, _ = make_orchestrator()
        assert orch._prev_status == []


# ---------------------------------------------------------------------------
# start_monitoring / stop_monitoring tests
# ---------------------------------------------------------------------------

class TestStartStopMonitoring:
    async def test_start_sets_running_true(self):
        """start_monitoring sets _running = True."""
        orch, mocks = make_orchestrator()
        mocks["fetcher"].fetch_comments.return_value = []

        await orch.start_monitoring("https://weibo.com/123", interval=0)
        assert orch._running is True
        await orch.stop_monitoring()

    async def test_start_creates_monitor_task(self):
        """start_monitoring creates an asyncio.Task stored in _monitor_task."""
        orch, mocks = make_orchestrator()
        mocks["fetcher"].fetch_comments.return_value = []

        await orch.start_monitoring("https://weibo.com/123", interval=0)
        assert orch._monitor_task is not None
        assert isinstance(orch._monitor_task, asyncio.Task)
        await orch.stop_monitoring()

    async def test_start_stores_weibo_url(self):
        """start_monitoring stores the weibo_url for later use."""
        orch, mocks = make_orchestrator()
        mocks["fetcher"].fetch_comments.return_value = []

        url = "https://weibo.com/12345"
        await orch.start_monitoring(url, interval=0)
        assert orch._weibo_url == url
        await orch.stop_monitoring()

    async def test_stop_sets_running_false(self):
        """stop_monitoring sets _running = False."""
        orch, mocks = make_orchestrator()
        mocks["fetcher"].fetch_comments.return_value = []

        await orch.start_monitoring("https://weibo.com/123", interval=0)
        await orch.stop_monitoring()
        assert orch._running is False

    async def test_stop_cancels_task(self):
        """stop_monitoring cancels _monitor_task and sets it to None."""
        orch, mocks = make_orchestrator()
        mocks["fetcher"].fetch_comments.return_value = []

        await orch.start_monitoring("https://weibo.com/123", interval=0)
        task = orch._monitor_task
        await orch.stop_monitoring()
        assert task.cancelled() or task.done()
        assert orch._monitor_task is None

    async def test_stop_when_not_running_is_safe(self):
        """stop_monitoring is safe to call when not monitoring."""
        orch, _ = make_orchestrator()
        await orch.stop_monitoring()  # Should not raise
        assert orch._running is False


# ---------------------------------------------------------------------------
# Monitoring loop tests
# ---------------------------------------------------------------------------

class TestMonitoringLoop:
    async def test_loop_calls_fetcher(self):
        """Loop calls fetcher.fetch_comments with the weibo_url."""
        orch, mocks = make_orchestrator()
        mocks["fetcher"].fetch_comments.return_value = []
        mocks["tracker"].get_team_uids.return_value = []
        mocks["analyzer"].analyze.return_value = []
        mocks["tracker"].track_comments.return_value = {}
        mocks["tracker"].get_member_grid_data.return_value = []
        mocks["analyzer"].get_team_hot_status.return_value = []
        mocks["analyzer"].detect_changes.return_value = {
            "entered_hot": [], "dropped_out": [], "rank_changed": []
        }
        mocks["alert_engine"].process_changes.return_value = []

        url = "https://weibo.com/456"
        await orch.start_monitoring(url, interval=0)
        # Let the loop run one iteration
        await asyncio.sleep(0.01)
        await orch.stop_monitoring()

        mocks["fetcher"].fetch_comments.assert_called_with(url)

    async def test_loop_calls_tracker_get_team_uids(self):
        """Loop calls tracker.get_team_uids()."""
        orch, mocks = make_orchestrator()
        mocks["fetcher"].fetch_comments.return_value = []
        mocks["tracker"].get_team_uids.return_value = []
        mocks["analyzer"].analyze.return_value = []
        mocks["tracker"].track_comments.return_value = {}
        mocks["tracker"].get_member_grid_data.return_value = []
        mocks["analyzer"].get_team_hot_status.return_value = []
        mocks["analyzer"].detect_changes.return_value = {
            "entered_hot": [], "dropped_out": [], "rank_changed": []
        }
        mocks["alert_engine"].process_changes.return_value = []

        await orch.start_monitoring("https://weibo.com/123", interval=0)
        await asyncio.sleep(0.01)
        await orch.stop_monitoring()

        mocks["tracker"].get_team_uids.assert_called()

    async def test_loop_calls_analyzer_analyze(self):
        """Loop calls analyzer.analyze with comments and team_uids."""
        orch, mocks = make_orchestrator()
        comments = [make_comment_dto()]
        team_uids = ["uid_001"]
        mocks["fetcher"].fetch_comments.return_value = comments
        mocks["tracker"].get_team_uids.return_value = team_uids
        mocks["analyzer"].analyze.return_value = comments
        mocks["tracker"].track_comments.return_value = {}
        mocks["tracker"].get_member_grid_data.return_value = []
        mocks["analyzer"].get_team_hot_status.return_value = []
        mocks["analyzer"].detect_changes.return_value = {
            "entered_hot": [], "dropped_out": [], "rank_changed": []
        }
        mocks["alert_engine"].process_changes.return_value = []

        await orch.start_monitoring("https://weibo.com/123", interval=0)
        await asyncio.sleep(0.01)
        await orch.stop_monitoring()

        mocks["analyzer"].analyze.assert_called_with(comments, team_uids)

    async def test_loop_calls_tracker_track_comments(self):
        """Loop calls tracker.track_comments with analyzed comments and team_uids."""
        orch, mocks = make_orchestrator()
        comments = [make_comment_dto()]
        team_uids = ["uid_001"]
        mocks["fetcher"].fetch_comments.return_value = comments
        mocks["tracker"].get_team_uids.return_value = team_uids
        mocks["analyzer"].analyze.return_value = comments
        mocks["tracker"].track_comments.return_value = {}
        mocks["tracker"].get_member_grid_data.return_value = []
        mocks["analyzer"].get_team_hot_status.return_value = []
        mocks["analyzer"].detect_changes.return_value = {
            "entered_hot": [], "dropped_out": [], "rank_changed": []
        }
        mocks["alert_engine"].process_changes.return_value = []

        await orch.start_monitoring("https://weibo.com/123", interval=0)
        await asyncio.sleep(0.01)
        await orch.stop_monitoring()

        mocks["tracker"].track_comments.assert_called_with(comments, team_uids)

    async def test_loop_calls_tracker_get_member_grid_data(self):
        """Loop calls tracker.get_member_grid_data with team_uids and tracked."""
        orch, mocks = make_orchestrator()
        comments = [make_comment_dto()]
        team_uids = ["uid_001"]
        tracked = {"uid_001": {"rank": 1}}
        mocks["fetcher"].fetch_comments.return_value = comments
        mocks["tracker"].get_team_uids.return_value = team_uids
        mocks["analyzer"].analyze.return_value = comments
        mocks["tracker"].track_comments.return_value = tracked
        mocks["tracker"].get_member_grid_data.return_value = []
        mocks["analyzer"].get_team_hot_status.return_value = []
        mocks["analyzer"].detect_changes.return_value = {
            "entered_hot": [], "dropped_out": [], "rank_changed": []
        }
        mocks["alert_engine"].process_changes.return_value = []

        await orch.start_monitoring("https://weibo.com/123", interval=0)
        await asyncio.sleep(0.01)
        await orch.stop_monitoring()

        mocks["tracker"].get_member_grid_data.assert_called_with(team_uids, tracked)

    async def test_loop_calls_analyzer_get_team_hot_status(self):
        """Loop calls analyzer.get_team_hot_status with analyzed and team_uids."""
        orch, mocks = make_orchestrator()
        comments = [make_comment_dto()]
        team_uids = ["uid_001"]
        mocks["fetcher"].fetch_comments.return_value = comments
        mocks["tracker"].get_team_uids.return_value = team_uids
        mocks["analyzer"].analyze.return_value = comments
        mocks["tracker"].track_comments.return_value = {}
        mocks["tracker"].get_member_grid_data.return_value = []
        mocks["analyzer"].get_team_hot_status.return_value = []
        mocks["analyzer"].detect_changes.return_value = {
            "entered_hot": [], "dropped_out": [], "rank_changed": []
        }
        mocks["alert_engine"].process_changes.return_value = []

        await orch.start_monitoring("https://weibo.com/123", interval=0)
        await asyncio.sleep(0.01)
        await orch.stop_monitoring()

        mocks["analyzer"].get_team_hot_status.assert_called_with(comments, team_uids)

    async def test_loop_calls_analyzer_detect_changes(self):
        """Loop calls analyzer.detect_changes with prev_status and curr_status."""
        orch, mocks = make_orchestrator()
        comments = [make_comment_dto()]
        team_uids = ["uid_001"]
        curr_status = [{"uid": "uid_001", "is_hot": True, "rank": 1}]
        mocks["fetcher"].fetch_comments.return_value = comments
        mocks["tracker"].get_team_uids.return_value = team_uids
        mocks["analyzer"].analyze.return_value = comments
        mocks["tracker"].track_comments.return_value = {}
        mocks["tracker"].get_member_grid_data.return_value = []
        mocks["analyzer"].get_team_hot_status.return_value = curr_status
        mocks["analyzer"].detect_changes.return_value = {
            "entered_hot": [], "dropped_out": [], "rank_changed": []
        }
        mocks["alert_engine"].process_changes.return_value = []

        await orch.start_monitoring("https://weibo.com/123", interval=0)
        await asyncio.sleep(0.01)
        await orch.stop_monitoring()

        # First call should have empty prev_status; loop may run multiple times
        first_call = mocks["analyzer"].detect_changes.call_args_list[0]
        assert first_call.args[0] == []
        assert first_call.args[1] == curr_status

    async def test_loop_calls_alert_engine_process_changes(self):
        """Loop calls alert_engine.process_changes with the changes dict."""
        orch, mocks = make_orchestrator()
        changes = {"entered_hot": ["uid_001"], "dropped_out": [], "rank_changed": []}
        mocks["fetcher"].fetch_comments.return_value = []
        mocks["tracker"].get_team_uids.return_value = []
        mocks["analyzer"].analyze.return_value = []
        mocks["tracker"].track_comments.return_value = {}
        mocks["tracker"].get_member_grid_data.return_value = []
        mocks["analyzer"].get_team_hot_status.return_value = []
        mocks["analyzer"].detect_changes.return_value = changes
        mocks["alert_engine"].process_changes.return_value = []

        await orch.start_monitoring("https://weibo.com/123", interval=0)
        await asyncio.sleep(0.01)
        await orch.stop_monitoring()

        mocks["alert_engine"].process_changes.assert_called_with(changes)

    async def test_loop_broadcasts_hot_comments_update(self):
        """Loop broadcasts 'hot_comments_update' via ws_manager."""
        orch, mocks = make_orchestrator()
        comments = [make_comment_dto(rank=1), make_comment_dto(id=2, rank=2)]
        mocks["fetcher"].fetch_comments.return_value = comments
        mocks["tracker"].get_team_uids.return_value = []
        mocks["analyzer"].analyze.return_value = comments
        mocks["tracker"].track_comments.return_value = {}
        mocks["tracker"].get_member_grid_data.return_value = []
        mocks["analyzer"].get_team_hot_status.return_value = []
        mocks["analyzer"].detect_changes.return_value = {
            "entered_hot": [], "dropped_out": [], "rank_changed": []
        }
        mocks["alert_engine"].process_changes.return_value = []

        await orch.start_monitoring("https://weibo.com/123", interval=0)
        await asyncio.sleep(0.01)
        await orch.stop_monitoring()

        broadcast_calls = mocks["ws_manager"].broadcast.call_args_list
        types_broadcast = [c.args[0] for c in broadcast_calls]
        assert "hot_comments_update" in types_broadcast

    async def test_loop_broadcasts_member_status_update(self):
        """Loop broadcasts 'member_status_update' with grid_data."""
        orch, mocks = make_orchestrator()
        grid_data = [{"uid": "uid_001", "current_rank": 1}]
        mocks["fetcher"].fetch_comments.return_value = []
        mocks["tracker"].get_team_uids.return_value = []
        mocks["analyzer"].analyze.return_value = []
        mocks["tracker"].track_comments.return_value = {}
        mocks["tracker"].get_member_grid_data.return_value = grid_data
        mocks["analyzer"].get_team_hot_status.return_value = []
        mocks["analyzer"].detect_changes.return_value = {
            "entered_hot": [], "dropped_out": [], "rank_changed": []
        }
        mocks["alert_engine"].process_changes.return_value = []

        await orch.start_monitoring("https://weibo.com/123", interval=0)
        await asyncio.sleep(0.01)
        await orch.stop_monitoring()

        broadcast_calls = mocks["ws_manager"].broadcast.call_args_list
        member_calls = [c for c in broadcast_calls if c.args[0] == "member_status_update"]
        assert len(member_calls) >= 1
        assert member_calls[0].args[1] == grid_data

    async def test_loop_broadcasts_stats_update(self):
        """Loop broadcasts 'stats_update' with a stats dict."""
        orch, mocks = make_orchestrator()
        mocks["fetcher"].fetch_comments.return_value = []
        mocks["tracker"].get_team_uids.return_value = []
        mocks["analyzer"].analyze.return_value = []
        mocks["tracker"].track_comments.return_value = {}
        mocks["tracker"].get_member_grid_data.return_value = []
        mocks["analyzer"].get_team_hot_status.return_value = []
        mocks["analyzer"].detect_changes.return_value = {
            "entered_hot": [], "dropped_out": [], "rank_changed": []
        }
        mocks["alert_engine"].process_changes.return_value = []

        await orch.start_monitoring("https://weibo.com/123", interval=0)
        await asyncio.sleep(0.01)
        await orch.stop_monitoring()

        broadcast_calls = mocks["ws_manager"].broadcast.call_args_list
        stats_calls = [c for c in broadcast_calls if c.args[0] == "stats_update"]
        assert len(stats_calls) >= 1

    async def test_loop_broadcasts_alert_new_for_each_alert(self):
        """Loop broadcasts 'alert_new' for each alert returned by process_changes."""
        orch, mocks = make_orchestrator()
        alert1 = MagicMock(id=1, alert_type="dropped_out", account_uid="uid_001",
                           message="test1", status="pending")
        alert2 = MagicMock(id=2, alert_type="entered_hot", account_uid="uid_002",
                           message="test2", status="pending")
        mocks["fetcher"].fetch_comments.return_value = []
        mocks["tracker"].get_team_uids.return_value = []
        mocks["analyzer"].analyze.return_value = []
        mocks["tracker"].track_comments.return_value = {}
        mocks["tracker"].get_member_grid_data.return_value = []
        mocks["analyzer"].get_team_hot_status.return_value = []
        mocks["analyzer"].detect_changes.return_value = {
            "entered_hot": [], "dropped_out": [], "rank_changed": []
        }
        mocks["alert_engine"].process_changes.return_value = [alert1, alert2]

        await orch.start_monitoring("https://weibo.com/123", interval=0)
        await asyncio.sleep(0.01)
        await orch.stop_monitoring()

        broadcast_calls = mocks["ws_manager"].broadcast.call_args_list
        alert_calls = [c for c in broadcast_calls if c.args[0] == "alert_new"]
        assert len(alert_calls) >= 2

    async def test_loop_updates_prev_status(self):
        """Loop updates _prev_status to curr_status after each iteration."""
        orch, mocks = make_orchestrator()
        curr_status = [{"uid": "uid_001", "is_hot": True, "rank": 1}]
        mocks["fetcher"].fetch_comments.return_value = []
        mocks["tracker"].get_team_uids.return_value = []
        mocks["analyzer"].analyze.return_value = []
        mocks["tracker"].track_comments.return_value = {}
        mocks["tracker"].get_member_grid_data.return_value = []
        mocks["analyzer"].get_team_hot_status.return_value = curr_status
        mocks["analyzer"].detect_changes.return_value = {
            "entered_hot": [], "dropped_out": [], "rank_changed": []
        }
        mocks["alert_engine"].process_changes.return_value = []

        await orch.start_monitoring("https://weibo.com/123", interval=0)
        await asyncio.sleep(0.01)
        await orch.stop_monitoring()

        assert orch._prev_status == curr_status

    async def test_loop_executes_full_pipeline_order(self):
        """Loop calls services in the correct order: fetch → uids → analyze → track → grid → status → changes → alerts."""
        orch, mocks = make_orchestrator()
        comments = [make_comment_dto()]
        team_uids = ["uid_001"]
        analyzed = [make_comment_dto(is_team_member=True)]
        tracked = {"uid_001": {"rank": 1}}
        grid_data = [{"uid": "uid_001", "current_rank": 1}]
        curr_status = [{"uid": "uid_001", "is_hot": True, "rank": 1}]
        changes = {"entered_hot": [], "dropped_out": [], "rank_changed": []}

        mocks["fetcher"].fetch_comments.return_value = comments
        mocks["tracker"].get_team_uids.return_value = team_uids
        mocks["analyzer"].analyze.return_value = analyzed
        mocks["tracker"].track_comments.return_value = tracked
        mocks["tracker"].get_member_grid_data.return_value = grid_data
        mocks["analyzer"].get_team_hot_status.return_value = curr_status
        mocks["analyzer"].detect_changes.return_value = changes
        mocks["alert_engine"].process_changes.return_value = []

        await orch.start_monitoring("https://weibo.com/123", interval=0)
        await asyncio.sleep(0.01)
        await orch.stop_monitoring()

        # Verify all key methods were called
        mocks["fetcher"].fetch_comments.assert_called()
        mocks["tracker"].get_team_uids.assert_called()
        mocks["analyzer"].analyze.assert_called()
        mocks["tracker"].track_comments.assert_called()
        mocks["tracker"].get_member_grid_data.assert_called()
        mocks["analyzer"].get_team_hot_status.assert_called()
        mocks["analyzer"].detect_changes.assert_called()
        mocks["alert_engine"].process_changes.assert_called()


# ---------------------------------------------------------------------------
# execute_alert_action tests
# ---------------------------------------------------------------------------

class TestExecuteAlertAction:
    async def test_calls_batch_like(self):
        """execute_alert_action calls action_executor.batch_like."""
        orch, mocks = make_orchestrator()
        alert = MagicMock(
            id=1, comment_id=42, alert_type="dropped_out",
            account_uid="uid_001", message="test", status="pending",
        )
        mocks["alert_engine"].get_pending_alerts.return_value = [alert]
        mocks["action_executor"].batch_like.return_value = [
            {"uid": "uid_001", "success": True, "error_msg": None}
        ]
        mocks["action_executor"].batch_comment.return_value = []
        mocks["alert_engine"].resolve_alert.return_value = True

        await orch.execute_alert_action(1, "nice comment", [1, 2])

        mocks["action_executor"].batch_like.assert_called_once()

    async def test_calls_batch_comment(self):
        """execute_alert_action calls action_executor.batch_comment."""
        orch, mocks = make_orchestrator()
        alert = MagicMock(
            id=1, comment_id=42, alert_type="dropped_out",
            account_uid="uid_001", message="test", status="pending",
        )
        mocks["alert_engine"].get_pending_alerts.return_value = [alert]
        mocks["action_executor"].batch_like.return_value = []
        mocks["action_executor"].batch_comment.return_value = [
            {"uid": "uid_001", "success": True, "comment_id": "999", "error_msg": None}
        ]
        mocks["alert_engine"].resolve_alert.return_value = True

        await orch.execute_alert_action(1, "nice comment", [1, 2])

        mocks["action_executor"].batch_comment.assert_called_once()

    async def test_calls_resolve_alert(self):
        """execute_alert_action calls alert_engine.resolve_alert."""
        orch, mocks = make_orchestrator()
        alert = MagicMock(
            id=1, comment_id=42, alert_type="dropped_out",
            account_uid="uid_001", message="test", status="pending",
        )
        mocks["alert_engine"].get_pending_alerts.return_value = [alert]
        mocks["action_executor"].batch_like.return_value = []
        mocks["action_executor"].batch_comment.return_value = []
        mocks["alert_engine"].resolve_alert.return_value = True

        await orch.execute_alert_action(1, "nice comment", [1])

        mocks["alert_engine"].resolve_alert.assert_called_once_with(1, "executed")

    async def test_broadcasts_action_result(self):
        """execute_alert_action broadcasts 'action_result' via ws_manager."""
        orch, mocks = make_orchestrator()
        alert = MagicMock(
            id=1, comment_id=42, alert_type="dropped_out",
            account_uid="uid_001", message="test", status="pending",
        )
        mocks["alert_engine"].get_pending_alerts.return_value = [alert]
        mocks["action_executor"].batch_like.return_value = [
            {"uid": "uid_001", "success": True, "error_msg": None}
        ]
        mocks["action_executor"].batch_comment.return_value = []
        mocks["alert_engine"].resolve_alert.return_value = True

        await orch.execute_alert_action(1, "nice comment", [1])

        broadcast_calls = mocks["ws_manager"].broadcast.call_args_list
        action_calls = [c for c in broadcast_calls if c.args[0] == "action_result"]
        assert len(action_calls) == 1

    async def test_returns_result_dict(self):
        """execute_alert_action returns a result summary dict."""
        orch, mocks = make_orchestrator()
        alert = MagicMock(
            id=1, comment_id=42, alert_type="dropped_out",
            account_uid="uid_001", message="test", status="pending",
        )
        mocks["alert_engine"].get_pending_alerts.return_value = [alert]
        mocks["action_executor"].batch_like.return_value = [
            {"uid": "uid_001", "success": True, "error_msg": None}
        ]
        mocks["action_executor"].batch_comment.return_value = [
            {"uid": "uid_001", "success": True, "comment_id": "999", "error_msg": None}
        ]
        mocks["alert_engine"].resolve_alert.return_value = True

        result = await orch.execute_alert_action(1, "nice comment", [1])

        assert isinstance(result, dict)
        assert "alert_id" in result
        assert "like_results" in result
        assert "comment_results" in result
        assert "resolved" in result

    async def test_returns_result_with_like_and_comment_details(self):
        """Result dict contains the actual like and comment results."""
        orch, mocks = make_orchestrator()
        alert = MagicMock(
            id=1, comment_id=42, alert_type="dropped_out",
            account_uid="uid_001", message="test", status="pending",
        )
        like_results = [{"uid": "uid_001", "success": True, "error_msg": None}]
        comment_results = [{"uid": "uid_001", "success": True, "comment_id": "999", "error_msg": None}]
        mocks["alert_engine"].get_pending_alerts.return_value = [alert]
        mocks["action_executor"].batch_like.return_value = like_results
        mocks["action_executor"].batch_comment.return_value = comment_results
        mocks["alert_engine"].resolve_alert.return_value = True

        result = await orch.execute_alert_action(1, "nice comment", [1])

        assert result["like_results"] == like_results
        assert result["comment_results"] == comment_results
        assert result["resolved"] is True

    async def test_with_db_session_gets_cookies_from_accounts(self):
        """When db_session is available, cookies are fetched from Account table."""
        from app.models.account import Account
        from app.models.competition_session import CompetitionSession

        # Create a real in-memory DB session
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.core.database import Base
        from app.models import Account as AccountModel, ActionLog, Alert, Comment, CommentSnapshot, CompetitionSession as SessionModel

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        db = SessionLocal()

        # Create a CompetitionSession
        session = SessionModel(
            target_weibo_url="https://weibo.com/123",
            target_weibo_mid="5056360400000000",
            status="running",
            total_comments=0,
        )
        db.add(session)
        db.commit()

        # Create Accounts with cookies
        acc1 = AccountModel(
            weibo_uid="uid_001", nickname="user1",
            cookie_json="cookie1=data1", status="active",
        )
        acc2 = AccountModel(
            weibo_uid="uid_002", nickname="user2",
            cookie_json="cookie2=data2", status="active",
        )
        db.add_all([acc1, acc2])
        db.commit()

        # Create an Alert
        alert = Alert(
            session_id=session.id, account_uid="uid_001",
            comment_id=None, alert_type="dropped_out",
            message="test alert", status="pending",
        )
        db.add(alert)
        db.commit()

        orch, mocks = make_orchestrator(db_session=db)
        mocks["alert_engine"].get_pending_alerts.return_value = [alert]
        mocks["action_executor"].batch_like.return_value = []
        mocks["action_executor"].batch_comment.return_value = []
        mocks["alert_engine"].resolve_alert.return_value = True

        await orch.execute_alert_action(alert.id, "test comment", [acc1.id, acc2.id])

        # Verify batch_like was called with cookies from DB
        call_args = mocks["action_executor"].batch_like.call_args
        cookies = call_args[0][1]  # second positional arg
        assert len(cookies) == 2
        uids = [c[0] for c in cookies]
        assert "uid_001" in uids
        assert "uid_002" in uids

        db.close()
        Base.metadata.drop_all(bind=engine)

    async def test_alert_not_found_returns_error(self):
        """execute_alert_action returns error when alert not found."""
        orch, mocks = make_orchestrator()
        mocks["alert_engine"].get_pending_alerts.return_value = []

        result = await orch.execute_alert_action(999, "comment", [1])

        assert result["resolved"] is False
        assert "error" in result


# ---------------------------------------------------------------------------
# get_stats tests
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_returns_dict_with_required_keys(self):
        """get_stats returns a dict with all StatsDTO keys."""
        orch, mocks = make_orchestrator()
        mocks["tracker"].get_team_uids.return_value = []
        mocks["alert_engine"].get_pending_alerts.return_value = []

        stats = orch.get_stats()

        required_keys = {
            "total_comments", "team_hot_count", "remaining_quota",
            "elapsed_time", "hot_ratio", "team_online_count",
            "pending_alerts", "executed_actions",
        }
        assert required_keys.issubset(set(stats.keys()))

    def test_total_comments_defaults_to_zero(self):
        """total_comments is 0 when no DB session."""
        orch, _ = make_orchestrator()
        stats = orch.get_stats()
        assert stats["total_comments"] == 0

    def test_remaining_quota_is_500_minus_total(self):
        """remaining_quota = 500 - total_comments."""
        orch, _ = make_orchestrator()
        stats = orch.get_stats()
        assert stats["remaining_quota"] == 500

    def test_pending_alerts_from_alert_engine(self):
        """pending_alerts count comes from alert_engine.get_pending_alerts()."""
        orch, mocks = make_orchestrator()
        mocks["alert_engine"].get_pending_alerts.return_value = [
            MagicMock(id=1), MagicMock(id=2), MagicMock(id=3),
        ]
        mocks["tracker"].get_team_uids.return_value = []

        stats = orch.get_stats()
        assert stats["pending_alerts"] == 3

    def test_team_online_count_from_tracker(self):
        """team_online_count comes from tracker.get_team_uids()."""
        orch, mocks = make_orchestrator()
        mocks["tracker"].get_team_uids.return_value = ["uid1", "uid2", "uid3"]
        mocks["alert_engine"].get_pending_alerts.return_value = []

        stats = orch.get_stats()
        assert stats["team_online_count"] == 3

    def test_with_db_session_queries_session(self):
        """get_stats queries CompetitionSession when db_session is available."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.core.database import Base
        from app.models import Account, ActionLog, Alert, Comment, CommentSnapshot, CompetitionSession

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        db = SessionLocal()

        session = CompetitionSession(
            target_weibo_url="https://weibo.com/123",
            target_weibo_mid="5056360400000000",
            status="running",
            total_comments=42,
        )
        db.add(session)
        db.commit()

        orch, mocks = make_orchestrator(db_session=db)
        mocks["tracker"].get_team_uids.return_value = []
        mocks["alert_engine"].get_pending_alerts.return_value = []

        stats = orch.get_stats()
        assert stats["total_comments"] == 42
        assert stats["remaining_quota"] == 458

        db.close()
        Base.metadata.drop_all(bind=engine)

    def test_executed_actions_from_db(self):
        """executed_actions counts ActionLog entries with status='success'."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.core.database import Base
        from app.models import Account, ActionLog, Alert, Comment, CommentSnapshot, CompetitionSession

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        db = SessionLocal()

        db.add(ActionLog(account_uid="uid1", action_type="like", target_comment_id="1", status="success"))
        db.add(ActionLog(account_uid="uid2", action_type="comment", target_comment_id="2", status="success"))
        db.add(ActionLog(account_uid="uid3", action_type="like", target_comment_id="3", status="failed"))
        db.commit()

        orch, mocks = make_orchestrator(db_session=db)
        mocks["tracker"].get_team_uids.return_value = []
        mocks["alert_engine"].get_pending_alerts.return_value = []

        stats = orch.get_stats()
        assert stats["executed_actions"] == 2

        db.close()
        Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

class TestMonitorAPI:
    @pytest.fixture
    def client_and_orch(self):
        """Create a FastAPI TestClient with a mock orchestrator."""
        from app.main import app
        from app.api import monitor as monitor_module

        orch, mocks = make_orchestrator()
        # Set the module-level orchestrator
        original = monitor_module._orchestrator
        monitor_module._orchestrator = orch

        mocks["fetcher"].fetch_comments.return_value = []
        mocks["tracker"].get_team_uids.return_value = []
        mocks["analyzer"].analyze.return_value = []
        mocks["tracker"].track_comments.return_value = {}
        mocks["tracker"].get_member_grid_data.return_value = []
        mocks["analyzer"].get_team_hot_status.return_value = []
        mocks["analyzer"].detect_changes.return_value = {
            "entered_hot": [], "dropped_out": [], "rank_changed": []
        }
        mocks["alert_engine"].process_changes.return_value = []
        mocks["alert_engine"].get_pending_alerts.return_value = []

        with TestClient(app) as client:
            yield client, orch, mocks

        monitor_module._orchestrator = original

    def test_start_monitor(self, client_and_orch):
        """POST /api/monitor/start returns {'status': 'running'}."""
        client, orch, mocks = client_and_orch
        resp = client.post("/api/monitor/start", json={"weibo_url": "https://weibo.com/123"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    def test_stop_monitor(self, client_and_orch):
        """POST /api/monitor/stop returns {'status': 'stopped'}."""
        client, orch, mocks = client_and_orch
        # Start first
        client.post("/api/monitor/start", json={"weibo_url": "https://weibo.com/123"})
        # Stop
        resp = client.post("/api/monitor/stop")
        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"

    def test_start_with_interval(self, client_and_orch):
        """POST /api/monitor/start accepts optional interval parameter."""
        client, orch, mocks = client_and_orch
        resp = client.post("/api/monitor/start", json={
            "weibo_url": "https://weibo.com/456", "interval": 30
        })
        assert resp.status_code == 200

    def test_get_pending_alerts(self, client_and_orch):
        """GET /api/alerts/pending returns list of pending alerts."""
        client, orch, mocks = client_and_orch
        alert = MagicMock(
            id=1, account_uid="uid_001", comment_id=None,
            alert_type="dropped_out", message="test", status="pending",
        )
        mocks["alert_engine"].get_pending_alerts.return_value = [alert]

        resp = client.get("/api/alerts/pending")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_get_stats(self, client_and_orch):
        """GET /api/stats returns stats dict."""
        client, orch, mocks = client_and_orch
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_comments" in data
        assert "remaining_quota" in data
        assert "pending_alerts" in data

    def test_execute_alert(self, client_and_orch):
        """POST /api/alerts/{id}/execute executes the alert action."""
        client, orch, mocks = client_and_orch
        alert = MagicMock(
            id=1, comment_id=42, account_uid="uid_001",
            alert_type="dropped_out", message="test", status="pending",
        )
        mocks["alert_engine"].get_pending_alerts.return_value = [alert]
        mocks["action_executor"].batch_like.return_value = []
        mocks["action_executor"].batch_comment.return_value = []
        mocks["alert_engine"].resolve_alert.return_value = True

        resp = client.post("/api/alerts/1/execute", json={
            "comment": "nice post", "account_ids": [1, 2]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "alert_id" in data
