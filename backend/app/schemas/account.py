"""Account schema for API serialization."""

from typing import Optional

from pydantic import BaseModel, ConfigDict


class AccountDTO(BaseModel):
    """Data transfer object for monitored Weibo accounts."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    weibo_uid: str
    nickname: str
    status: str
    avatar_url: Optional[str] = None
