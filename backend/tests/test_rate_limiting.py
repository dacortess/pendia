"""Rate limiting integration tests — requires real PostgreSQL.

RNF-SEG-03: max 10 attempts/min/IP on /auth/login, /auth/register, /auth/refresh.
RNF-SEG-08: same threshold on POST /groups/join.
"""
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database.session import get_db_session

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://app:app_dev_only@localhost:5432/gestor_pagos",
)


@pytest.fixture(scope="module")
def pg_engine():
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as e:
        pytest.skip(f"Postgres not available: {e}")


@pytest.fixture(autouse=True)
def _clean_rate_limit_tables(pg_engine):
    with pg_engine.connect() as conn:
        conn.execute(text("DELETE FROM refresh_tokens"))
        conn.execute(text("DELETE FROM group_memberships"))
        conn.execute(text("DELETE FROM group_invite_codes"))
        conn.execute(text("DELETE FROM groups"))
        conn.execute(text("DELETE FROM users WHERE email LIKE '%@ratelimit-test%'"))
        conn.commit()
    yield
    with pg_engine.connect() as conn:
        conn.execute(text("DELETE FROM refresh_tokens"))
        conn.execute(text("DELETE FROM group_memberships"))
        conn.execute(text("DELETE FROM group_invite_codes"))
        conn.execute(text("DELETE FROM groups"))
        conn.execute(text("DELETE FROM users WHERE email LIKE '%@ratelimit-test%'"))
        conn.commit()


@pytest.fixture()
def client(pg_engine):
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


class TestLoginRateLimit:
    """POST /auth/login — 10 attempts allowed, 11th returns 429."""

    def test_11th_login_attempt_returns_429(self, client):
        for i in range(10):
            resp = client.post(
                "/api/v1/auth/login",
                json={"email": f"rl-login{i}@ratelimit-test.com", "password": "WrongPass123!"},
            )
            assert resp.status_code == 401, f"Request {i+1} should be 401, got {resp.status_code}"

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "rl-login10@ratelimit-test.com", "password": "WrongPass123!"},
        )
        assert resp.status_code == 429
        assert resp.json()["code"] == "RATE_LIMIT_EXCEEDED"


class TestRegisterRateLimit:
    """POST /auth/register — 10 attempts allowed, 11th returns 429."""

    def test_11th_register_attempt_returns_429(self, client):
        for i in range(10):
            resp = client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"rl-reg{i}@ratelimit-test.com",
                    "password": "ValidPass123!",
                    "full_name": f"Rate Limit User {i}",
                },
            )
            assert resp.status_code == 201, f"Request {i+1} should be 201, got {resp.status_code}"

        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "rl-reg10@ratelimit-test.com",
                "password": "ValidPass123!",
                "full_name": "Rate Limit User 10",
            },
        )
        assert resp.status_code == 429
        assert resp.json()["code"] == "RATE_LIMIT_EXCEEDED"


class TestRefreshRateLimit:
    """POST /auth/refresh — 10 attempts allowed, 11th returns 429."""

    def test_11th_refresh_attempt_returns_429(self, client):
        for i in range(10):
            resp = client.post(
                "/api/v1/auth/refresh",
                cookies={"refresh_token": f"garbage-token-{i}"},
            )
            assert resp.status_code == 401, f"Request {i+1} should be 401, got {resp.status_code}"

        resp = client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": "garbage-token-10"},
        )
        assert resp.status_code == 429
        assert resp.json()["code"] == "RATE_LIMIT_EXCEEDED"


class TestJoinGroupRateLimit:
    """POST /groups/join — 10 attempts allowed, 11th returns 429."""

    def _register_user(self, client, email):
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "ValidPass123!",
                "full_name": "Join Rate Limit User",
            },
        )
        return resp.json()["access_token"]

    def test_11th_join_attempt_returns_429(self, client):
        token = self._register_user(client, "rl-join-host@ratelimit-test.com")
        headers = {"Authorization": f"Bearer {token}"}

        for i in range(10):
            resp = client.post(
                "/api/v1/groups/join",
                json={"code": f"BADCODE{i}"},
                headers=headers,
            )
            assert resp.status_code == 404, f"Request {i+1} should be 404, got {resp.status_code}"

        resp = client.post(
            "/api/v1/groups/join",
            json={"code": "BADCODE10"},
            headers=headers,
        )
        assert resp.status_code == 429
        assert resp.json()["code"] == "RATE_LIMIT_EXCEEDED"


class TestLimiterResetBetweenTests:
    """Verify that the _reset_rate_limiter autouse fixture works correctly."""

    def test_first_batch_of_requests(self, client):
        for i in range(5):
            resp = client.post(
                "/api/v1/auth/login",
                json={"email": "rl-reset-a@ratelimit-test.com", "password": "WrongPass123!"},
            )
            assert resp.status_code == 401

    def test_second_batch_not_interfered_by_first(self, client):
        """If the limiter wasn't reset, this test would fail with 429 from request 1."""
        for i in range(5):
            resp = client.post(
                "/api/v1/auth/login",
                json={"email": "rl-reset-b@ratelimit-test.com", "password": "WrongPass123!"},
            )
            assert resp.status_code == 401, (
                f"Request {i+1} in second test failed with {resp.status_code} — "
                "limiter reset between tests is not working"
            )
