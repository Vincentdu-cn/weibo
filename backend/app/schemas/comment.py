"""Comment schema for API serialization."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CommentDTO(BaseModel):
    """Data transfer object for Weibo comments."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    weibo_comment_id: str
    user_uid: str
    user_name: str
    content: str
    like_count: int
    rank: int
    is_hot: bool
    is_team_member: bool
    created_at: Optional[datetime] = None
