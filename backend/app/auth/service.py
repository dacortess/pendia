"""Business logic for auth — register, login, refresh, logout."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
)
from app.auth import repository as repo


class AuthError(Exception):
    """Expected auth failure (409 or 401). Carries detail + code for the API response."""

    def __init__(self, detail: str, code: str, status_code: int):
        self.detail = detail
        self.code = code
        self.status_code = status_code


def register(
    db: Session,
    *,
    email: str,
    password: str,
    full_name: str,
    phone_number: str | None = None,
    invite_code: str | None = None,
) -> tuple[str, str]:
    """Create a new user and return (access_token, refresh_token).
    Raises AuthError 409 if email is already taken.
    If invite_code is provided, joins the user to the group in the same transaction.
    """
    if repo.get_user_by_email(db, email) is not None:
        raise AuthError("Email already registered", "EMAIL_ALREADY_EXISTS", 409)

    user = repo.create_user(
        db,
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        phone_number=phone_number,
    )

    if invite_code is not None:
        from app.groups.service import join_group_by_code, GroupError
        try:
            join_group_by_code(db, user_id=user.id, code=invite_code)
        except GroupError as exc:
            db.rollback()
            raise AuthError(exc.detail, exc.code, exc.status_code)

    access_token, raw_refresh = _issue_token_pair(db, user.id)
    db.commit()
    return access_token, raw_refresh


def authenticate(
    db: Session,
    *,
    email: str,
    password: str,
) -> tuple[str, str]:
    """Validate credentials and return (access_token, refresh_token).
    Raises AuthError 401 on any failure (email not found or wrong password).
    """
    user = repo.get_user_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("Invalid credentials", "INVALID_CREDENTIALS", 401)

    access_token, raw_refresh = _issue_token_pair(db, user.id)
    db.commit()
    return access_token, raw_refresh


def refresh(db: Session, *, refresh_token_value: str) -> tuple[str, str]:
    """Rotate a valid refresh token: revoke old, issue new pair.
    Raises AuthError 401 if token is missing, invalid, revoked, or expired.
    """
    if not refresh_token_value:
        raise AuthError("Missing refresh token", "MISSING_REFRESH_TOKEN", 401)

    token_hash = hash_refresh_token(refresh_token_value)
    existing = repo.get_active_refresh_token_by_hash(db, token_hash)
    if existing is None:
        raise AuthError("Invalid or expired refresh token", "INVALID_REFRESH_TOKEN", 401)

    # Revoke old token (rotation)
    repo.revoke_refresh_token(db, token_hash)

    # Issue new pair
    access_token, raw_refresh = _issue_token_pair(db, existing.user_id)
    db.commit()
    return access_token, raw_refresh


def logout(db: Session, *, refresh_token_value: str) -> None:
    """Revoke the refresh token if it exists (idempotent)."""
    if refresh_token_value:
        token_hash = hash_refresh_token(refresh_token_value)
        repo.revoke_refresh_token(db, token_hash)
        db.commit()


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _issue_token_pair(db: Session, user_id: int) -> tuple[str, str]:
    """Create an access token and a persisted refresh token. Returns (access_token, refresh_token_raw)."""
    access_token = create_access_token(user_id)

    raw_refresh = generate_refresh_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS)
    repo.create_refresh_token(
        db,
        user_id=user_id,
        token_hash=hash_refresh_token(raw_refresh),
        expires_at=expires_at,
    )

    return access_token, raw_refresh
