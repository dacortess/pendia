"""Test fixtures and configuration."""
import pytest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset slowapi in-memory rate limiter storage before each test.

    Without this, the 10/min limit accumulates across tests (same
    TestClient → same IP) and tests start failing with 429.
    """
    from app.core.rate_limit import limiter
    limiter.reset()


@pytest.fixture(scope="session")
def engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture(scope="function")
def session(engine):
    """Create a session for testing."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_user(session):
    """Create a sample user for testing."""
    from app.users.models import User
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        full_name="Test User",
    )
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def sample_group(session, sample_user):
    """Create a sample group for testing."""
    from app.groups.models import Group
    group = Group(
        name="Test Family",
        created_by=sample_user.id,
    )
    session.add(group)
    session.commit()
    return group
