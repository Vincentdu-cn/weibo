"""Alert model — alerts generated when comments need attention."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.core.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("competition_sessions.id"), nullable=True, index=True)
    account_uid = Column(String(64), nullable=True, index=True)
    comment_id = Column(Integer, ForeignKey("comments.id"), nullable=True, index=True)
    alert_type = Column(String(64), nullable=False)  # dropped_out / rank_drop / low_likes
    message = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="pending")  # pending / confirmed / executed / dismissed
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Alert(id={self.id}, type={self.alert_type}, status={self.status})>"
