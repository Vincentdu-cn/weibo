"""Pytest fixtures: in-memory SQLite for isolated testing."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import Base and all models so metadata is fully populated
from app.core.database import Base
from app.models import (  # noqa: F401 — register tables on Base.metadata
    Account,
    ActionLog,
    Alert,
    Comment,
    CommentSnapshot,
    CompetitionSession,
)


@pytest.fixture
def db_session():
    """Yield a fresh in-memory SQLite session for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
