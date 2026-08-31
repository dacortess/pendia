"""Invite code endpoint integration tests — requires real PostgreSQL."""
import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database.session import get_db_session
from app.main import app

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://app:app_dev_only@localhost:5432/gestor_pagos",
)

_CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"


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
def _clean_invite_tables(pg_engine):
    _do_cleanup(pg_engine)
    yield
    _do_cleanup(pg_engine)


def _do_cleanup(pg_engine):
    with pg_engine.connect() as conn:
        conn.execute(text("DELETE FROM group_memberships"))
        conn.execute(text("DELETE FROM group_invite_codes"))
        conn.execute(text(
            "DELETE FROM groups WHERE created_by IN "
            "(SELECT id FROM users WHERE email LIKE '%@invite-test%%')"
        ))
        conn.execute(text(
            "DELETE FROM refresh_tokens WHERE user_id IN "
            "(SELECT id FROM users WHERE email LIKE '%@invite-test%%')"
        ))
        conn.execute(text("DELETE FROM users WHERE email LIKE '%@invite-test%%'"))
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _register(client, email: str, password: str = "Str0ngP@ss!", full_name: str = "Test User") -> tuple[str, int]:
    resp = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": full_name,
    })
    assert resp.status_code == 201, f"Register failed: {resp.json()}"
    token = resp.json()["access_token"]
    me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    return token, me.json()["id"]


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_group(client, token: str, name: str = "Test Group") -> int:
    resp = client.post("/api/v1/groups", json={"name": name}, headers=_auth_header(token))
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_invite_code(client, token: str, group_id: int, **kwargs) -> dict:
    body = {"role_to_assign": "member", **kwargs}
    resp = client.post(
        f"/api/v1/groups/{group_id}/invite-codes",
        json=body,
        headers=_auth_header(token),
    )
    assert resp.status_code == 201, f"Create invite code failed: {resp.json()}"
    return resp.json()


def _get_user_id_by_email(pg_engine, email: str) -> int:
    with pg_engine.connect() as conn:
        row = conn.execute(
            text("SELECT id FROM users WHERE email = :e"),
            {"e": email},
        ).fetchone()
        return row[0]


# ---------------------------------------------------------------------------
# POST /groups/{group_id}/invite-codes — create invite code
# ---------------------------------------------------------------------------

class TestCreateInviteCode:
    def test_create_code_success(self, client):
        token, _ = _register(client, "admin1@invite-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Invite Group")

        resp = client.post(
            f"/api/v1/groups/{group_id}/invite-codes",
            json={"role_to_assign": "member"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert len(body["code"]) == 8
        assert all(c in _CODE_ALPHABET for c in body["code"])
        assert body["role_to_assign"] == "member"
        assert body["is_active"] is True
        assert body["uses_count"] == 0
        assert body["max_uses"] is None
        assert body["expires_at"] is None

    def test_create_code_with_max_uses(self, client):
        token, _ = _register(client, "admin2@invite-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Max Uses Group")

        resp = client.post(
            f"/api/v1/groups/{group_id}/invite-codes",
            json={"role_to_assign": "member", "max_uses": 1},
            headers=_auth_header(token),
        )
        assert resp.status_code == 201
        assert resp.json()["max_uses"] == 1

    def test_create_code_with_expires_at(self, client):
        token, _ = _register(client, "admin3@invite-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Expiry Group")
        future = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

        resp = client.post(
            f"/api/v1/groups/{group_id}/invite-codes",
            json={"role_to_assign": "member", "expires_at": future},
            headers=_auth_header(token),
        )
        assert resp.status_code == 201
        assert resp.json()["expires_at"] is not None

    def test_create_code_admin_role(self, client):
        token, _ = _register(client, "admin4@invite-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Admin Role Group")

        resp = client.post(
            f"/api/v1/groups/{group_id}/invite-codes",
            json={"role_to_assign": "admin"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 201
        assert resp.json()["role_to_assign"] == "admin"

    def test_create_code_owner_rejected(self, client):
        token, _ = _register(client, "admin5@invite-test.com", full_name="Admin")
        group_id = _create_group(client, token, "No Owner Group")

        resp = client.post(
            f"/api/v1/groups/{group_id}/invite-codes",
            json={"role_to_assign": "owner"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 422

    def test_create_code_member_forbidden(self, client):
        token_owner, _ = _register(client, "own6@invite-test.com", full_name="Owner")
        token_member, _ = _register(client, "mem6@invite-test.com", full_name="Member")
        group_id = _create_group(client, token_owner, "Member Forbidden Group")

        client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "mem6@invite-test.com", "role": "member"},
            headers=_auth_header(token_owner),
        )

        resp = client.post(
            f"/api/v1/groups/{group_id}/invite-codes",
            json={"role_to_assign": "member"},
            headers=_auth_header(token_member),
        )
        assert resp.status_code == 403
        assert resp.json()["code"] == "FORBIDDEN_NOT_ADMIN"


# ---------------------------------------------------------------------------
# GET /groups/{group_id}/invite-codes — list invite codes
# ---------------------------------------------------------------------------

class TestListInviteCodes:
    def test_list_codes_empty(self, client):
        token, _ = _register(client, "list1@invite-test.com", full_name="Lister")
        group_id = _create_group(client, token, "Empty Codes Group")

        resp = client.get(
            f"/api/v1/groups/{group_id}/invite-codes",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_codes_includes_created(self, client):
        token, _ = _register(client, "list2@invite-test.com", full_name="Lister")
        group_id = _create_group(client, token, "Codes Group")

        code1 = _create_invite_code(client, token, group_id)
        code2 = _create_invite_code(client, token, group_id, role_to_assign="admin")

        resp = client.get(
            f"/api/v1/groups/{group_id}/invite-codes",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        codes = resp.json()
        assert len(codes) == 2
        code_ids = {c["id"] for c in codes}
        assert code1["id"] in code_ids
        assert code2["id"] in code_ids

    def test_list_codes_member_forbidden(self, client):
        token_owner, _ = _register(client, "list3@invite-test.com", full_name="Owner")
        token_member, _ = _register(client, "listm3@invite-test.com", full_name="Member")
        group_id = _create_group(client, token_owner, "List Member Group")

        client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "listm3@invite-test.com", "role": "member"},
            headers=_auth_header(token_owner),
        )

        resp = client.get(
            f"/api/v1/groups/{group_id}/invite-codes",
            headers=_auth_header(token_member),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /groups/{group_id}/invite-codes/{id} — revoke invite code
# ---------------------------------------------------------------------------

class TestRevokeInviteCode:
    def test_revoke_code_success(self, client):
        token, _ = _register(client, "revoke1@invite-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Revoke Group")
        code = _create_invite_code(client, token, group_id)

        resp = client.patch(
            f"/api/v1/groups/{group_id}/invite-codes/{code['id']}",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_revoke_code_not_found(self, client):
        token, _ = _register(client, "revoke2@invite-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Revoke NF Group")

        resp = client.patch(
            f"/api/v1/groups/{group_id}/invite-codes/999999",
            headers=_auth_header(token),
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == "INVITE_CODE_NOT_FOUND"

    def test_revoke_code_other_group_forbidden(self, client, pg_engine):
        token_a, _ = _register(client, "revokeA@invite-test.com", full_name="AdminA")
        token_b, _ = _register(client, "revokeB@invite-test.com", full_name="AdminB")
        group_a = _create_group(client, token_a, "Group A")
        group_b = _create_group(client, token_b, "Group B")

        code_a = _create_invite_code(client, token_a, group_a)

        resp = client.patch(
            f"/api/v1/groups/{group_b}/invite-codes/{code_a['id']}",
            headers=_auth_header(token_b),
        )
        assert resp.status_code == 404

    def test_revoked_code_cannot_join(self, client):
        token, _ = _register(client, "revoke3@invite-test.com", full_name="Admin")
        _register(client, "joiner3@invite-test.com", full_name="Joiner")
        group_id = _create_group(client, token, "Revoked Join Group")
        code = _create_invite_code(client, token, group_id)

        client.patch(
            f"/api/v1/groups/{group_id}/invite-codes/{code['id']}",
            headers=_auth_header(token),
        )

        join_token, _ = _register(client, "joiner3b@invite-test.com", full_name="JoinerB")
        resp = client.post(
            "/api/v1/groups/join",
            json={"code": code["code"]},
            headers=_auth_header(join_token),
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == "INVALID_INVITE_CODE"


# ---------------------------------------------------------------------------
# GET /groups/{group_id}/invite-codes/{id}/qr — QR code image
# ---------------------------------------------------------------------------

class TestInviteCodeQR:
    def test_qr_returns_png(self, client):
        token, _ = _register(client, "qr1@invite-test.com", full_name="Admin")
        group_id = _create_group(client, token, "QR Group")
        code = _create_invite_code(client, token, group_id)

        resp = client.get(
            f"/api/v1/groups/{group_id}/invite-codes/{code['id']}/qr",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert len(resp.content) > 0

    def test_qr_not_found(self, client):
        token, _ = _register(client, "qr2@invite-test.com", full_name="Admin")
        group_id = _create_group(client, token, "QR NF Group")

        resp = client.get(
            f"/api/v1/groups/{group_id}/invite-codes/999999/qr",
            headers=_auth_header(token),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /groups/join/preview — preview group name (no auth)
# ---------------------------------------------------------------------------

class TestJoinPreview:
    def test_preview_valid_code(self, client):
        token, _ = _register(client, "prev1@invite-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Preview Family")
        code = _create_invite_code(client, token, group_id)

        resp = client.get(f"/api/v1/groups/join/preview?code={code['code']}")
        assert resp.status_code == 200
        assert resp.json()["group_name"] == "Preview Family"

    def test_preview_invalid_code(self, client):
        resp = client.get("/api/v1/groups/join/preview?code=INVALID1")
        assert resp.status_code == 404
        assert resp.json()["code"] == "INVALID_INVITE_CODE"

    def test_preview_revoked_code(self, client):
        token, _ = _register(client, "prev2@invite-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Revoked Preview")
        code = _create_invite_code(client, token, group_id)

        client.patch(
            f"/api/v1/groups/{group_id}/invite-codes/{code['id']}",
            headers=_auth_header(token),
        )

        resp = client.get(f"/api/v1/groups/join/preview?code={code['code']}")
        assert resp.status_code == 404
        assert resp.json()["code"] == "INVALID_INVITE_CODE"


# ---------------------------------------------------------------------------
# POST /groups/join — join group via code
# ---------------------------------------------------------------------------

class TestJoinGroup:
    def test_join_success(self, client):
        token_owner, _ = _register(client, "jown1@invite-test.com", full_name="Owner")
        token_joined, _ = _register(client, "jnew1@invite-test.com", full_name="Joiner")
        group_id = _create_group(client, token_owner, "Join Family")
        code = _create_invite_code(client, token_owner, group_id)

        resp = client.post(
            "/api/v1/groups/join",
            json={"code": code["code"]},
            headers=_auth_header(token_joined),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["group_id"] == group_id
        assert body["group_name"] == "Join Family"
        assert body["role"] == "member"

    def test_join_sets_joined_via_invite_code_id(self, client, pg_engine):
        token_owner, _ = _register(client, "jown2@invite-test.com", full_name="Owner")
        token_joined, _ = _register(client, "jnew2@invite-test.com", full_name="Joiner")
        group_id = _create_group(client, token_owner, "Join ID Group")
        code = _create_invite_code(client, token_owner, group_id)

        client.post(
            "/api/v1/groups/join",
            json={"code": code["code"]},
            headers=_auth_header(token_joined),
        )

        with pg_engine.connect() as conn:
            row = conn.execute(
                text("SELECT joined_via_invite_code_id FROM group_memberships WHERE user_id = :uid AND group_id = :gid"),
                {"uid": _get_user_id_by_email(pg_engine, "jnew2@invite-test.com"), "gid": group_id},
            ).fetchone()
            assert row[0] == code["id"]

    def test_join_increments_uses_count(self, client, pg_engine):
        token_owner, _ = _register(client, "jown3@invite-test.com", full_name="Owner")
        token_joined, _ = _register(client, "jnew3@invite-test.com", full_name="Joiner")
        group_id = _create_group(client, token_owner, "Uses Count Group")
        code = _create_invite_code(client, token_owner, group_id)

        client.post(
            "/api/v1/groups/join",
            json={"code": code["code"]},
            headers=_auth_header(token_joined),
        )

        with pg_engine.connect() as conn:
            row = conn.execute(
                text("SELECT uses_count FROM group_invite_codes WHERE id = :id"),
                {"id": code["id"]},
            ).fetchone()
            assert row[0] == 1

    def test_join_already_member(self, client):
        token_owner, _ = _register(client, "jown4@invite-test.com", full_name="Owner")
        join_token, _ = _register(client, "jnew4@invite-test.com", full_name="Joiner")
        group_id = _create_group(client, token_owner, "Already Member Group")
        code = _create_invite_code(client, token_owner, group_id)

        resp1 = client.post(
            "/api/v1/groups/join",
            json={"code": code["code"]},
            headers=_auth_header(join_token),
        )
        assert resp1.status_code == 201

        resp2 = client.post(
            "/api/v1/groups/join",
            json={"code": code["code"]},
            headers=_auth_header(join_token),
        )
        assert resp2.status_code == 409
        assert resp2.json()["code"] == "ALREADY_MEMBER"

    def test_join_max_uses_exhausted(self, client):
        token_owner, _ = _register(client, "jown5@invite-test.com", full_name="Owner")
        token_j1, _ = _register(client, "jnew5a@invite-test.com", full_name="Joiner1")
        token_j2, _ = _register(client, "jnew5b@invite-test.com", full_name="Joiner2")
        group_id = _create_group(client, token_owner, "Max Uses Join Group")
        code = _create_invite_code(client, token_owner, group_id, max_uses=1)

        resp1 = client.post(
            "/api/v1/groups/join",
            json={"code": code["code"]},
            headers=_auth_header(token_j1),
        )
        assert resp1.status_code == 201

        resp2 = client.post(
            "/api/v1/groups/join",
            json={"code": code["code"]},
            headers=_auth_header(token_j2),
        )
        assert resp2.status_code == 404
        assert resp2.json()["code"] == "INVALID_INVITE_CODE"

    def test_join_expired_code(self, client):
        token_owner, _ = _register(client, "jown6@invite-test.com", full_name="Owner")
        token_joined, _ = _register(client, "jnew6@invite-test.com", full_name="Joiner")
        group_id = _create_group(client, token_owner, "Expired Join Group")

        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        resp_code = client.post(
            f"/api/v1/groups/{group_id}/invite-codes",
            json={"role_to_assign": "member", "expires_at": past},
            headers=_auth_header(token_owner),
        )
        code = resp_code.json()

        resp = client.post(
            "/api/v1/groups/join",
            json={"code": code["code"]},
            headers=_auth_header(token_joined),
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == "INVALID_INVITE_CODE"

    def test_join_unauthenticated(self, client):
        resp = client.post(
            "/api/v1/groups/join",
            json={"code": "ANYCODE1"},
        )
        assert resp.status_code == 401

    def test_join_invalid_code(self, client):
        token, _ = _register(client, "jown7@invite-test.com", full_name="Admin")
        resp = client.post(
            "/api/v1/groups/join",
            json={"code": "INVALID1"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == "INVALID_INVITE_CODE"


# ---------------------------------------------------------------------------
# Route ordering — /groups/join doesn't conflict with /groups/{group_id}
# ---------------------------------------------------------------------------

class TestRouteOrdering:
    def test_join_endpoint_not_confused_with_group_id(self, client):
        token, _ = _register(client, "route1@invite-test.com", full_name="User")
        group_id = _create_group(client, token, "Route Group")

        resp = client.get(f"/api/v1/groups/{group_id}", headers=_auth_header(token))
        assert resp.status_code == 200
        assert resp.json()["name"] == "Route Group"

    def test_join_preview_not_confused_with_group_id(self, client):
        resp = client.get("/api/v1/groups/join/preview?code=ANYCODE1")
        assert resp.status_code == 404
        assert resp.json()["code"] == "INVALID_INVITE_CODE"


# ---------------------------------------------------------------------------
# POST /auth/register with invite_code — atomic register + join
# ---------------------------------------------------------------------------

class TestRegisterWithInviteCode:
    def test_register_with_valid_code(self, client, pg_engine):
        token_owner, _ = _register(client, "regown1@invite-test.com", full_name="Owner")
        group_id = _create_group(client, token_owner, "Register Join Group")
        code = _create_invite_code(client, token_owner, group_id)

        resp = client.post("/api/v1/auth/register", json={
            "email": "regnew1@invite-test.com",
            "password": "Str0ngP@ss!",
            "full_name": "New Joiner",
            "invite_code": code["code"],
        })
        assert resp.status_code == 201
        assert "access_token" in resp.json()

        user_id = _get_user_id_by_email(pg_engine, "regnew1@invite-test.com")
        with pg_engine.connect() as conn:
            row = conn.execute(
                text("SELECT role, joined_via_invite_code_id FROM group_memberships WHERE user_id = :uid AND group_id = :gid"),
                {"uid": user_id, "gid": group_id},
            ).fetchone()
            assert row is not None
            assert row[0] == "member"
            assert row[1] == code["id"]

    def test_register_with_invalid_code_no_user_created(self, client, pg_engine):
        resp = client.post("/api/v1/auth/register", json={
            "email": "regfail1@invite-test.com",
            "password": "Str0ngP@ss!",
            "full_name": "Fail Joiner",
            "invite_code": "INVALID1",
        })
        assert resp.status_code == 404
        assert resp.json()["code"] == "INVALID_INVITE_CODE"

        with pg_engine.connect() as conn:
            row = conn.execute(
                text("SELECT id FROM users WHERE email = :e"),
                {"e": "regfail1@invite-test.com"},
            ).fetchone()
            assert row is None

    def test_register_without_invite_code_still_works(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": "regnoinv@invite-test.com",
            "password": "Str0ngP@ss!",
            "full_name": "No Invite",
        })
        assert resp.status_code == 201
        assert "access_token" in resp.json()

    def test_register_with_expired_code_no_user_created(self, client, pg_engine):
        token_owner, _ = _register(client, "regown2@invite-test.com", full_name="Owner")
        group_id = _create_group(client, token_owner, "Reg Expired Group")

        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        resp_code = client.post(
            f"/api/v1/groups/{group_id}/invite-codes",
            json={"role_to_assign": "member", "expires_at": past},
            headers=_auth_header(token_owner),
        )
        code = resp_code.json()

        resp = client.post("/api/v1/auth/register", json={
            "email": "regfail2@invite-test.com",
            "password": "Str0ngP@ss!",
            "full_name": "Fail Expired",
            "invite_code": code["code"],
        })
        assert resp.status_code == 404
        assert resp.json()["code"] == "INVALID_INVITE_CODE"

        with pg_engine.connect() as conn:
            row = conn.execute(
                text("SELECT id FROM users WHERE email = :e"),
                {"e": "regfail2@invite-test.com"},
            ).fetchone()
            assert row is None

    def test_register_with_exhausted_code_no_user_created(self, client, pg_engine):
        token_owner, _ = _register(client, "regown3@invite-test.com", full_name="Owner")
        group_id = _create_group(client, token_owner, "Reg Exhausted Group")
        code = _create_invite_code(client, token_owner, group_id, max_uses=1)

        # First user joins via register — succeeds
        resp1 = client.post("/api/v1/auth/register", json={
            "email": "regok3@invite-test.com",
            "password": "Str0ngP@ss!",
            "full_name": "OK Joiner",
            "invite_code": code["code"],
        })
        assert resp1.status_code == 201

        # Second user tries to register with same exhausted code — fails, no user created
        resp2 = client.post("/api/v1/auth/register", json={
            "email": "regfail3@invite-test.com",
            "password": "Str0ngP@ss!",
            "full_name": "Fail Exhausted",
            "invite_code": code["code"],
        })
        assert resp2.status_code == 404
        assert resp2.json()["code"] == "INVALID_INVITE_CODE"

        with pg_engine.connect() as conn:
            row = conn.execute(
                text("SELECT id FROM users WHERE email = :e"),
                {"e": "regfail3@invite-test.com"},
            ).fetchone()
            assert row is None
