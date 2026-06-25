"""WebSocket connection manager for broadcasting messages to connected clients."""
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket


class WebSocketConnectionManager:
    """Manages active WebSocket connections and provides broadcast/send utilities."""

    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket) -> str:
        """Accept a new WebSocket connection and register it.

        Args:
            websocket: The incoming WebSocket connection.

        Returns:
            A unique connection_id (UUID string) for this connection.
        """
        await websocket.accept()
        connection_id = str(uuid.uuid4())
        self._connections[connection_id] = websocket
        return connection_id

    async def disconnect(self, connection_id: str) -> None:
        """Remove a connection from the manager.

        Args:
            connection_id: The UUID of the connection to remove.
        """
        self._connections.pop(connection_id, None)

    async def broadcast(self, message_type: str, data: dict[str, Any]) -> None:
        """Send a formatted message to ALL connected clients.

        Args:
            message_type: The event type (e.g. "alert_new", "stats_update").
            data: The payload to send.
        """
        message = {
            "type": message_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for websocket in self._connections.values():
            await websocket.send_json(message)

    async def send_to(self, connection_id: str, message: dict[str, Any]) -> None:
        """Send a raw message to a specific connected client.

        Args:
            connection_id: The UUID of the target connection.
            message: The dict to send as JSON.
        """
        ws = self._connections.get(connection_id)
        if ws is not None:
            await ws.send_json(message)

    def get_connection_count(self) -> int:
        """Return the number of active connections."""
        return len(self._connections)
