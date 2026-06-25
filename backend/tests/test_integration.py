"""Integration tests — cross-service workflows with real DB sessions.

All HTTP calls are mocked. ``asyncio.sleep`` is patched in anti_detection
to avoid real waiting. Uses the ``db_session`` fixture from conftest.py
(in-memory SQLite) for real database operations.

pytest async mode=auto — no @pytest.mark.asyncio needed.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import Account, ActionLog, Alert, CompetitionSession
from app.schemas.comment import CommentDTO
from app.services.action_executor import ActionExecutor
from app.services.alert_engine import AlertEngine
from app.services.anti_detection import AntiDetectionEngine, CookiePool
from app.services.competition_manager import CompetitionManager
from app.services.hot_analyzer import HotCommentAnalyzer
from app.services.member_tracker import TeamMemberTracker
from app.services.monitor_orchestrator import MonitorOrchestrator
from app.services.ws_manager import WebSocketConnectionManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WEIBO_URL = "https://weibo.com/1234567890/z0JH2lOMb"


def make_comment_dto(**kwargs) -> CommentDTO:
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


# ---------------------------------------------------------------------------
# Test 1: CompetitionManager + MonitorOrchestrator lifecycle with real DB
# ---------------------------------------------------------------------------

class TestCompetitionLifecycle:
    async def test_start_pause_resume_end_with_db(self, db_session):
        """CompetitionManager creates/updates CompetitionSession in real DB
        and delegates to MonitorOrchestrator at each lifecycle transition."""
        mock_monitor = MagicMock()
        mock_monitor.start_monitoring = AsyncMock()
        mock_monitor.stop_monitoring = AsyncMock()

        mgr = CompetitionManager(
            db_session=db_session, monitor_orchestrator=mock_monitor,
        )

        # Start
        result = await mgr.start_competition(WEIBO_URL)
        assert result["status"] == "running"
        session = db_session.query(CompetitionSession).first()
        assert session is not None
        assert session.status == "running"
        assert session.target_weibo_url == WEIBO_URL
        mock_monitor.start_monitoring.assert_called_once_with(WEIBO_URL)

        # Pause
        await mgr.pause_competition()
        db_session.refresh(session)
        assert session.status == "paused"
        mock_monitor.stop_monitoring.assert_called_once()

        # Resume
        await mgr.resume_competition()
        db_session.refresh(session)
        assert session.status == "running"
        assert mock_monitor.start_monitoring.call_count == 2

        # End
        end_result = await mgr.end_competition()
        db_session.refresh(session)
        assert session.status == "ended"
        assert session.ended_at is not None
        assert end_result["status"] == "ended"
        assert mock_monitor.stop_monitoring.call_count == 2


# ---------------------------------------------------------------------------
# Test 2: CompetitionManager comment quota enforcement with real DB
# ---------------------------------------------------------------------------

class TestCommentQuotaEnforcement:
    async def test_quota_blocks_at_500(self, db_session):
        """can_post_comment returns False and increment fails at 500."""
        mgr = CompetitionManager(db_session=db_session)
        await mgr.start_competition(WEIBO_URL)

        session = db_session.query(CompetitionSession).first()
        session.total_comments = 499
        db_session.commit()

        assert await mgr.can_post_comment() is True
        assert await mgr.increment_comment_count() is True
        db_session.refresh(session)
        assert session.total_comments == 500

        assert await mgr.can_post_comment() is False
        assert await mgr.increment_comment_count() is False
        db_session.refresh(session)
        assert session.total_comments == 500  # unchanged


# ---------------------------------------------------------------------------
# Test 3: AlertEngine process_changes persists alerts to real DB
# ---------------------------------------------------------------------------

class TestAlertEnginePersistence:
    async def test_process_changes_creates_db_alerts(self, db_session):
        """AlertEngine.process_changes creates Alert rows in the DB."""
        engine = AlertEngine(db_session=db_session)
        changes = {
            "entered_hot": ["uid_100"],
            "dropped_out": ["uid_200"],
            "rank_changed": [
                {"uid": "uid_300", "prev_rank": 5, "curr_rank": 20},
            ],
        }

        alerts = await engine.process_changes(changes)
        assert len(alerts) == 3

        db_alerts = db_session.query(Alert).filter(Alert.status == "pending").all()
        assert len(db_alerts) == 3
        types = {a.alert_type for a in db_alerts}
        assert types == {"entered_hot", "dropped_out", "rank_drop"}


# ---------------------------------------------------------------------------
# Test 4: AlertEngine resolve_alert updates DB status
# ---------------------------------------------------------------------------

class TestAlertEngineResolve:
    async def test_resolve_alert_updates_status(self, db_session):
        """resolve_alert sets alert status in DB and returns True."""
        engine = AlertEngine(db_session=db_session)

        # Create an alert via process_changes
        alerts = await engine.process_changes({
            "entered_hot": ["uid_400"],
            "dropped_out": [],
            "rank_changed": [],
        })
        alert_id = alerts[0].id

        result = await engine.resolve_alert(alert_id, "confirmed")
        assert result is True

        db_alert = db_session.query(Alert).filter(Alert.id == alert_id).first()
        assert db_alert.status == "confirmed"


# ---------------------------------------------------------------------------
# Test 5: MonitorOrchestrator iteration with real AlertEngine + real DB
# ---------------------------------------------------------------------------

class TestMonitorIterationWithRealAlertEngine:
    async def test_iteration_creates_alerts_in_db(self, db_session):
        """One monitoring iteration with a real AlertEngine persists alerts
        to the DB when changes are detected, and broadcasts via WS."""

        # Real AlertEngine with DB
        alert_engine = AlertEngine(db_session=db_session)
        ws_manager = MagicMock()
        ws_manager.broadcast = AsyncMock()

        # Mock fetcher, tracker, analyzer
        fetcher = MagicMock()
        comments = [make_comment_dto()]
        fetcher.fetch_comments = AsyncMock(return_value=comments)

        tracker = MagicMock()
        tracker.get_team_uids.return_value = ["uid_001"]
        tracker.track_comments.return_value = {}
        tracker.get_member_grid_data.return_value = []

        analyzer = MagicMock()
        analyzer.analyze.return_value = comments
        curr_status = [{"uid": "uid_001", "is_hot": True, "rank": 1}]
        analyzer.get_team_hot_status.return_value = curr_status
        analyzer.detect_changes.return_value = {
            "entered_hot": ["uid_001"],
            "dropped_out": [],
            "rank_changed": [],
        }

        # Mock action_executor and anti_detection
        action_executor = MagicMock()
        anti_detection = MagicMock()

        orch = MonitorOrchestrator(
            client=MagicMock(),
            anti_detection=anti_detection,
            fetcher=fetcher,
            analyzer=analyzer,
            tracker=tracker,
            alert_engine=alert_engine,
            action_executor=action_executor,
            ws_manager=ws_manager,
            db_session=db_session,
        )

        await orch._run_single_iteration(WEIBO_URL)

        # Alert should be persisted in DB
        db_alerts = db_session.query(Alert).filter(Alert.status == "pending").all()
        assert len(db_alerts) == 1
        assert db_alerts[0].alert_type == "entered_hot"

        # WS should have broadcast alert_new
        broadcast_types = [c.args[0] for c in ws_manager.broadcast.call_args_list]
        assert "alert_new" in broadcast_types


# ---------------------------------------------------------------------------
# Test 6: MonitorOrchestrator execute_alert_action with real DB
# ---------------------------------------------------------------------------

class TestExecuteAlertActionWithDB:
    async def test_fetches_cookies_from_account_table(self, db_session):
        """execute_alert_action queries the Account table for cookies and
        passes them to batch_like."""

        # Set up DB: session + accounts + alert
        session = CompetitionSession(
            target_weibo_url=WEIBO_URL,
            target_weibo_mid="5056360400000000",
            status="running",
            total_comments=0,
        )
        db_session.add(session)
        db_session.commit()

        acc1 = Account(
            weibo_uid="uid_a", nickname="userA",
            cookie_json="cookieA=data", status="active",
        )
        acc2 = Account(
            weibo_uid="uid_b", nickname="userB",
            cookie_json="cookieB=data", status="active",
        )
        db_session.add_all([acc1, acc2])
        db_session.commit()

        alert = Alert(
            session_id=session.id, account_uid="uid_a",
            comment_id=42, alert_type="dropped_out",
            message="test", status="pending",
        )
        db_session.add(alert)
        db_session.commit()

        # Real AlertEngine, mocked everything else
        alert_engine = AlertEngine(db_session=db_session)
        action_executor = MagicMock()
        action_executor.batch_like = AsyncMock(return_value=[
            {"uid": "uid_a", "success": True, "error_msg": None},
        ])
        action_executor.batch_comment = AsyncMock(return_value=[])
        ws_manager = MagicMock()
        ws_manager.broadcast = AsyncMock()

        orch = MonitorOrchestrator(
            client=MagicMock(),
            anti_detection=MagicMock(),
            fetcher=MagicMock(),
            analyzer=MagicMock(),
            tracker=MagicMock(),
            alert_engine=alert_engine,
            action_executor=action_executor,
            ws_manager=ws_manager,
            db_session=db_session,
        )

        result = await orch.execute_alert_action(alert.id, "nice", [acc1.id, acc2.id])

        # batch_like called with cookies from DB
        call_args = action_executor.batch_like.call_args
        cookies = call_args[0][1]
        assert len(cookies) == 2
        uids = [c[0] for c in cookies]
        assert "uid_a" in uids
        assert "uid_b" in uids

        assert result["resolved"] is True


# ---------------------------------------------------------------------------
# Test 7: ActionExecutor like_comment with real DB logging
# ---------------------------------------------------------------------------

class TestActionExecutorDBLogging:
    async def test_like_comment_creates_actionlog(self, db_session):
        """like_comment logs success to ActionLog when db_session is provided."""
        mock_client = MagicMock()
        mock_client._post = AsyncMock(return_value={"ok": 1})

        executor = ActionExecutor(
            client=mock_client,
            anti_detection=AntiDetectionEngine(),
            db_session=db_session,
        )

        result = await executor.like_comment(123, "cookie=abc", uid="uid_777")

        assert result["success"] is True
        logs = db_session.query(ActionLog).all()
        assert len(logs) == 1
        assert logs[0].account_uid == "uid_777"
        assert logs[0].action_type == "like"
        assert logs[0].status == "success"
        assert logs[0].target_comment_id == "123"


# ---------------------------------------------------------------------------
# Test 8: ActionExecutor comment limit enforcement with real DB
# ---------------------------------------------------------------------------

class TestActionExecutorCommentLimit:
    async def test_post_comment_blocked_at_500(self, db_session):
        """post_comment returns failure without API call when limit reached."""
        session = CompetitionSession(
            target_weibo_url=WEIBO_URL,
            target_weibo_mid="5056360400000000",
            status="running",
            total_comments=500,
        )
        db_session.add(session)
        db_session.commit()

        mock_client = MagicMock()
        mock_client._post = AsyncMock()

        executor = ActionExecutor(
            client=mock_client,
            db_session=db_session,
        )

        result = await executor.post_comment("5056360400000000", "test", "cookie=x")

        assert result["success"] is False
        assert result["comment_id"] is None
        assert "limit" in result["error_msg"].lower()

        # Client should NOT have been called
        mock_client._post.assert_not_called()


# ---------------------------------------------------------------------------
# Test 9: AntiDetectionEngine.wait_cookie_switch returns 3-8s
# ---------------------------------------------------------------------------

class TestCookieSwitchDelay:
    async def test_wait_cookie_switch_range(self):
        """wait_cookie_switch delegates to DelayManager.cookie_switch_delay
        and returns a value in the 3-8 second range."""
        engine = AntiDetectionEngine()
        with patch.object(asyncio, "sleep", new_callable=AsyncMock):
            for _ in range(20):
                d = await engine.wait_cookie_switch()
                assert 3 <= d <= 8


# ---------------------------------------------------------------------------
# Test 10: CookiePool rotation after MAX_USES_PER_COOKIE=8
# ---------------------------------------------------------------------------

class TestCookiePoolRotationAt8:
    def test_rotation_after_8_uses(self):
        """Monitor cookie rotates to the next cookie after exactly 8 uses,
        confirming MAX_USES_PER_COOKIE was tuned from 10 to 8."""
        pool = CookiePool()
        pool.add_cookie("uid1", "cookie_str_1", tier="monitor")
        pool.add_cookie("uid2", "cookie_str_2", tier="monitor")

        # First 8 calls should return uid1's cookie
        for i in range(CookiePool.MAX_USES_PER_COOKIE):
            c = pool.get_monitor_cookie()
            assert c == "cookie_str_1", f"call {i + 1} should return cookie_str_1"

        # 9th call should have rotated to uid2
        assert pool.get_monitor_cookie() == "cookie_str_2"

    async def test_wait_cookie_switch_calls_asyncio_sleep(self):
        """wait_cookie_switch actually awaits asyncio.sleep."""
        engine = AntiDetectionEngine()
        with patch.object(asyncio, "sleep", new_callable=AsyncMock) as mock_sleep:
            await engine.wait_cookie_switch()
            mock_sleep.assert_awaited_once()
