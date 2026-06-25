"""CRUD tests for all models using in-memory SQLite."""

from datetime import datetime

from app.models import Account, ActionLog, Alert, Comment, CommentSnapshot, CompetitionSession


# ─── init_db / table creation ───────────────────────────────────────────────

def test_tables_created(db_session):
    """All six tables should exist and accept inserts."""
    account = Account(weibo_uid="123456", nickname="tester")
    db_session.add(account)
    db_session.commit()

    assert account.id is not None, "Account should get an ID after commit"


# ─── Account CRUD ────────────────────────────────────────────────────────────

def test_account_create(db_session):
    account = Account(
        weibo_uid="111111",
        nickname="alice",
        cookie_json='{"key": "val"}',
        status="active",
        avatar_url="https://example.com/a.png",
    )
    db_session.add(account)
    db_session.commit()

    assert account.id is not None
    assert account.weibo_uid == "111111"
    assert account.nickname == "alice"
    assert account.status == "active"
    assert account.created_at is not None


def test_account_read(db_session):
    account = Account(weibo_uid="222222", nickname="bob")
    db_session.add(account)
    db_session.commit()

    found = db_session.query(Account).filter_by(weibo_uid="222222").first()
    assert found is not None
    assert found.nickname == "bob"


def test_account_update(db_session):
    account = Account(weibo_uid="333333", nickname="carol", status="active")
    db_session.add(account)
    db_session.commit()

    account.status = "expired"
    account.nickname = "carol_updated"
    db_session.commit()

    refreshed = db_session.query(Account).filter_by(weibo_uid="333333").first()
    assert refreshed.status == "expired"
    assert refreshed.nickname == "carol_updated"


def test_account_delete(db_session):
    account = Account(weibo_uid="444444", nickname="dave")
    db_session.add(account)
    db_session.commit()

    db_session.delete(account)
    db_session.commit()

    assert db_session.query(Account).filter_by(weibo_uid="444444").first() is None


# ─── Comment CRUD ────────────────────────────────────────────────────────────

def test_comment_create(db_session):
    comment = Comment(
        weibo_comment_id="cmt_001",
        weibo_post_id="post_001",
        user_uid="555555",
        user_name="commenter1",
        content="Great post!",
        like_count=42,
    )
    db_session.add(comment)
    db_session.commit()

    assert comment.id is not None
    assert comment.like_count == 42
    assert comment.fetched_at is not None


def test_comment_read(db_session):
    comment = Comment(
        weibo_comment_id="cmt_002",
        weibo_post_id="post_002",
        user_uid="666666",
        user_name="commenter2",
        content="Nice",
    )
    db_session.add(comment)
    db_session.commit()

    found = db_session.query(Comment).filter_by(weibo_comment_id="cmt_002").first()
    assert found is not None
    assert found.user_name == "commenter2"
    assert found.like_count == 0  # default


def test_comment_update(db_session):
    comment = Comment(
        weibo_comment_id="cmt_003",
        weibo_post_id="post_003",
        user_uid="777777",
        user_name="commenter3",
        content="Old content",
        like_count=10,
    )
    db_session.add(comment)
    db_session.commit()

    comment.like_count = 100
    comment.content = "Updated content"
    db_session.commit()

    refreshed = db_session.query(Comment).filter_by(weibo_comment_id="cmt_003").first()
    assert refreshed.like_count == 100
    assert refreshed.content == "Updated content"


def test_comment_delete(db_session):
    comment = Comment(
        weibo_comment_id="cmt_004",
        weibo_post_id="post_004",
        user_uid="888888",
        user_name="commenter4",
    )
    db_session.add(comment)
    db_session.commit()

    db_session.delete(comment)
    db_session.commit()

    assert db_session.query(Comment).filter_by(weibo_comment_id="cmt_004").first() is None


# ─── CommentSnapshot CRUD ───────────────────────────────────────────────────

def test_comment_snapshot_create(db_session):
    comment = Comment(
        weibo_comment_id="cmt_s1",
        weibo_post_id="post_s1",
        user_uid="uid_s1",
        user_name="snap_user",
    )
    db_session.add(comment)
    db_session.commit()

    snap = CommentSnapshot(
        comment_id=comment.id,
        like_count=50,
        rank=3,
        is_hot=True,
        is_team_member=False,
    )
    db_session.add(snap)
    db_session.commit()

    assert snap.id is not None
    assert snap.like_count == 50
    assert snap.is_hot is True
    assert snap.snapshot_at is not None


def test_comment_snapshot_multiple(db_session):
    """Multiple snapshots for the same comment (time-series)."""
    comment = Comment(
        weibo_comment_id="cmt_s2",
        weibo_post_id="post_s2",
        user_uid="uid_s2",
        user_name="snap_user2",
    )
    db_session.add(comment)
    db_session.commit()

    for i in range(5):
        db_session.add(CommentSnapshot(
            comment_id=comment.id,
            like_count=10 * i,
            rank=i + 1,
        ))
    db_session.commit()

    snaps = db_session.query(CommentSnapshot).filter_by(comment_id=comment.id).all()
    assert len(snaps) == 5


# ─── Alert CRUD ──────────────────────────────────────────────────────────────

def test_alert_create(db_session):
    alert = Alert(
        alert_type="rank_drop",
        message="Comment dropped from rank 2 to rank 8",
        status="pending",
    )
    db_session.add(alert)
    db_session.commit()

    assert alert.id is not None
    assert alert.alert_type == "rank_drop"
    assert alert.created_at is not None


def test_alert_read(db_session):
    alert = Alert(alert_type="dropped_out", message="Comment disappeared", status="pending")
    db_session.add(alert)
    db_session.commit()

    found = db_session.query(Alert).filter_by(alert_type="dropped_out").first()
    assert found is not None
    assert found.message == "Comment disappeared"


def test_alert_update(db_session):
    alert = Alert(alert_type="low_likes", message="Low likes", status="pending")
    db_session.add(alert)
    db_session.commit()

    alert.status = "executed"
    db_session.commit()

    refreshed = db_session.query(Alert).filter_by(alert_type="low_likes").first()
    assert refreshed.status == "executed"


def test_alert_delete(db_session):
    alert = Alert(alert_type="rank_drop", message="temp", status="dismissed")
    db_session.add(alert)
    db_session.commit()

    db_session.delete(alert)
    db_session.commit()

    assert db_session.query(Alert).filter_by(alert_type="rank_drop").first() is None


# ─── ActionLog CRUD ──────────────────────────────────────────────────────────

def test_action_log_create(db_session):
    log = ActionLog(
        account_uid="999999",
        action_type="like",
        target_comment_id="cmt_target_1",
        status="success",
        response='{"ok": true}',
    )
    db_session.add(log)
    db_session.commit()

    assert log.id is not None
    assert log.action_type == "like"
    assert log.status == "success"
    assert log.created_at is not None


def test_action_log_read(db_session):
    log = ActionLog(
        account_uid="log_uid",
        action_type="reply",
        content="My reply text",
        status="pending",
    )
    db_session.add(log)
    db_session.commit()

    found = db_session.query(ActionLog).filter_by(account_uid="log_uid").first()
    assert found is not None
    assert found.action_type == "reply"
    assert found.content == "My reply text"


def test_action_log_delete(db_session):
    log = ActionLog(account_uid="del_uid", action_type="comment", status="failed")
    db_session.add(log)
    db_session.commit()

    db_session.delete(log)
    db_session.commit()

    assert db_session.query(ActionLog).filter_by(account_uid="del_uid").first() is None


# ─── CompetitionSession CRUD ────────────────────────────────────────────────

def test_session_create(db_session):
    session = CompetitionSession(
        target_weibo_url="https://weibo.com/123456/AbCdEfG",
        target_weibo_mid="AbCdEfG",
        status="running",
    )
    db_session.add(session)
    db_session.commit()

    assert session.id is not None
    assert session.status == "running"
    assert session.total_comments == 0  # default
    assert session.started_at is not None
    assert session.ended_at is None


def test_session_read(db_session):
    session = CompetitionSession(
        target_weibo_url="https://weibo.com/999/X",
        target_weibo_mid="MID_X",
        status="idle",
    )
    db_session.add(session)
    db_session.commit()

    found = db_session.query(CompetitionSession).filter_by(target_weibo_mid="MID_X").first()
    assert found is not None
    assert found.target_weibo_url == "https://weibo.com/999/X"


def test_session_update(db_session):
    session = CompetitionSession(
        target_weibo_url="https://weibo.com/1/Y",
        target_weibo_mid="MID_Y",
        status="running",
    )
    db_session.add(session)
    db_session.commit()

    session.status = "ended"
    session.ended_at = datetime.utcnow()
    session.total_comments = 500
    db_session.commit()

    refreshed = db_session.query(CompetitionSession).filter_by(target_weibo_mid="MID_Y").first()
    assert refreshed.status == "ended"
    assert refreshed.ended_at is not None
    assert refreshed.total_comments == 500


def test_session_delete(db_session):
    session = CompetitionSession(
        target_weibo_url="https://weibo.com/2/Z",
        target_weibo_mid="MID_Z",
        status="paused",
    )
    db_session.add(session)
    db_session.commit()

    db_session.delete(session)
    db_session.commit()

    assert db_session.query(CompetitionSession).filter_by(target_weibo_mid="MID_Z").first() is None
