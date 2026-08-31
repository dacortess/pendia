"""Base declarativa de SQLAlchemy."""
from sqlalchemy import BigInteger, Integer
from sqlalchemy.orm import DeclarativeBase

# BigInteger that renders as INTEGER in SQLite (for autoincrement) but BIGINT in Postgres
BigInt = BigInteger().with_variant(Integer, "sqlite")


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass
