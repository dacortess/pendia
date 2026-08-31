"""Auth endpoint integration tests — requires real PostgreSQL (CITEXT)."""
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.main import app
from app.database.session import get_db_session

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
def _clean_auth_tables(pg_engine):
    """Delete rows touched by auth tests before and after each test."""
    with pg_engine.connect() as conn:
        conn.execute(text("DELETE FROM refresh_tokens"))
        conn.execute(text("DELETE FROM users WHERE email LIKE '%@auth-test%'"))
        conn.commit()
    yield
    with pg_engine.connect() as conn:
        conn.execute(text("DELETE FROM refresh_tokens"))
        conn.execute(text("DELETE FROM users WHERE email LIKE '%@auth-test%'"))
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


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

class TestRegister:
    def test_register_success(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": "new@auth-test.com",
            "password": "Str0ngP@ss!",
            "full_name": "New User",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        # Refresh token is in cookie, not in body
        assert "refresh_token" in resp.cookies

    def test_register_duplicate_email(self, client):
        payload = {
            "email": "dup@auth-test.com",
            "password": "Str0ngP@ss!",
            "full_name": "Dup User",
        }
        resp1 = client.post("/api/v1/auth/register", json=payload)
        assert resp1.status_code == 201

        resp2 = client.post("/api/v1/auth/register", json=payload)
        assert resp2.status_code == 409
        assert resp2.json()["code"] == "EMAIL_ALREADY_EXISTS"


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class TestLogin:
    def _register(self, client, email: str = "login@auth-test.com"):
        client.post("/api/v1/auth/register", json={
            "email": email,
            "password": "Str0ngP@ss!",
            "full_name": "Login User",
        })

    def test_login_success(self, client):
        self._register(client)
        resp = client.post("/api/v1/auth/login", json={
            "email": "login@auth-test.com",
            "password": "Str0ngP@ss!",
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()
        assert "refresh_token" in resp.cookies

    def test_login_nonexistent_email(self, client):
        resp = client.post("/api/v1/auth/login", json={
            "email": "noone@auth-test.com",
            "password": "Whatever123!",
        })
        assert resp.status_code == 401
        assert resp.json()["code"] == "INVALID_CREDENTIALS"

    def test_login_wrong_password(self, client):
        self._register(client)
        resp = client.post("/api/v1/auth/login", json={
            "email": "login@auth-test.com",
            "password": "WrongPassword!",
        })
        assert resp.status_code == 401
        assert resp.json()["code"] == "INVALID_CREDENTIALS"


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------

class TestRefresh:
    def _login(self, client) -> dict:
        """Register + login, return cookies as plain dict."""
        client.post("/api/v1/auth/register", json={
            "email": "refresh@auth-test.com",
            "password": "Str0ngP@ss!",
            "full_name": "Refresh User",
        })
        resp = client.post("/api/v1/auth/login", json={
            "email": "refresh@auth-test.com",
            "password": "Str0ngP@ss!",
        })
        return dict(resp.cookies)

    def test_refresh_success(self, client, pg_engine):
        cookies = self._login(client)
        resp = client.post("/api/v1/auth/refresh", cookies=cookies)
        assert resp.status_code == 200
        assert "access_token" in resp.json()
        assert "refresh_token" in resp.cookies

        # Verify old token is revoked
        from app.core.security import hash_refresh_token
        old_hash = hash_refresh_token(cookies["refresh_token"])
        with pg_engine.connect() as conn:
            row = conn.execute(
                text("SELECT revoked_at FROM refresh_tokens WHERE token_hash = :h"),
                {"h": old_hash},
            ).fetchone()
            assert row is not None
            assert row[0] is not None  # revoked_at is set

    def test_refresh_reuse_old_token_fails(self, client):
        cookies = self._login(client)
        # First refresh succeeds
        client.post("/api/v1/auth/refresh", cookies=cookies)
        # Reuse old cookie → should fail
        resp = client.post("/api/v1/auth/refresh", cookies=cookies)
        assert resp.status_code == 401
        assert resp.json()["code"] == "INVALID_REFRESH_TOKEN"

    def test_refresh_no_cookie(self, client):
        resp = client.post("/api/v1/auth/refresh")
        assert resp.status_code == 401
        assert resp.json()["code"] == "MISSING_REFRESH_TOKEN"


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

class TestLogout:
    def _login(self, client) -> dict:
        client.post("/api/v1/auth/register", json={
            "email": "logout@auth-test.com",
            "password": "Str0ngP@ss!",
            "full_name": "Logout User",
        })
        resp = client.post("/api/v1/auth/login", json={
            "email": "logout@auth-test.com",
            "password": "Str0ngP@ss!",
        })
        return dict(resp.cookies)

    def test_logout_success(self, client, pg_engine):
        cookies = self._login(client)
        resp = client.post("/api/v1/auth/logout", cookies=cookies)
        assert resp.status_code == 204

        # Cookie should be deleted
        assert "refresh_token" not in resp.cookies or resp.cookies["refresh_token"] == ""

        # Token is revoked in DB
        from app.core.security import hash_refresh_token
        token_hash = hash_refresh_token(cookies["refresh_token"])
        with pg_engine.connect() as conn:
            row = conn.execute(
                text("SELECT revoked_at FROM refresh_tokens WHERE token_hash = :h"),
                {"h": token_hash},
            ).fetchone()
            assert row is not None
            assert row[0] is not None

    def test_logout_idempotent(self, client):
        cookies = self._login(client)
        resp1 = client.post("/api/v1/auth/logout", cookies=cookies)
        assert resp1.status_code == 204
        resp2 = client.post("/api/v1/auth/logout", cookies=cookies)
        assert resp2.status_code == 204
