"""Comment model — a Weibo comment fetched from a target post."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.core.database import Base


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    weibo_comment_id = Column(String(64), nullable=False, index=True)
    weibo_post_id = Column(String(64), nullable=False, index=True)
    user_uid = Column(String(64), nullable=False, index=True)
    user_name = Column(String(128), nullable=False)
    content = Column(Text, nullable=True)
    like_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=True)  # when the comment was posted on Weibo
    fetched_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Comment(id={self.id}, comment_id={self.weibo_comment_id}, likes={self.like_count})>"
