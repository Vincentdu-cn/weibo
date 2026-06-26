"""TeamMember model — represents a tracked Weibo user (UID + nickname).

Unlike :class:`~app.models.account.Account`, a TeamMember does not need
login credentials.  It is simply a UID+nickname pair used by the
member-tracker to identify which commenters are "team members".
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.core.database import Base


class TeamMember(Base):
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, index=True)
    weibo_uid = Column(String(64), unique=True, nullable=False, index=True)
    nickname = Column(String(128), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<TeamMember(id={self.id}, uid={self.weibo_uid}, nickname={self.nickname})>"
