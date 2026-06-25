"""Stats schema for API serialization."""

from pydantic import BaseModel, ConfigDict


class StatsDTO(BaseModel):
    """Data transfer object for dashboard statistics."""

    model_config = ConfigDict(from_attributes=True)

    total_comments: int
    team_hot_count: int
    remaining_quota: int
    elapsed_time: str
    hot_ratio: float
    team_online_count: int = 0
    pending_alerts: int = 0
    executed_actions: int = 0
