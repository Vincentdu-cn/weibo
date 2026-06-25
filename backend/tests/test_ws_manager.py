"""Tests for WebSocketConnectionManager."""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.ws_manager import WebSocketConnectionManager


def make_mock_ws() -> MagicMock:
    """Create a mock WebSocket with async accept/send_json/receive_text/close."""
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.mark.asyncio
async def test_connect_stores_connection():
    """connect() accepts WS and stores it; returns a connection_id."""
    mgr = WebSocketConnectionManager()
    ws = make_mock_ws()

    conn_id = await mgr.connect(ws)

    ws.accept.assert_awaited_once()
    assert conn_id in mgr._connections
    assert mgr._connections[conn_id] is ws
    # connection_id should be a valid UUID string
    uuid.UUID(conn_id)


@pytest.mark.asyncio
async def test_disconnect_removes_connection():
    """disconnect() removes the connection from the dict."""
    mgr = WebSocketConnectionManager()
    ws = make_mock_ws()

    conn_id = await mgr.connect(ws)
    assert mgr.get_connection_count() == 1

    await mgr.disconnect(conn_id)
    assert conn_id not in mgr._connections
    assert mgr.get_connection_count() == 0


@pytest.mark.asyncio
async def test_disconnect_nonexistent_is_noop():
    """disconnect() with unknown id does not raise."""
    mgr = WebSocketConnectionManager()
    await mgr.disconnect("nonexistent-id")  # should not raise


@pytest.mark.asyncio
async def test_broadcast_sends_to_all_clients():
    """broadcast() sends formatted message to every connected client."""
    mgr = WebSocketConnectionManager()
    ws1 = make_mock_ws()
    ws2 = make_mock_ws()

    await mgr.connect(ws1)
    await mgr.connect(ws2)

    await mgr.broadcast("test_event", {"key": "value"})

    for ws in (ws1, ws2):
        ws.send_json.assert_awaited_once()
        sent = ws.send_json.call_args[0][0]
        assert sent["type"] == "test_event"
        assert sent["data"] == {"key": "value"}
        assert "timestamp" in sent


@pytest.mark.asyncio
async def test_broadcast_no_connections_is_noop():
    """broadcast() with zero connections does not raise."""
    mgr = WebSocketConnectionManager()
    await mgr.broadcast("test", {})  # should not raise


@pytest.mark.asyncio
async def test_send_to_specific_client():
    """send_to() delivers message only to the specified connection."""
    mgr = WebSocketConnectionManager()
    ws1 = make_mock_ws()
    ws2 = make_mock_ws()

    id1 = await mgr.connect(ws1)
    id2 = await mgr.connect(ws2)

    msg = {"type": "private", "data": "hello"}
    await mgr.send_to(id1, msg)

    ws1.send_json.assert_awaited_once_with(msg)
    ws2.send_json.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_to_nonexistent_is_noop():
    """send_to() with unknown id does not raise."""
    mgr = WebSocketConnectionManager()
    await mgr.send_to("nonexistent", {"type": "test"})  # should not raise


@pytest.mark.asyncio
async def test_get_connection_count():
    """get_connection_count() returns number of active connections."""
    mgr = WebSocketConnectionManager()
    assert mgr.get_connection_count() == 0

    ws1 = make_mock_ws()
    ws2 = make_mock_ws()
    ws3 = make_mock_ws()

    await mgr.connect(ws1)
    await mgr.connect(ws2)
    await mgr.connect(ws3)
    assert mgr.get_connection_count() == 3

    await mgr.disconnect(list(mgr._connections.keys())[0])
    assert mgr.get_connection_count() == 2


@pytest.mark.asyncio
async def test_broadcast_message_format():
    """Broadcast message has type, data, and timestamp fields."""
    mgr = WebSocketConnectionManager()
    ws = make_mock_ws()
    await mgr.connect(ws)

    await mgr.broadcast("alert_new", {"alert_id": 42})

    sent = ws.send_json.call_args[0][0]
    assert set(sent.keys()) == {"type", "data", "timestamp"}
    assert sent["type"] == "alert_new"
    assert sent["data"] == {"alert_id": 42}
    assert isinstance(sent["timestamp"], str)
