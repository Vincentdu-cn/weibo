"""FastAPI WebSocket route with heartbeat and connection management."""
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.ws_manager import WebSocketConnectionManager

router = APIRouter()
ws_manager = WebSocketConnectionManager()

HEARTBEAT_TIMEOUT_SECONDS = 30


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint.

    - Accepts connection via manager
    - Sends welcome message
    - Listens for messages; responds "pong" to "ping"
    - 30-second heartbeat timeout: disconnects idle clients
    - Cleans up on disconnect
    """
    connection_id = await ws_manager.connect(websocket)

    # Send welcome message
    await ws_manager.send_to(connection_id, {
        "type": "connection",
        "data": {"connection_id": connection_id, "status": "connected"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    try:
        while True:
            # Wait for a message with heartbeat timeout
            try:
                raw = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=HEARTBEAT_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                # No message within timeout — disconnect
                break

            # Handle ping/pong
            if raw == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "data": {},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(connection_id)
