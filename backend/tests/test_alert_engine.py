"""Tests for AlertEngine — alert creation, lifecycle, and WS broadcast."""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.alert import Alert
from app.services.alert_engine import AlertEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mock_ws_manager() -> MagicMock:
    """Create a mock WSManager with an async broadcast method."""
    mgr = MagicMock()
    mgr.broadcast = AsyncMock()
    return mgr


def make_changes(
    entered_hot: list[str] | None = None,
    dropped_out: list[str] | None = None,
    rank_changed: list[dict] | None = None,
) -> dict:
    """Build a changes dict in detect_changes() output format."""
    return {
        "entered_hot": entered_hot or [],
        "dropped_out": dropped_out or [],
        "rank_changed": rank_changed or [],
    }


# ---------------------------------------------------------------------------
# process_changes — dropped_out
# ---------------------------------------------------------------------------

async def test_process_changes_dropped_out_creates_alert():
    """dropped_out uid → creates pending dropped_out alert."""
    engine = AlertEngine()
    changes = make_changes(dropped_out=["uid_001"])

    alerts = await engine.process_changes(changes)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.alert_type == "dropped_out"
    assert alert.status == "pending"
    assert alert.account_uid == "uid_001"
    assert "uid_001" in alert.message
    assert "掉出热评" in alert.message


# ---------------------------------------------------------------------------
# process_changes — entered_hot
# ---------------------------------------------------------------------------

async def test_process_changes_entered_hot_creates_alert():
    """entered_hot uid → creates pending entered_hot alert."""
    engine = AlertEngine()
    changes = make_changes(entered_hot=["uid_002"])

    alerts = await engine.process_changes(changes)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.alert_type == "entered_hot"
    assert alert.status == "pending"
    assert alert.account_uid == "uid_002"
    assert "uid_002" in alert.message
    assert "进入热评" in alert.message


# ---------------------------------------------------------------------------
# process_changes — rank_drop > 10
# ---------------------------------------------------------------------------

async def test_process_changes_rank_drop_gt_10_creates_alert():
    """rank drop > 10 → creates rank_drop alert."""
    engine = AlertEngine()
    changes = make_changes(
        rank_changed=[{"uid": "uid_003", "prev_rank": 5, "curr_rank": 20}]
    )

    alerts = await engine.process_changes(changes)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.alert_type == "rank_drop"
    assert alert.status == "pending"
    assert alert.account_uid == "uid_003"
    assert "15" in alert.message  # 20 - 5 = 15


# ---------------------------------------------------------------------------
# process_changes — rank_drop <= 10 (no alert)
# ---------------------------------------------------------------------------

async def test_process_changes_rank_drop_le_10_no_alert():
    """rank drop <= 10 → no alert created."""
    engine = AlertEngine()
    changes = make_changes(
        rank_changed=[{"uid": "uid_004", "prev_rank": 5, "curr_rank": 15}]
    )

    alerts = await engine.process_changes(changes)

    assert len(alerts) == 0


async def test_process_changes_rank_drop_exactly_10_no_alert():
    """rank drop exactly 10 → no alert (threshold is > 10)."""
    engine = AlertEngine()
    changes = make_changes(
        rank_changed=[{"uid": "uid_004b", "prev_rank": 1, "curr_rank": 11}]
    )

    alerts = await engine.process_changes(changes)

    assert len(alerts) == 0


# ---------------------------------------------------------------------------
# process_changes — empty changes
# ---------------------------------------------------------------------------

async def test_process_changes_empty_changes_returns_empty():
    """Empty changes dict → returns empty list."""
    engine = AlertEngine()
    alerts = await engine.process_changes(make_changes())

    assert alerts == []


# ---------------------------------------------------------------------------
# process_changes — multiple changes
# ---------------------------------------------------------------------------

async def test_process_changes_multiple_creates_multiple_alerts():
    """Multiple changes → creates multiple alerts in order."""
    engine = AlertEngine()
    changes = make_changes(
        dropped_out=["uid_a", "uid_b"],
        entered_hot=["uid_c"],
        rank_changed=[{"uid": "uid_d", "prev_rank": 1, "curr_rank": 50}],
    )

    alerts = await engine.process_changes(changes)

    assert len(alerts) == 4
    types = [a.alert_type for a in alerts]
    assert types.count("dropped_out") == 2
    assert types.count("entered_hot") == 1
    assert types.count("rank_drop") == 1


# ---------------------------------------------------------------------------
# process_changes — DB persistence
# ---------------------------------------------------------------------------

async def test_process_changes_persists_to_db(db_session):
    """When db_session provided, alerts are persisted with IDs."""
    engine = AlertEngine(db_session=db_session)
    changes = make_changes(dropped_out=["uid_persist"])

    alerts = await engine.process_changes(changes)

    assert len(alerts) == 1
    assert alerts[0].id is not None  # DB assigned an ID

    # Query DB directly to verify.
    db_alerts = db_session.query(Alert).all()
    assert len(db_alerts) == 1
    assert db_alerts[0].account_uid == "uid_persist"
    assert db_alerts[0].status == "pending"


# ---------------------------------------------------------------------------
# process_changes — no db_session (in-memory only)
# ---------------------------------------------------------------------------

async def test_process_changes_no_db_session_returns_alerts():
    """Without db_session, Alert objects are returned but not persisted."""
    engine = AlertEngine()
    changes = make_changes(dropped_out=["uid_mem"])

    alerts = await engine.process_changes(changes)

    assert len(alerts) == 1
    assert alerts[0].account_uid == "uid_mem"
    assert alerts[0].id is None  # not persisted


# ---------------------------------------------------------------------------
# process_changes — WS broadcast
# ---------------------------------------------------------------------------

async def test_process_changes_broadcasts_alert_new():
    """When ws_manager provided, broadcast('alert_new', ...) is called per alert."""
    ws = make_mock_ws_manager()
    engine = AlertEngine(ws_manager=ws)
    changes = make_changes(dropped_out=["uid_ws1"], entered_hot=["uid_ws2"])

    alerts = await engine.process_changes(changes)

    assert ws.broadcast.call_count == 2
    # Check first call
    first_call_args = ws.broadcast.call_args_list[0]
    assert first_call_args[0][0] == "alert_new"
    data = first_call_args[0][1]
    assert data["alert_type"] == "dropped_out"
    assert data["account_uid"] == "uid_ws1"
    assert data["status"] == "pending"


# ---------------------------------------------------------------------------
# process_changes — no ws_manager (no crash)
# ---------------------------------------------------------------------------

async def test_process_changes_no_ws_manager_no_crash():
    """Without ws_manager, process_changes still works without error."""
    engine = AlertEngine()
    changes = make_changes(dropped_out=["uid_no_ws"])

    alerts = await engine.process_changes(changes)

    assert len(alerts) == 1


# ---------------------------------------------------------------------------
# get_pending_alerts — returns pending from DB
# ---------------------------------------------------------------------------

def test_get_pending_alerts_returns_pending(db_session):
    """get_pending_alerts returns alerts with status='pending'."""
    db_session.add(Alert(alert_type="dropped_out", status="pending", account_uid="u1"))
    db_session.add(Alert(alert_type="entered_hot", status="pending", account_uid="u2"))
    db_session.add(Alert(alert_type="rank_drop", status="confirmed", account_uid="u3"))
    db_session.commit()

    engine = AlertEngine(db_session=db_session)
    pending = engine.get_pending_alerts()

    assert len(pending) == 2
    uids = {a.account_uid for a in pending}
    assert uids == {"u1", "u2"}


# ---------------------------------------------------------------------------
# get_pending_alerts — no db_session returns empty
# ---------------------------------------------------------------------------

def test_get_pending_alerts_no_db_session_returns_empty():
    """Without db_session, get_pending_alerts returns []."""
    engine = AlertEngine()
    assert engine.get_pending_alerts() == []


# ---------------------------------------------------------------------------
# get_pending_alerts — excludes non-pending
# ---------------------------------------------------------------------------

def test_get_pending_alerts_excludes_non_pending(db_session):
    """get_pending_alerts excludes confirmed/dismissed/executed alerts."""
    db_session.add(Alert(alert_type="dropped_out", status="pending", account_uid="u1"))
    db_session.add(Alert(alert_type="dropped_out", status="confirmed", account_uid="u2"))
    db_session.add(Alert(alert_type="dropped_out", status="dismissed", account_uid="u3"))
    db_session.add(Alert(alert_type="dropped_out", status="executed", account_uid="u4"))
    db_session.commit()

    engine = AlertEngine(db_session=db_session)
    pending = engine.get_pending_alerts()

    assert len(pending) == 1
    assert pending[0].account_uid == "u1"


# ---------------------------------------------------------------------------
# resolve_alert — updates to confirmed
# ---------------------------------------------------------------------------

async def test_resolve_alert_updates_to_confirmed(db_session):
    """resolve_alert sets status to 'confirmed'."""
    alert = Alert(alert_type="dropped_out", status="pending", account_uid="u1")
    db_session.add(alert)
    db_session.commit()

    engine = AlertEngine(db_session=db_session)
    result = await engine.resolve_alert(alert.id, action="confirmed")

    assert result is True
    db_session.refresh(alert)
    assert alert.status == "confirmed"


# ---------------------------------------------------------------------------
# resolve_alert — updates to dismissed
# ---------------------------------------------------------------------------

async def test_resolve_alert_updates_to_dismissed(db_session):
    """resolve_alert sets status to 'dismissed'."""
    alert = Alert(alert_type="dropped_out", status="pending", account_uid="u2")
    db_session.add(alert)
    db_session.commit()

    engine = AlertEngine(db_session=db_session)
    result = await engine.resolve_alert(alert.id, action="dismissed")

    assert result is True
    db_session.refresh(alert)
    assert alert.status == "dismissed"


# ---------------------------------------------------------------------------
# resolve_alert — broadcasts alert_resolved
# ---------------------------------------------------------------------------

async def test_resolve_alert_broadcasts(db_session):
    """resolve_alert broadcasts 'alert_resolved' via ws_manager."""
    alert = Alert(alert_type="dropped_out", status="pending", account_uid="u3")
    db_session.add(alert)
    db_session.commit()

    ws = make_mock_ws_manager()
    engine = AlertEngine(db_session=db_session, ws_manager=ws)
    await engine.resolve_alert(alert.id, action="confirmed")

    ws.broadcast.assert_awaited_once()
    call_args = ws.broadcast.call_args
    assert call_args[0][0] == "alert_resolved"
    assert call_args[0][1]["alert_id"] == alert.id
    assert call_args[0][1]["status"] == "confirmed"


# ---------------------------------------------------------------------------
# resolve_alert — nonexistent alert returns False
# ---------------------------------------------------------------------------

async def test_resolve_alert_nonexistent_returns_false(db_session):
    """resolve_alert returns False for a nonexistent alert_id."""
    engine = AlertEngine(db_session=db_session)
    result = await engine.resolve_alert(99999, action="confirmed")

    assert result is False


# ---------------------------------------------------------------------------
# resolve_alert — no db_session returns False
# ---------------------------------------------------------------------------

async def test_resolve_alert_no_db_session_returns_false():
    """resolve_alert returns False when db_session is None."""
    engine = AlertEngine()
    result = await engine.resolve_alert(1, action="confirmed")

    assert result is False


# ---------------------------------------------------------------------------
# attach_action — sets status to confirmed
# ---------------------------------------------------------------------------

async def test_attach_action_sets_confirmed(db_session):
    """attach_action sets status to 'confirmed'."""
    alert = Alert(alert_type="dropped_out", status="pending", account_uid="u_a")
    db_session.add(alert)
    db_session.commit()

    engine = AlertEngine(db_session=db_session)
    result = await engine.attach_action(alert.id, "加油!", ["acc1", "acc2"])

    assert result is True
    db_session.refresh(alert)
    assert alert.status == "confirmed"


# ---------------------------------------------------------------------------
# attach_action — stores comment_content and selected_account_ids
# ---------------------------------------------------------------------------

async def test_attach_action_stores_action_data(db_session):
    """attach_action stores comment_content and selected_account_ids in message."""
    original_msg = "组员u_b掉出热评"
    alert = Alert(alert_type="dropped_out", status="pending", account_uid="u_b", message=original_msg)
    db_session.add(alert)
    db_session.commit()

    engine = AlertEngine(db_session=db_session)
    await engine.attach_action(alert.id, "冲冲冲!", ["acc1", "acc2", "acc3"])

    db_session.refresh(alert)
    stored = json.loads(alert.message)
    assert stored["original_message"] == original_msg
    assert stored["comment_content"] == "冲冲冲!"
    assert stored["selected_account_ids"] == ["acc1", "acc2", "acc3"]


# ---------------------------------------------------------------------------
# attach_action — broadcasts alert_resolved
# ---------------------------------------------------------------------------

async def test_attach_action_broadcasts(db_session):
    """attach_action broadcasts 'alert_resolved' with action data."""
    alert = Alert(alert_type="dropped_out", status="pending", account_uid="u_c")
    db_session.add(alert)
    db_session.commit()

    ws = make_mock_ws_manager()
    engine = AlertEngine(db_session=db_session, ws_manager=ws)
    await engine.attach_action(alert.id, "好棒!", ["acc_x"])

    ws.broadcast.assert_awaited_once()
    call_args = ws.broadcast.call_args
    assert call_args[0][0] == "alert_resolved"
    data = call_args[0][1]
    assert data["alert_id"] == alert.id
    assert data["status"] == "confirmed"
    assert data["comment_content"] == "好棒!"
    assert data["selected_account_ids"] == ["acc_x"]


# ---------------------------------------------------------------------------
# attach_action — nonexistent alert returns False
# ---------------------------------------------------------------------------

async def test_attach_action_nonexistent_returns_false(db_session):
    """attach_action returns False for a nonexistent alert_id."""
    engine = AlertEngine(db_session=db_session)
    result = await engine.attach_action(99999, "test", ["acc1"])

    assert result is False


# ---------------------------------------------------------------------------
# attach_action — no db_session returns False
# ---------------------------------------------------------------------------

async def test_attach_action_no_db_session_returns_false():
    """attach_action returns False when db_session is None."""
    engine = AlertEngine()
    result = await engine.attach_action(1, "test", ["acc1"])

    assert result is False
