"""CompetitionSession model — a monitoring session for a target Weibo post."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.core.database import Base


class CompetitionSession(Base):
    __tablename__ = "competition_sessions"

    id = Column(Integer, primary_key=True, index=True)
    target_weibo_url = Column(String(1024), nullable=False)
    target_weibo_mid = Column(String(64), nullable=False, index=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    total_comments = Column(Integer, nullable=False, default=0)
    status = Column(String(32), nullable=False, default="idle")  # idle / running / paused / ended

    def __repr__(self) -> str:
        return f"<CompetitionSession(id={self.id}, mid={self.target_weibo_mid}, status={self.status})>"
