"""GET /api/v1/users/me integration tests — requires real PostgreSQL (CITEXT)."""
import os
import pytest
import jwt
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database.session import get_db_session
from app.core.config import settings

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://app:app_dev_only@localhost:5432/gestor_pagos",
)


@pytest.fixture(scope="module")
def pg_engine():
    """Create a Postgres engine, skip if not available."""
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as e:
        pytest.skip(f"Postgres not available: {e}")


@pytest.fixture(autouse=True)
def _clean_users_me_tables(pg_engine):
    """Delete rows touched by users/me tests before and after each test."""
    with pg_engine.connect() as conn:
        conn.execute(text("DELETE FROM refresh_tokens"))
        conn.execute(text("DELETE FROM users WHERE email LIKE '%@usersme-test%'"))
        conn.commit()
    yield
    with pg_engine.connect() as conn:
        conn.execute(text("DELETE FROM refresh_tokens"))
        conn.execute(text("DELETE FROM users WHERE email LIKE '%@usersme-test%'"))
        conn.commit()


@pytest.fixture()
def client(pg_engine):
    """TestClient that overrides the DB dependency with our Postgres engine."""
    TestSession = sessionmaker(bind=pg_engine)

    def _override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db_session] = _override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def _register_and_get_token(client, email: str = "me@usersme-test.com") -> str:
    """Register a user and return the access token."""
    resp = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "Str0ngP@ss!",
        "full_name": "Me User",
    })
    assert resp.status_code == 201
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# GET /me — success
# ---------------------------------------------------------------------------

class TestGetMeSuccess:
    def test_returns_user_profile(self, client):
        token = _register_and_get_token(client)
        resp = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "me@usersme-test.com"
        assert body["full_name"] == "Me User"
        assert body["phone_number"] is None
        assert body["whatsapp_opt_in"] is False
        assert "id" in body
        assert "created_at" in body
        # password_hash must NEVER appear
        assert "password_hash" not in body


# ---------------------------------------------------------------------------
# GET /me — auth failures
# ---------------------------------------------------------------------------

class TestGetMeMissingToken:
    def test_no_header(self, client):
        resp = client.get("/api/v1/users/me")
        assert resp.status_code == 401
        assert resp.json()["code"] == "MISSING_TOKEN"

    def test_header_without_bearer_prefix(self, client):
        token = _register_and_get_token(client)
        resp = client.get("/api/v1/users/me", headers={"Authorization": token})
        assert resp.status_code == 401
        assert resp.json()["code"] == "MISSING_TOKEN"

    def test_bearer_with_empty_token(self, client):
        resp = client.get("/api/v1/users/me", headers={"Authorization": "Bearer "})
        assert resp.status_code == 401
        assert resp.json()["code"] == "MISSING_TOKEN"


class TestGetMeInvalidToken:
    def test_garbage_token(self, client):
        resp = client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer this-is-not-a-jwt"},
        )
        assert resp.status_code == 401
        assert resp.json()["code"] == "INVALID_TOKEN"

    def test_token_signed_with_wrong_secret(self, client):
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "1",
            "exp": now + timedelta(minutes=15),
            "iat": now,
        }
        bad_token = jwt.encode(payload, "wrong-secret-key-that-is-long-enough!!", algorithm="HS256")
        resp = client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {bad_token}"},
        )
        assert resp.status_code == 401
        assert resp.json()["code"] == "INVALID_TOKEN"


class TestGetMeExpiredToken:
    def test_expired_token(self, client):
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "1",
            "exp": now - timedelta(minutes=5),
            "iat": now - timedelta(minutes=20),
        }
        expired_token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
        resp = client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401
        assert resp.json()["code"] == "TOKEN_EXPIRED"


class TestGetMeUserNotFound:
    def test_nonexistent_user_id(self, client):
        """Token is valid but user_id doesn't exist in DB (user was deleted)."""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "999999999",  # absurdly high id that can't exist
            "exp": now + timedelta(minutes=15),
            "iat": now,
        }
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
        resp = client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401
        assert resp.json()["code"] == "USER_NOT_FOUND"
