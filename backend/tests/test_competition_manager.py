"""TDD tests for CompetitionManager — comment count controller + competition lifecycle.

Tests are written FIRST (before implementation) following TDD discipline.
pytest async mode=auto — no @pytest.mark.asyncio needed.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models import CompetitionSession
from app.services.competition_manager import CompetitionManager


# ─── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_monitor():
    """A mock MonitorOrchestrator with async start/stop methods."""
    m = MagicMock()
    m.start_monitoring = AsyncMock()
    m.stop_monitoring = AsyncMock()
    return m


@pytest.fixture
def manager(db_session, mock_monitor):
    """CompetitionManager with real DB session and mock monitor."""
    return CompetitionManager(db_session=db_session, monitor_orchestrator=mock_monitor)


@pytest.fixture
def manager_no_monitor(db_session):
    """CompetitionManager with real DB session but no monitor orchestrator."""
    return CompetitionManager(db_session=db_session, monitor_orchestrator=None)


@pytest.fixture
def manager_no_db():
    """CompetitionManager with no DB session (for edge-case testing)."""
    return CompetitionManager(db_session=None, monitor_orchestrator=None)


WEIBO_URL = "https://weibo.com/1234567890/z0JH2lOMb"
EXPECTED_MID = "3501756485200075"


# ─── start_competition ─────────────────────────────────────────────────────────


class TestStartCompetition:
    async def test_creates_session_with_running_status(self, manager, db_session):
        result = await manager.start_competition(WEIBO_URL)

        assert result["status"] == "running"
        assert "session_id" in result

        session = db_session.query(CompetitionSession).first()
        assert session is not None
        assert session.status == "running"
        assert session.target_weibo_url == WEIBO_URL
        assert session.target_weibo_mid == EXPECTED_MID
        assert session.total_comments == 0
        assert session.started_at is not None
        assert session.ended_at is None

    async def test_stores_session_id_as_instance_var(self, manager):
        result = await manager.start_competition(WEIBO_URL)
        assert manager.session_id == result["session_id"]

    async def test_calls_monitor_start(self, manager, mock_monitor):
        await manager.start_competition(WEIBO_URL)
        mock_monitor.start_monitoring.assert_called_once_with(WEIBO_URL)

    async def test_works_without_monitor(self, manager_no_monitor):
        result = await manager_no_monitor.start_competition(WEIBO_URL)
        assert result["status"] == "running"
        assert "session_id" in result

    async def test_with_team_uids(self, manager):
        result = await manager.start_competition(WEIBO_URL, team_uids=["uid1", "uid2"])
        assert result["status"] == "running"

    async def test_raises_when_no_db(self, manager_no_db):
        with pytest.raises(RuntimeError, match="db_session"):
            await manager_no_db.start_competition(WEIBO_URL)


# ─── pause_competition ─────────────────────────────────────────────────────────


class TestPauseCompetition:
    async def test_updates_status_to_paused(self, manager, db_session):
        await manager.start_competition(WEIBO_URL)
        result = await manager.pause_competition()

        assert result["status"] == "paused"

        session = db_session.query(CompetitionSession).first()
        assert session.status == "paused"

    async def test_calls_monitor_stop(self, manager, mock_monitor):
        await manager.start_competition(WEIBO_URL)
        await manager.pause_competition()
        mock_monitor.stop_monitoring.assert_called_once()

    async def test_works_without_monitor(self, manager_no_monitor):
        await manager_no_monitor.start_competition(WEIBO_URL)
        result = await manager_no_monitor.pause_competition()
        assert result["status"] == "paused"

    async def test_raises_when_no_active_session(self, manager_no_monitor):
        with pytest.raises(RuntimeError, match="No active"):
            await manager_no_monitor.pause_competition()


# ─── resume_competition ────────────────────────────────────────────────────────


class TestResumeCompetition:
    async def test_updates_status_to_running(self, manager, db_session):
        await manager.start_competition(WEIBO_URL)
        await manager.pause_competition()
        result = await manager.resume_competition()

        assert result["status"] == "running"

        session = db_session.query(CompetitionSession).first()
        assert session.status == "running"

    async def test_calls_monitor_start_with_url(self, manager, mock_monitor):
        await manager.start_competition(WEIBO_URL)
        await manager.pause_competition()
        mock_monitor.start_monitoring.reset_mock()
        await manager.resume_competition()
        mock_monitor.start_monitoring.assert_called_once_with(WEIBO_URL)

    async def test_works_without_monitor(self, manager_no_monitor):
        await manager_no_monitor.start_competition(WEIBO_URL)
        await manager_no_monitor.pause_competition()
        result = await manager_no_monitor.resume_competition()
        assert result["status"] == "running"

    async def test_raises_when_no_active_session(self, manager_no_monitor):
        with pytest.raises(RuntimeError, match="No active"):
            await manager_no_monitor.resume_competition()


# ─── end_competition ───────────────────────────────────────────────────────────


class TestEndCompetition:
    async def test_updates_status_to_ended(self, manager, db_session):
        await manager.start_competition(WEIBO_URL)
        result = await manager.end_competition()

        assert result["status"] == "ended"
        assert "total_comments" in result
        assert result["total_comments"] == 0

        session = db_session.query(CompetitionSession).first()
        assert session.status == "ended"
        assert session.ended_at is not None

    async def test_returns_total_comments(self, manager, db_session):
        await manager.start_competition(WEIBO_URL)
        # Increment a few times
        for _ in range(5):
            await manager.increment_comment_count()

        result = await manager.end_competition()
        assert result["total_comments"] == 5

    async def test_calls_monitor_stop(self, manager, mock_monitor):
        await manager.start_competition(WEIBO_URL)
        mock_monitor.stop_monitoring.reset_mock()
        await manager.end_competition()
        mock_monitor.stop_monitoring.assert_called_once()

    async def test_works_without_monitor(self, manager_no_monitor):
        await manager_no_monitor.start_competition(WEIBO_URL)
        result = await manager_no_monitor.end_competition()
        assert result["status"] == "ended"

    async def test_raises_when_no_active_session(self, manager_no_monitor):
        with pytest.raises(RuntimeError, match="No active"):
            await manager_no_monitor.end_competition()


# ─── get_status ─────────────────────────────────────────────────────────────────


class TestGetStatus:
    async def test_returns_idle_when_no_session(self, manager_no_monitor):
        result = await manager_no_monitor.get_status()
        assert result == {"status": "idle"}

    async def test_returns_running_status(self, manager):
        await manager.start_competition(WEIBO_URL)
        result = await manager.get_status()

        assert result["status"] == "running"
        assert result["session_id"] == manager.session_id
        assert result["total_comments"] == 0
        assert result["remaining_quota"] == 500
        assert result["started_at"] is not None
        assert result["target_weibo_url"] == WEIBO_URL

    async def test_returns_paused_status(self, manager):
        await manager.start_competition(WEIBO_URL)
        await manager.pause_competition()
        result = await manager.get_status()
        assert result["status"] == "paused"

    async def test_reflects_comment_count(self, manager):
        await manager.start_competition(WEIBO_URL)
        for _ in range(10):
            await manager.increment_comment_count()

        result = await manager.get_status()
        assert result["total_comments"] == 10
        assert result["remaining_quota"] == 490


# ─── increment_comment_count ───────────────────────────────────────────────────


class TestIncrementCommentCount:
    async def test_increments_count(self, manager, db_session):
        await manager.start_competition(WEIBO_URL)

        result = await manager.increment_comment_count()
        assert result is True

        session = db_session.query(CompetitionSession).first()
        assert session.total_comments == 1

    async def test_multiple_increments(self, manager, db_session):
        await manager.start_competition(WEIBO_URL)

        for _ in range(100):
            result = await manager.increment_comment_count()
            assert result is True

        session = db_session.query(CompetitionSession).first()
        assert session.total_comments == 100

    async def test_returns_false_at_limit(self, manager):
        await manager.start_competition(WEIBO_URL)

        # Increment to 500
        for _ in range(500):
            await manager.increment_comment_count()

        # 501st should fail
        result = await manager.increment_comment_count()
        assert result is False

    async def test_returns_false_without_session(self, manager_no_monitor):
        result = await manager_no_monitor.increment_comment_count()
        assert result is False


# ─── get_remaining_quota ────────────────────────────────────────────────────────


class TestGetRemainingQuota:
    async def test_returns_500_at_start(self, manager):
        await manager.start_competition(WEIBO_URL)
        assert await manager.get_remaining_quota() == 500

    async def test_decreases_with_increments(self, manager):
        await manager.start_competition(WEIBO_URL)
        for _ in range(50):
            await manager.increment_comment_count()
        assert await manager.get_remaining_quota() == 450

    async def test_returns_0_at_limit(self, manager):
        await manager.start_competition(WEIBO_URL)
        for _ in range(500):
            await manager.increment_comment_count()
        assert await manager.get_remaining_quota() == 0

    async def test_returns_0_without_session(self, manager_no_monitor):
        assert await manager_no_monitor.get_remaining_quota() == 0


# ─── can_post_comment ──────────────────────────────────────────────────────────


class TestCanPostComment:
    async def test_true_at_start(self, manager):
        await manager.start_competition(WEIBO_URL)
        assert await manager.can_post_comment() is True

    async def test_false_at_limit(self, manager):
        await manager.start_competition(WEIBO_URL)
        for _ in range(500):
            await manager.increment_comment_count()
        assert await manager.can_post_comment() is False

    async def test_false_without_session(self, manager_no_monitor):
        assert await manager_no_monitor.can_post_comment() is False

    async def test_true_just_below_limit(self, manager):
        await manager.start_competition(WEIBO_URL)
        for _ in range(499):
            await manager.increment_comment_count()
        assert await manager.can_post_comment() is True


# ─── _COMMENT_LIMIT constant ───────────────────────────────────────────────────


class TestCommentLimit:
    def test_class_constant_exists(self):
        assert hasattr(CompetitionManager, "_COMMENT_LIMIT")
        assert CompetitionManager._COMMENT_LIMIT == 500


# ─── Full lifecycle integration ────────────────────────────────────────────────


class TestFullLifecycle:
    async def test_start_pause_resume_end(self, manager, db_session):
        # Start
        result = await manager.start_competition(WEIBO_URL)
        assert result["status"] == "running"

        # Pause
        result = await manager.pause_competition()
        assert result["status"] == "paused"

        # Resume
        result = await manager.resume_competition()
        assert result["status"] == "running"

        # End
        result = await manager.end_competition()
        assert result["status"] == "ended"

        session = db_session.query(CompetitionSession).first()
        assert session.status == "ended"
        assert session.ended_at is not None

    async def test_lifecycle_with_comments(self, manager, db_session):
        await manager.start_competition(WEIBO_URL)

        # Post 200 comments
        for _ in range(200):
            await manager.increment_comment_count()

        await manager.pause_competition()
        await manager.resume_competition()

        # Post 200 more
        for _ in range(200):
            await manager.increment_comment_count()

        result = await manager.end_competition()
        assert result["total_comments"] == 400
        assert await manager.get_remaining_quota() == 100  # 500 - 400

    async def test_monitor_calls_throughout_lifecycle(self, manager, mock_monitor):
        await manager.start_competition(WEIBO_URL)
        assert mock_monitor.start_monitoring.call_count == 1

        await manager.pause_competition()
        assert mock_monitor.stop_monitoring.call_count == 1

        await manager.resume_competition()
        assert mock_monitor.start_monitoring.call_count == 2

        await manager.end_competition()
        assert mock_monitor.stop_monitoring.call_count == 2
