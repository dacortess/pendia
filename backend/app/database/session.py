"""SQLAlchemy session management and database engine."""
from contextlib import contextmanager
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from .base import Base
from ..core.config import settings


def get_postgres_url() -> str:
    """Get PostgreSQL connection URL from settings."""
    return settings.DATABASE_URL


def create_sync_engine(url: str) -> Engine:
    """Create a synchronous SQLAlchemy engine."""
    return create_engine(
        url,
        pool_pre_ping=True,
        future=True,
        connect_args={"options": "-c TimeZone=America/Bogota"},
    )


# Sync engine and session factory (for tests and Alembic)
_sync_engine = create_sync_engine(get_postgres_url())

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_sync_engine)


@contextmanager
def get_db():
    """Context manager for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session():
    """FastAPI dependency — yields a DB session, closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
