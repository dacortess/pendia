"""Database queries for auth — User and RefreshToken."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.users.models import User, RefreshToken


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """Return user by primary key or None."""
    return db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()


def get_user_by_email(db: Session, email: str) -> User | None:
    """Return user by email (case-insensitive via CITEXT) or None."""
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


def create_user(
    db: Session,
    *,
    email: str,
    password_hash: str,
    full_name: str,
    phone_number: str | None = None,
) -> User:
    """Insert a new user and return it (with id populated). Caller must commit."""
    user = User(
        email=email,
        password_hash=password_hash,
        full_name=full_name,
        phone_number=phone_number,
    )
    db.add(user)
    db.flush()
    db.refresh(user)
    return user


def get_active_refresh_token_by_hash(db: Session, token_hash: str) -> RefreshToken | None:
    """Return the first non-revoked, non-expired refresh token matching the hash."""
    now = datetime.now(timezone.utc)
    return db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        )
    ).scalar_one_or_none()


def create_refresh_token(
    db: Session,
    *,
    user_id: int,
    token_hash: str,
    expires_at: datetime,
) -> RefreshToken:
    """Insert a new refresh token row. Caller must commit."""
    rt = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(rt)
    db.flush()
    db.refresh(rt)
    return rt


def revoke_refresh_token(db: Session, token_hash: str) -> None:
    """Mark a refresh token as revoked (idempotent — no-op if hash not found)."""
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .values(revoked_at=datetime.now(timezone.utc))
    )
    db.flush()


def update_password_hash(db: Session, user_id: int, password_hash: str) -> None:
    """Update a user's password hash. Caller must commit."""
    db.execute(
        update(User)
        .where(User.id == user_id)
        .values(password_hash=password_hash)
    )
    db.flush()


def revoke_all_refresh_tokens_for_user(db: Session, user_id: int) -> None:
    """Revoke all active refresh tokens for a user (security: invalidate sessions on password reset)."""
    db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
    )
    db.flush()
