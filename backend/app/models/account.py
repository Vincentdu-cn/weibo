"""Account model — represents a Weibo account used by the platform."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.core.database import Base


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    weibo_uid = Column(String(64), unique=True, nullable=False, index=True)
    nickname = Column(String(128), nullable=False)
    cookie_json = Column(Text, nullable=True)
    cookie_expires_at = Column(DateTime, nullable=True)
    status = Column(String(32), nullable=False, default="active")  # active / expired / disabled
    avatar_url = Column(String(512), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Account(id={self.id}, uid={self.weibo_uid}, nickname={self.nickname})>"
