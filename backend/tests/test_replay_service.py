"""TDD tests for ReplayService — replay and review of past competition sessions.

Tests are written FIRST (before implementation) following TDD discipline.
pytest async mode=auto — no @pytest.mark.asyncio needed.
"""

from datetime import datetime, timedelta

import pytest

from app.models import (
    ActionLog,
    Alert,
    Comment,
    CommentSnapshot,
    CompetitionSession,
)
from app.services.replay_service import ReplayService


# ─── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def service(db_session):
    """ReplayService with real DB session."""
    return ReplayService(db_session=db_session)


@pytest.fixture
def service_no_db():
    """ReplayService with no DB session (for edge-case testing)."""
    return ReplayService(db_session=None)


@pytest.fixture
def session_data(db_session):
    """Create a complete set of test data: session, comments, snapshots, alerts, actions."""
    now = datetime.utcnow()

    # Create session
    session = CompetitionSession(
        target_weibo_url="https://weibo.com/1234567890/abc123",
        target_weibo_mid="3501756485200075",
        started_at=now - timedelta(hours=2),
        ended_at=now - timedelta(hours=1),
        total_comments=100,
        status="ended",
    )
    db_session.add(session)
    db_session.flush()

    # Create comments (team + non-team)
    comment1 = Comment(
        weibo_comment_id="wc_001",
        weibo_post_id="3501756485200075",
        user_uid="uid_alpha",
        user_name="Player Alpha",
        content="Great post!",
        like_count=50,
        created_at=now - timedelta(hours=3),
        fetched_at=now - timedelta(hours=2),
    )
    comment2 = Comment(
        weibo_comment_id="wc_002",
        weibo_post_id="3501756485200075",
        user_uid="uid_bravo",
        user_name="Player Bravo",
        content="Nice work!",
        like_count=30,
        created_at=now - timedelta(hours=3),
        fetched_at=now - timedelta(hours=2),
    )
    db_session.add_all([comment1, comment2])
    db_session.flush()

    # Create snapshots at two timestamps
    snap_time1 = now - timedelta(hours=2)
    snap_time2 = now - timedelta(hours=1, minutes=30)

    snap1 = CommentSnapshot(
        comment_id=comment1.id,
        like_count=50,
        rank=1,
        is_hot=True,
        is_team_member=True,
        snapshot_at=snap_time1,
    )
    snap2 = CommentSnapshot(
        comment_id=comment2.id,
        like_count=30,
        rank=2,
        is_hot=False,
        is_team_member=False,
        snapshot_at=snap_time1,
    )
    snap3 = CommentSnapshot(
        comment_id=comment1.id,
        like_count=80,
        rank=1,
        is_hot=True,
        is_team_member=True,
        snapshot_at=snap_time2,
    )
    snap4 = CommentSnapshot(
        comment_id=comment2.id,
        like_count=40,
        rank=2,
        is_hot=True,
        is_team_member=False,
        snapshot_at=snap_time2,
    )
    db_session.add_all([snap1, snap2, snap3, snap4])
    db_session.flush()

    # Create alerts
    alert1 = Alert(
        session_id=session.id,
        account_uid="uid_alpha",
        comment_id=comment1.id,
        alert_type="rank_drop",
        message="Rank dropped from 1 to 3",
        status="confirmed",
        created_at=now - timedelta(hours=1, minutes=30),
    )
    alert2 = Alert(
        session_id=session.id,
        account_uid="uid_bravo",
        comment_id=comment2.id,
        alert_type="low_likes",
        message="Low like count detected",
        status="pending",
        created_at=now - timedelta(hours=1, minutes=15),
    )
    db_session.add_all([alert1, alert2])
    db_session.flush()

    # Create action logs (within session time range)
    action1 = ActionLog(
        account_uid="uid_alpha",
        action_type="like",
        target_comment_id="wc_001",
        content=None,
        status="success",
        created_at=now - timedelta(hours=1, minutes=45),
    )
    action2 = ActionLog(
        account_uid="uid_bravo",
        action_type="comment",
        target_comment_id="wc_002",
        content="Keep it up!",
        status="success",
        created_at=now - timedelta(hours=1, minutes=30),
    )
    action3 = ActionLog(
        account_uid="uid_alpha",
        action_type="reply",
        target_comment_id="wc_001",
        content="Thanks!",
        status="failed",
        created_at=now - timedelta(hours=1, minutes=10),
    )
    db_session.add_all([action1, action2, action3])
    db_session.commit()

    return {
        "session": session,
        "comments": [comment1, comment2],
        "snapshots": [snap1, snap2, snap3, snap4],
        "alerts": [alert1, alert2],
        "actions": [action1, action2, action3],
    }


# ─── get_sessions ──────────────────────────────────────────────────────────────


class TestGetSessions:
    async def test_returns_list_of_sessions(self, service, session_data):
        result = await service.get_sessions()

        assert isinstance(result, list)
        assert len(result) >= 1

        entry = result[0]
        assert "id" in entry
        assert "target_weibo_url" in entry
        assert "target_weibo_mid" in entry
        assert "started_at" in entry
        assert "ended_at" in entry
        assert "total_comments" in entry
        assert "status" in entry

    async def test_returns_correct_session_data(self, service, session_data):
        result = await service.get_sessions()
        session = session_data["session"]

        matching = [s for s in result if s["id"] == session.id]
        assert len(matching) == 1
        assert matching[0]["target_weibo_url"] == session.target_weibo_url
        assert matching[0]["status"] == "ended"
        assert matching[0]["total_comments"] == 100

    async def test_empty_db_returns_empty_list(self, service, db_session):
        result = await service.get_sessions()
        assert result == []

    async def test_none_db_returns_empty_list(self, service_no_db):
        result = await service_no_db.get_sessions()
        assert result == []


# ─── get_session_timeline ─────────────────────────────────────────────────────


class TestGetSessionTimeline:
    async def test_returns_timeline_with_snapshots(self, service, session_data):
        session = session_data["session"]
        result = await service.get_session_timeline(session.id)

        assert "timeline" in result
        assert isinstance(result["timeline"], list)
        assert len(result["timeline"]) >= 1

    async def test_timeline_entries_have_required_fields(self, service, session_data):
        session = session_data["session"]
        result = await service.get_session_timeline(session.id)

        entry = result["timeline"][0]
        assert "timestamp" in entry
        assert "comments" in entry
        assert isinstance(entry["comments"], list)

    async def test_timeline_comment_has_fields(self, service, session_data):
        session = session_data["session"]
        result = await service.get_session_timeline(session.id)

        if result["timeline"] and result["timeline"][0]["comments"]:
            comment = result["timeline"][0]["comments"][0]
            assert "comment_id" in comment
            assert "rank" in comment
            assert "user_uid" in comment
            assert "user_name" in comment
            assert "like_count" in comment
            assert "is_hot" in comment
            assert "is_team_member" in comment

    async def test_timeline_has_two_snapshot_groups(self, service, session_data):
        session = session_data["session"]
        result = await service.get_session_timeline(session.id)

        # We created snapshots at 2 distinct timestamps
        assert len(result["timeline"]) == 2

    async def test_nonexistent_session_returns_empty(self, service):
        result = await service.get_session_timeline(99999)
        assert result == {"timeline": []}

    async def test_none_db_returns_empty(self, service_no_db):
        result = await service_no_db.get_session_timeline(1)
        assert result == {"timeline": []}


# ─── get_session_alerts ────────────────────────────────────────────────────────


class TestGetSessionAlerts:
    async def test_returns_alerts_for_session(self, service, session_data):
        session = session_data["session"]
        result = await service.get_session_alerts(session.id)

        assert "alerts" in result
        assert isinstance(result["alerts"], list)
        assert len(result["alerts"]) == 2

    async def test_alert_has_required_fields(self, service, session_data):
        session = session_data["session"]
        result = await service.get_session_alerts(session.id)

        alert = result["alerts"][0]
        assert "id" in alert
        assert "alert_type" in alert
        assert "message" in alert
        assert "status" in alert
        assert "account_uid" in alert
        assert "comment_id" in alert
        assert "created_at" in alert

    async def test_nonexistent_session_returns_empty(self, service):
        result = await service.get_session_alerts(99999)
        assert result == {"alerts": []}

    async def test_none_db_returns_empty(self, service_no_db):
        result = await service_no_db.get_session_alerts(1)
        assert result == {"alerts": []}


# ─── get_session_actions ───────────────────────────────────────────────────────


class TestGetSessionActions:
    async def test_returns_actions_in_session_time_range(self, service, session_data):
        session = session_data["session"]
        result = await service.get_session_actions(session.id)

        assert "actions" in result
        assert isinstance(result["actions"], list)
        assert len(result["actions"]) == 3

    async def test_action_has_required_fields(self, service, session_data):
        session = session_data["session"]
        result = await service.get_session_actions(session.id)

        action = result["actions"][0]
        assert "id" in action
        assert "account_uid" in action
        assert "action_type" in action
        assert "target_comment_id" in action
        assert "content" in action
        assert "status" in action
        assert "created_at" in action

    async def test_actions_filtered_by_session_time_range(self, service, db_session):
        """Actions outside the session time range should NOT appear."""
        now = datetime.utcnow()

        session = CompetitionSession(
            target_weibo_url="https://weibo.com/test/test",
            target_weibo_mid="mid_test",
            started_at=now - timedelta(hours=1),
            ended_at=now - timedelta(minutes=30),
            total_comments=10,
            status="ended",
        )
        db_session.add(session)
        db_session.flush()

        # Action within session time range
        in_range = ActionLog(
            account_uid="uid_x",
            action_type="like",
            target_comment_id="c1",
            status="success",
            created_at=now - timedelta(minutes=45),
        )
        # Action outside session time range (before session started)
        out_range = ActionLog(
            account_uid="uid_x",
            action_type="like",
            target_comment_id="c2",
            status="success",
            created_at=now - timedelta(hours=3),
        )
        db_session.add_all([in_range, out_range])
        db_session.commit()

        result = await service.get_session_actions(session.id)
        uids = [a["account_uid"] for a in result["actions"]]
        assert len(result["actions"]) == 1
        assert result["actions"][0]["target_comment_id"] == "c1"

    async def test_nonexistent_session_returns_empty(self, service):
        result = await service.get_session_actions(99999)
        assert result == {"actions": []}

    async def test_none_db_returns_empty(self, service_no_db):
        result = await service_no_db.get_session_actions(1)
        assert result == {"actions": []}


# ─── get_session_summary ───────────────────────────────────────────────────────


class TestGetSessionSummary:
    async def test_returns_summary_with_required_fields(self, service, session_data):
        session = session_data["session"]
        result = await service.get_session_summary(session.id)

        assert "total_comments" in result
        assert "peak_hot_count" in result
        assert "hot_ratio" in result
        assert "action_success_rate" in result
        assert "member_performance" in result

    async def test_total_comments_from_session(self, service, session_data):
        session = session_data["session"]
        result = await service.get_session_summary(session.id)
        assert result["total_comments"] == 100

    async def test_peak_hot_count(self, service, session_data):
        """Peak hot count should be the max hot count across all snapshot timestamps."""
        session = session_data["session"]
        result = await service.get_session_summary(session.id)
        # At snap_time2: both comments are hot → peak_hot_count = 2
        assert result["peak_hot_count"] == 2

    async def test_hot_ratio(self, service, session_data):
        session = session_data["session"]
        result = await service.get_session_summary(session.id)
        # hot_ratio should be between 0 and 1
        assert 0 <= result["hot_ratio"] <= 1

    async def test_action_success_rate(self, service, session_data):
        session = session_data["session"]
        result = await service.get_session_summary(session.id)
        # 3 actions: 2 success, 1 failed → 2/3 ≈ 0.667
        assert abs(result["action_success_rate"] - 2 / 3) < 0.01

    async def test_member_performance(self, service, session_data):
        session = session_data["session"]
        result = await service.get_session_summary(session.id)

        assert isinstance(result["member_performance"], list)
        assert len(result["member_performance"]) >= 1

        member = result["member_performance"][0]
        assert "uid" in member
        assert "name" in member
        assert "like_count" in member
        assert "comment_count" in member
        assert "best_rank" in member

    async def test_nonexistent_session_returns_empty(self, service):
        result = await service.get_session_summary(99999)
        assert result["total_comments"] == 0
        assert result["member_performance"] == []

    async def test_none_db_returns_empty(self, service_no_db):
        result = await service_no_db.get_session_summary(1)
        assert result["total_comments"] == 0
        assert result["member_performance"] == []


# ─── Integration ───────────────────────────────────────────────────────────────


class TestReplayIntegration:
    async def test_full_replay_workflow(self, service, session_data):
        """Test the full replay workflow: sessions → timeline → alerts → actions → summary."""
        session = session_data["session"]

        # 1. List sessions
        sessions = await service.get_sessions()
        assert len(sessions) >= 1

        # 2. Get timeline
        timeline = await service.get_session_timeline(session.id)
        assert len(timeline["timeline"]) == 2

        # 3. Get alerts
        alerts = await service.get_session_alerts(session.id)
        assert len(alerts["alerts"]) == 2

        # 4. Get actions
        actions = await service.get_session_actions(session.id)
        assert len(actions["actions"]) == 3

        # 5. Get summary
        summary = await service.get_session_summary(session.id)
        assert summary["total_comments"] == 100
        assert summary["peak_hot_count"] == 2
