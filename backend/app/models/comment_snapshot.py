"""CommentSnapshot model — time-series snapshot of a comment's metrics."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer

from app.core.database import Base


class CommentSnapshot(Base):
    __tablename__ = "comment_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(Integer, ForeignKey("comments.id"), nullable=False, index=True)
    like_count = Column(Integer, nullable=False, default=0)
    rank = Column(Integer, nullable=True)
    is_hot = Column(Boolean, nullable=False, default=False)
    is_team_member = Column(Boolean, nullable=False, default=False)
    snapshot_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return (
            f"<CommentSnapshot(id={self.id}, comment_id={self.comment_id}, "
            f"likes={self.like_count}, rank={self.rank}, hot={self.is_hot})>"
        )
