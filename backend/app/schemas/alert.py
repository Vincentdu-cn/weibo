"""Alert schema for API serialization."""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class AlertDTO(BaseModel):
    """Data transfer object for system alerts."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_uid: Optional[str] = None
    comment_id: Optional[int] = None
    alert_type: str
    message: str
    status: str
    comment_input: Optional[str] = None
    selected_account_ids: Optional[List[int]] = []
