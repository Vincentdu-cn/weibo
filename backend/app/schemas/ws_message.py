"""WebSocket message schema for real-time communication."""

from typing import Any, Dict

from pydantic import BaseModel, ConfigDict


class WSMessage(BaseModel):
    """Data transfer object for WebSocket messages."""

    model_config = ConfigDict(from_attributes=True)

    type: str
    data: Dict[str, Any]
    timestamp: str
