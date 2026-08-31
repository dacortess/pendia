"""Password hashing and JWT utilities — pure functions, no DB or FastAPI deps."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings


def hash_password(password: str) -> str:
    """Hash a password using Argon2id with configured parameters."""
    ph = PasswordHasher(
        time_cost=settings.ARGON2_TIME_COST,
        memory_cost=settings.ARGON2_MEMORY_COST_KB,
        parallelism=settings.ARGON2_PARALLELISM,
    )
    return ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against an Argon2id hash. Returns False on mismatch, never raises."""
    ph = PasswordHasher(
        time_cost=settings.ARGON2_TIME_COST,
        memory_cost=settings.ARGON2_MEMORY_COST_KB,
        parallelism=settings.ARGON2_PARALLELISM,
    )
    try:
        return ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def create_access_token(user_id: int) -> str:
    """Create a JWT access token for the given user_id (HS256, 15 min TTL)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "exp": now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_TTL_MINUTES),
        "iat": now,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token. Raises jwt.ExpiredSignatureError
    or jwt.InvalidTokenError on failure — caller must handle."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])


def generate_refresh_token() -> str:
    """Generate a cryptographically secure opaque refresh token."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    """Return SHA-256 hex digest of a refresh token (for storage in DB)."""
    return hashlib.sha256(token.encode()).hexdigest()
