"""ActionLog model — logs actions taken by accounts (like, comment, reply)."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.core.database import Base


class ActionLog(Base):
    __tablename__ = "action_logs"

    id = Column(Integer, primary_key=True, index=True)
    account_uid = Column(String(64), nullable=False, index=True)
    action_type = Column(String(32), nullable=False)  # like / comment / reply
    target_comment_id = Column(String(64), nullable=True)
    content = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="pending")  # success / failed / pending
    response = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<ActionLog(id={self.id}, account={self.account_uid}, action={self.action_type}, status={self.status})>"
