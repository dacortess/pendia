"""Tests for core.security — password hashing, JWT, and refresh tokens."""
import pytest
import jwt
from datetime import datetime, timezone, timedelta

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_refresh_token,
)
from app.core.config import settings


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

class TestPasswordHashing:
    def test_correct_password_verifies(self):
        password = "SuperSecret123!"
        password_hash = hash_password(password)
        assert verify_password(password, password_hash) is True

    def test_incorrect_password_fails(self):
        password_hash = hash_password("CorrectPassword")
        assert verify_password("WrongPassword", password_hash) is False

    def test_same_password_produces_different_hashes(self):
        password = "SamePassword!"
        h1 = hash_password(password)
        h2 = hash_password(password)
        # Different random salts → different hash strings
        assert h1 != h2
        # But both verify correctly
        assert verify_password(password, h1) is True
        assert verify_password(password, h2) is True


# ---------------------------------------------------------------------------
# JWT access tokens
# ---------------------------------------------------------------------------

class TestAccessToken:
    def test_round_trip_returns_same_user_id(self):
        user_id = 42
        token = create_access_token(user_id)
        decoded = decode_access_token(token)
        assert decoded["sub"] == str(user_id)

    def test_token_with_wrong_secret_fails(self):
        user_id = 1
        # Manually create a token with a different secret
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "exp": now + timedelta(minutes=15),
            "iat": now,
        }
        wrong_token = jwt.encode(payload, "wrong-secret-key-that-is-long-enough!!", algorithm="HS256")
        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token(wrong_token)

    def test_expired_token_fails(self):
        user_id = 1
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "exp": now - timedelta(minutes=5),  # already expired
            "iat": now - timedelta(minutes=20),
        }
        expired_token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_access_token(expired_token)


# ---------------------------------------------------------------------------
# Refresh tokens
# ---------------------------------------------------------------------------

class TestRefreshToken:
    def test_two_tokens_are_different(self):
        t1 = generate_refresh_token()
        t2 = generate_refresh_token()
        assert t1 != t2

    def test_hash_is_deterministic(self):
        token = generate_refresh_token()
        h1 = hash_refresh_token(token)
        h2 = hash_refresh_token(token)
        assert h1 == h2

    def test_hash_differs_from_original_token(self):
        token = generate_refresh_token()
        h = hash_refresh_token(token)
        assert h != token
