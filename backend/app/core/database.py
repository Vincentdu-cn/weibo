"""Database engine, session factory, and initialization for the Weibo hot-comment platform."""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Ensure the data directory exists
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR / 'weibo.db'}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

Base = declarative_base()


def init_db() -> None:
    """Create all tables registered on Base.metadata."""
    # Import models so that their tables are registered on Base.metadata
    from app.models import (  # noqa: F401
        Account,
        ActionLog,
        Alert,
        Comment,
        CommentSnapshot,
        CompetitionSession,
        TeamMember,
    )

    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency: yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
