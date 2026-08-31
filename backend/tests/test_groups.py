"""Group endpoint integration tests — requires real PostgreSQL."""
import os
import secrets
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
    """Create a Postgres engine, skip if not available."""
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as e:
        pytest.skip(f"Postgres not available: {e}")


@pytest.fixture(autouse=True)
def _clean_groups_tables(pg_engine):
    """Delete rows touched by groups tests before and after each test.

    Order matters due to FKs: memberships → groups → refresh_tokens → users.
    Groups are found via created_by subquery since group names don't match
    the email LIKE pattern.
    """
    _do_cleanup(pg_engine)
    yield
    _do_cleanup(pg_engine)


def _do_cleanup(pg_engine):
    with pg_engine.connect() as conn:
        conn.execute(text("DELETE FROM audit_logs"))
        conn.execute(text("DELETE FROM group_memberships"))
        conn.execute(text(
            "DELETE FROM groups WHERE created_by IN "
            "(SELECT id FROM users WHERE email LIKE '%@groups-test%%')"
        ))
        conn.execute(text(
            "DELETE FROM refresh_tokens WHERE user_id IN "
            "(SELECT id FROM users WHERE email LIKE '%@groups-test%%')"
        ))
        conn.execute(text("DELETE FROM users WHERE email LIKE '%@groups-test%%'"))
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
# Helpers
# ---------------------------------------------------------------------------

def _register(client, email: str, password: str = "Str0ngP@ss!", full_name: str = "Test User") -> tuple[str, int]:
    """Register a user and return (access_token, user_id)."""
    resp = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": full_name,
    })
    assert resp.status_code == 201, f"Register failed: {resp.json()}"
    # Get user_id via /users/me
    token = resp.json()["access_token"]
    me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    return token, me.json()["id"]


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _get_user_id_by_email(pg_engine, email: str) -> int:
    """Look up a user's ID by email directly in the DB."""
    with pg_engine.connect() as conn:
        row = conn.execute(
            text("SELECT id FROM users WHERE email = :e"),
            {"e": email},
        ).fetchone()
        return row[0]


# ---------------------------------------------------------------------------
# POST /groups — create group
# ---------------------------------------------------------------------------

class TestCreateGroup:
    def test_create_group_success(self, client):
        token, _ = _register(client, "owner@groups-test.com", full_name="Owner User")
        resp = client.post("/api/v1/groups", json={"name": "Mi Familia"}, headers=_auth_header(token))
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Mi Familia"
        assert body["my_role"] == "owner"
        assert "id" in body
        assert "created_at" in body

    def test_create_group_creator_is_owner(self, client):
        token, _ = _register(client, "creator@groups-test.com", full_name="Creator")
        resp = client.post("/api/v1/groups", json={"name": "Familia Dueño"}, headers=_auth_header(token))
        assert resp.status_code == 201
        group_id = resp.json()["id"]

        resp2 = client.get(f"/api/v1/groups/{group_id}", headers=_auth_header(token))
        assert resp2.status_code == 200
        assert resp2.json()["my_role"] == "owner"

    def test_create_group_unauthenticated(self, client):
        resp = client.post("/api/v1/groups", json={"name": "No Auth"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /groups — list user's groups
# ---------------------------------------------------------------------------

class TestListGroups:
    def test_list_groups_empty(self, client):
        token, _ = _register(client, "empty@groups-test.com", full_name="Empty")
        resp = client.get("/api/v1/groups", headers=_auth_header(token))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_groups_only_user_groups(self, client):
        token_a, _ = _register(client, "lista@groups-test.com", full_name="List A")
        token_b, _ = _register(client, "listb@groups-test.com", full_name="List B")

        resp = client.post("/api/v1/groups", json={"name": "Grupo A"}, headers=_auth_header(token_a))
        group_a_id = resp.json()["id"]

        resp_a = client.get("/api/v1/groups", headers=_auth_header(token_a))
        assert resp_a.status_code == 200
        assert len(resp_a.json()) == 1
        assert resp_a.json()[0]["id"] == group_a_id

        resp_b = client.get("/api/v1/groups", headers=_auth_header(token_b))
        assert resp_b.status_code == 200
        assert resp_b.json() == []

    def test_list_groups_includes_my_role(self, client):
        token, _ = _register(client, "rolecheck@groups-test.com", full_name="Role Check")
        resp = client.post("/api/v1/groups", json={"name": "Role Group"}, headers=_auth_header(token))
        assert resp.status_code == 201

        resp_list = client.get("/api/v1/groups", headers=_auth_header(token))
        assert resp_list.json()[0]["my_role"] == "owner"


# ---------------------------------------------------------------------------
# GET /groups/{group_id} — group detail
# ---------------------------------------------------------------------------

class TestGetGroup:
    def test_get_group_success(self, client):
        token, _ = _register(client, "detail@groups-test.com", full_name="Detail User")
        resp = client.post("/api/v1/groups", json={"name": "Detail Group"}, headers=_auth_header(token))
        group_id = resp.json()["id"]

        resp2 = client.get(f"/api/v1/groups/{group_id}", headers=_auth_header(token))
        assert resp2.status_code == 200
        assert resp2.json()["name"] == "Detail Group"
        assert resp2.json()["my_role"] == "owner"

    def test_get_group_not_member(self, client):
        token_owner, _ = _register(client, "notmember-owner@groups-test.com", full_name="Owner")
        token_stranger, _ = _register(client, "notmember-stranger@groups-test.com", full_name="Stranger")

        resp = client.post("/api/v1/groups", json={"name": "Private Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        resp2 = client.get(f"/api/v1/groups/{group_id}", headers=_auth_header(token_stranger))
        assert resp2.status_code == 403
        assert resp2.json()["code"] == "NOT_GROUP_MEMBER"

    def test_get_group_not_found(self, client):
        token, _ = _register(client, "notfound@groups-test.com", full_name="Not Found")
        resp = client.get("/api/v1/groups/999999", headers=_auth_header(token))
        assert resp.status_code == 404
        assert resp.json()["code"] == "GROUP_NOT_FOUND"


# ---------------------------------------------------------------------------
# PATCH /groups/{group_id} — edit name (owner only)
# ---------------------------------------------------------------------------

class TestUpdateGroup:
    def test_update_group_owner(self, client):
        token, _ = _register(client, "updowner@groups-test.com", full_name="Update Owner")
        resp = client.post("/api/v1/groups", json={"name": "Old Name"}, headers=_auth_header(token))
        group_id = resp.json()["id"]

        resp2 = client.patch(
            f"/api/v1/groups/{group_id}",
            json={"name": "New Name"},
            headers=_auth_header(token),
        )
        assert resp2.status_code == 200
        assert resp2.json()["name"] == "New Name"

    def test_update_group_member_forbidden(self, client):
        token_owner, _ = _register(client, "updown2@groups-test.com", full_name="Owner")
        token_member, _ = _register(client, "updmbr2@groups-test.com", full_name="Member")

        resp = client.post("/api/v1/groups", json={"name": "Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "updmbr2@groups-test.com", "role": "member"},
            headers=_auth_header(token_owner),
        )

        resp2 = client.patch(
            f"/api/v1/groups/{group_id}",
            json={"name": "Hacked Name"},
            headers=_auth_header(token_member),
        )
        assert resp2.status_code == 403
        assert resp2.json()["code"] == "FORBIDDEN_NOT_OWNER"

    def test_update_group_admin_forbidden(self, client):
        token_owner, _ = _register(client, "updown3@groups-test.com", full_name="Owner")
        token_admin, _ = _register(client, "updadm3@groups-test.com", full_name="Admin")

        resp = client.post("/api/v1/groups", json={"name": "Admin Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "updadm3@groups-test.com", "role": "admin"},
            headers=_auth_header(token_owner),
        )

        resp2 = client.patch(
            f"/api/v1/groups/{group_id}",
            json={"name": "Admin Hack"},
            headers=_auth_header(token_admin),
        )
        assert resp2.status_code == 403
        assert resp2.json()["code"] == "FORBIDDEN_NOT_OWNER"


# ---------------------------------------------------------------------------
# POST /groups/{group_id}/members — add member
# ---------------------------------------------------------------------------

class TestAddMember:
    def test_add_member_success(self, client):
        token_owner, _ = _register(client, "addown@groups-test.com", full_name="Add Owner")
        _register(client, "addmbr@groups-test.com", full_name="Add Member")

        resp = client.post("/api/v1/groups", json={"name": "Add Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        resp2 = client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "addmbr@groups-test.com", "role": "member"},
            headers=_auth_header(token_owner),
        )
        assert resp2.status_code == 201
        assert resp2.json()["role"] == "member"
        assert resp2.json()["email"] == "addmbr@groups-test.com"

    def test_add_admin_by_owner(self, client):
        token_owner, _ = _register(client, "addown2@groups-test.com", full_name="Owner2")
        _register(client, "addadm@groups-test.com", full_name="Admin2")

        resp = client.post("/api/v1/groups", json={"name": "Add Admin Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        resp2 = client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "addadm@groups-test.com", "role": "admin"},
            headers=_auth_header(token_owner),
        )
        assert resp2.status_code == 201
        assert resp2.json()["role"] == "admin"

    def test_add_member_by_admin(self, client):
        token_owner, _ = _register(client, "admown@groups-test.com", full_name="AdmOwner")
        token_admin, _ = _register(client, "admmem@groups-test.com", full_name="AdmMember")
        _register(client, "newmbr@groups-test.com", full_name="New Member")

        resp = client.post("/api/v1/groups", json={"name": "Admin Add Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "admmem@groups-test.com", "role": "admin"},
            headers=_auth_header(token_owner),
        )

        resp2 = client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "newmbr@groups-test.com", "role": "member"},
            headers=_auth_header(token_admin),
        )
        assert resp2.status_code == 201

    def test_add_member_user_not_found(self, client):
        token, _ = _register(client, "notfoundown@groups-test.com", full_name="Owner")
        resp = client.post("/api/v1/groups", json={"name": "NF Group"}, headers=_auth_header(token))
        group_id = resp.json()["id"]

        resp2 = client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "ghost@groups-test.com", "role": "member"},
            headers=_auth_header(token),
        )
        assert resp2.status_code == 404
        assert resp2.json()["code"] == "USER_NOT_FOUND_MUST_REGISTER"

    def test_add_member_already_member(self, client):
        token_owner, _ = _register(client, "dupown@groups-test.com", full_name="Dup Owner")
        _register(client, "dupmbr@groups-test.com", full_name="Dup Member")

        resp = client.post("/api/v1/groups", json={"name": "Dup Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "dupmbr@groups-test.com", "role": "member"},
            headers=_auth_header(token_owner),
        )

        resp2 = client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "dupmbr@groups-test.com", "role": "member"},
            headers=_auth_header(token_owner),
        )
        assert resp2.status_code == 409
        assert resp2.json()["code"] == "ALREADY_MEMBER"

    def test_add_member_by_member_forbidden(self, client):
        token_owner, _ = _register(client, "membown@groups-test.com", full_name="Mem Owner")
        token_member, _ = _register(client, "memmbr@groups-test.com", full_name="Mem Member")
        _register(client, "target@groups-test.com", full_name="Target")

        resp = client.post("/api/v1/groups", json={"name": "Mem Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "memmbr@groups-test.com", "role": "member"},
            headers=_auth_header(token_owner),
        )

        resp2 = client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "target@groups-test.com", "role": "member"},
            headers=_auth_header(token_member),
        )
        assert resp2.status_code == 403
        assert resp2.json()["code"] == "FORBIDDEN_NOT_ADMIN"

    def test_add_member_cannot_add_owner(self, client):
        token, _ = _register(client, "noowner@groups-test.com", full_name="No Owner")
        _register(client, "victim@groups-test.com", full_name="Victim")

        resp = client.post("/api/v1/groups", json={"name": "No Owner Group"}, headers=_auth_header(token))
        group_id = resp.json()["id"]

        resp2 = client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "victim@groups-test.com", "role": "owner"},
            headers=_auth_header(token),
        )
        assert resp2.status_code == 422  # Pydantic validation error


# ---------------------------------------------------------------------------
# GET /groups/{group_id}/members — list members
# ---------------------------------------------------------------------------

class TestListMembers:
    def test_list_members_owner_sees_all(self, client):
        token_owner, _ = _register(client, "lm-own@groups-test.com", full_name="LM Owner")
        _register(client, "lm-mbr@groups-test.com", full_name="LM Member")

        resp = client.post("/api/v1/groups", json={"name": "LM Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "lm-mbr@groups-test.com", "role": "member"},
            headers=_auth_header(token_owner),
        )

        resp2 = client.get(f"/api/v1/groups/{group_id}/members", headers=_auth_header(token_owner))
        assert resp2.status_code == 200
        members = resp2.json()
        assert len(members) == 2
        emails = {m["email"] for m in members}
        assert emails == {"lm-own@groups-test.com", "lm-mbr@groups-test.com"}
        for m in members:
            assert "user_id" in m
            assert "email" in m
            assert "full_name" in m
            assert "role" in m
            assert "joined_at" in m

    def test_list_members_admin_can_view(self, client):
        token_owner, _ = _register(client, "lm-adm-own@groups-test.com", full_name="LM Adm Owner")
        token_admin, _ = _register(client, "lm-adm@groups-test.com", full_name="LM Admin")
        _register(client, "lm-adm-mbr@groups-test.com", full_name="LM Adm Member")

        resp = client.post("/api/v1/groups", json={"name": "LM Adm Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "lm-adm@groups-test.com", "role": "admin"},
            headers=_auth_header(token_owner),
        )
        client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "lm-adm-mbr@groups-test.com", "role": "member"},
            headers=_auth_header(token_owner),
        )

        resp2 = client.get(f"/api/v1/groups/{group_id}/members", headers=_auth_header(token_admin))
        assert resp2.status_code == 200
        assert len(resp2.json()) == 3

    def test_list_members_member_can_view(self, client):
        token_owner, _ = _register(client, "lm-mbr-own@groups-test.com", full_name="LM Mbr Owner")
        token_member, _ = _register(client, "lm-mbr2@groups-test.com", full_name="LM Mbr Member")

        resp = client.post("/api/v1/groups", json={"name": "LM Mbr Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "lm-mbr2@groups-test.com", "role": "member"},
            headers=_auth_header(token_owner),
        )

        resp2 = client.get(f"/api/v1/groups/{group_id}/members", headers=_auth_header(token_member))
        assert resp2.status_code == 200
        assert len(resp2.json()) == 2

    def test_list_members_not_group_member_forbidden(self, client):
        token_owner, _ = _register(client, "lm-forb-own@groups-test.com", full_name="LM Forb Owner")
        token_stranger, _ = _register(client, "lm-stranger@groups-test.com", full_name="LM Stranger")

        resp = client.post("/api/v1/groups", json={"name": "LM Forb Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        resp2 = client.get(f"/api/v1/groups/{group_id}/members", headers=_auth_header(token_stranger))
        assert resp2.status_code == 403
        assert resp2.json()["code"] == "NOT_GROUP_MEMBER"

    def test_list_members_includes_correct_roles(self, client):
        token_owner, _ = _register(client, "lm-roles-own@groups-test.com", full_name="LM Roles Owner")
        _register(client, "lm-roles-adm@groups-test.com", full_name="LM Roles Admin")
        _register(client, "lm-roles-mbr@groups-test.com", full_name="LM Roles Member")

        resp = client.post("/api/v1/groups", json={"name": "LM Roles Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "lm-roles-adm@groups-test.com", "role": "admin"},
            headers=_auth_header(token_owner),
        )
        client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "lm-roles-mbr@groups-test.com", "role": "member"},
            headers=_auth_header(token_owner),
        )

        resp2 = client.get(f"/api/v1/groups/{group_id}/members", headers=_auth_header(token_owner))
        assert resp2.status_code == 200
        members = resp2.json()
        assert len(members) == 3

        roles_by_email = {m["email"]: m["role"] for m in members}
        assert roles_by_email["lm-roles-own@groups-test.com"] == "owner"
        assert roles_by_email["lm-roles-adm@groups-test.com"] == "admin"
        assert roles_by_email["lm-roles-mbr@groups-test.com"] == "member"


# ---------------------------------------------------------------------------
# PATCH /groups/{group_id}/members/{user_id} — change role
# ---------------------------------------------------------------------------

class TestChangeMemberRole:
    def test_change_role_success(self, client):
        token_owner, _ = _register(client, "chown@groups-test.com", full_name="Ch Owner")
        _register(client, "chmbr@groups-test.com", full_name="Ch Member")

        resp = client.post("/api/v1/groups", json={"name": "Ch Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        add_resp = client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "chmbr@groups-test.com", "role": "member"},
            headers=_auth_header(token_owner),
        )
        member_user_id = add_resp.json()["user_id"]

        resp2 = client.patch(
            f"/api/v1/groups/{group_id}/members/{member_user_id}",
            json={"role": "admin"},
            headers=_auth_header(token_owner),
        )
        assert resp2.status_code == 200
        assert resp2.json()["role"] == "admin"

    def test_change_role_cannot_modify_owner(self, client, pg_engine):
        token_owner, owner_id = _register(client, "ownown@groups-test.com", full_name="Own Owner")
        token_admin, _ = _register(client, "ownadm@groups-test.com", full_name="Own Admin")

        resp = client.post("/api/v1/groups", json={"name": "Own Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "ownadm@groups-test.com", "role": "admin"},
            headers=_auth_header(token_owner),
        )

        # Admin tries to change owner's role → 403
        resp2 = client.patch(
            f"/api/v1/groups/{group_id}/members/{owner_id}",
            json={"role": "member"},
            headers=_auth_header(token_admin),
        )
        assert resp2.status_code == 403
        assert resp2.json()["code"] == "CANNOT_MODIFY_OWNER"

    def test_change_role_not_member(self, client, pg_engine):
        token_owner, _ = _register(client, "nmown@groups-test.com", full_name="NM Owner")
        _register(client, "nmtarget@groups-test.com", full_name="NM Target")

        resp = client.post("/api/v1/groups", json={"name": "NM Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        target_id = _get_user_id_by_email(pg_engine, "nmtarget@groups-test.com")

        resp2 = client.patch(
            f"/api/v1/groups/{group_id}/members/{target_id}",
            json={"role": "admin"},
            headers=_auth_header(token_owner),
        )
        assert resp2.status_code == 404
        assert resp2.json()["code"] == "NOT_GROUP_MEMBER"


# ---------------------------------------------------------------------------
# DELETE /groups/{group_id}/members/{user_id} — remove member
# ---------------------------------------------------------------------------

class TestRemoveMember:
    def test_remove_member_success(self, client):
        token_owner, _ = _register(client, "rmown@groups-test.com", full_name="Rm Owner")
        _register(client, "rmmbr@groups-test.com", full_name="Rm Member")

        resp = client.post("/api/v1/groups", json={"name": "Rm Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        add_resp = client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "rmmbr@groups-test.com", "role": "member"},
            headers=_auth_header(token_owner),
        )
        member_user_id = add_resp.json()["user_id"]

        resp2 = client.delete(
            f"/api/v1/groups/{group_id}/members/{member_user_id}",
            headers=_auth_header(token_owner),
        )
        assert resp2.status_code == 204

        # Re-add to verify the endpoint works again
        add_resp2 = client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "rmmbr@groups-test.com", "role": "member"},
            headers=_auth_header(token_owner),
        )
        assert add_resp2.status_code == 201

    def test_remove_owner_forbidden(self, client, pg_engine):
        token_owner, owner_id = _register(client, "rmown2@groups-test.com", full_name="Rm Owner2")
        token_admin, _ = _register(client, "rmadm@groups-test.com", full_name="Rm Admin")

        resp = client.post("/api/v1/groups", json={"name": "Rm Guard Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "rmadm@groups-test.com", "role": "admin"},
            headers=_auth_header(token_owner),
        )

        # Admin tries to remove owner → 403
        resp2 = client.delete(
            f"/api/v1/groups/{group_id}/members/{owner_id}",
            headers=_auth_header(token_admin),
        )
        assert resp2.status_code == 403
        assert resp2.json()["code"] == "CANNOT_MODIFY_OWNER"

    def test_remove_not_member(self, client, pg_engine):
        token_owner, _ = _register(client, "rmown3@groups-test.com", full_name="Rm Owner3")
        _register(client, "rmghost@groups-test.com", full_name="Rm Ghost")

        resp = client.post("/api/v1/groups", json={"name": "Rm Ghost Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        ghost_id = _get_user_id_by_email(pg_engine, "rmghost@groups-test.com")

        resp2 = client.delete(
            f"/api/v1/groups/{group_id}/members/{ghost_id}",
            headers=_auth_header(token_owner),
        )
        assert resp2.status_code == 404
        assert resp2.json()["code"] == "NOT_GROUP_MEMBER"


# ---------------------------------------------------------------------------
# Transactional integrity — create_group creates membership in same txn
# ---------------------------------------------------------------------------

class TestTransactionalIntegrity:
    def test_create_group_and_membership_exist_together(self, client):
        token, _ = _register(client, "txn@groups-test.com", full_name="Txn User")
        resp = client.post("/api/v1/groups", json={"name": "Txn Group"}, headers=_auth_header(token))
        group_id = resp.json()["id"]

        resp2 = client.get(f"/api/v1/groups/{group_id}", headers=_auth_header(token))
        assert resp2.status_code == 200
        assert resp2.json()["my_role"] == "owner"

    def test_group_owner_in_list(self, client):
        token, _ = _register(client, "txnlist@groups-test.com", full_name="Txn List")
        resp = client.post("/api/v1/groups", json={"name": "Txn List Group"}, headers=_auth_header(token))
        group_id = resp.json()["id"]

        resp2 = client.get("/api/v1/groups", headers=_auth_header(token))
        assert len(resp2.json()) == 1
        assert resp2.json()[0]["id"] == group_id
        assert resp2.json()[0]["my_role"] == "owner"


# ---------------------------------------------------------------------------
# Helpers — audit
# ---------------------------------------------------------------------------

def _query_audit_log(pg_engine, *, entity_type: str, entity_id: int, action: str) -> dict | None:
    """Query audit_logs for a specific entry."""
    with pg_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT id, actor_user_id, group_id, action, entity_type, entity_id, metadata "
                "FROM audit_logs "
                "WHERE entity_type = :et AND entity_id = :eid AND action = :act "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"et": entity_type, "eid": entity_id, "act": action},
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "actor_user_id": row[1],
            "group_id": row[2],
            "action": row[3],
            "entity_type": row[4],
            "entity_id": row[5],
            "metadata": row[6],
        }


# ---------------------------------------------------------------------------
# PATCH /groups/{group_id}/members/{user_id} — ownership transfer (ADR-011 #8)
# ---------------------------------------------------------------------------

class TestOwnershipTransfer:
    def test_owner_transfers_to_admin(self, client, pg_engine):
        token_owner, owner_id = _register(client, "xfer-own@groups-test.com", full_name="Owner")
        _register(client, "xfer-tgt@groups-test.com", full_name="Target")

        resp = client.post("/api/v1/groups", json={"name": "Xfer Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        add_resp = client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "xfer-tgt@groups-test.com", "role": "admin"},
            headers=_auth_header(token_owner),
        )
        target_id = add_resp.json()["user_id"]

        resp2 = client.patch(
            f"/api/v1/groups/{group_id}/members/{target_id}",
            json={"role": "owner"},
            headers=_auth_header(token_owner),
        )
        assert resp2.status_code == 200
        assert resp2.json()["role"] == "owner"

        # Old owner should now be admin
        get_resp = client.get(f"/api/v1/groups/{group_id}", headers=_auth_header(token_owner))
        assert get_resp.json()["my_role"] == "admin"

        # Audit entry exists
        log = _query_audit_log(pg_engine, entity_type="GroupMembership", entity_id=target_id, action="membership.ownership_transferred")
        assert log is not None
        assert log["actor_user_id"] == owner_id
        assert log["group_id"] == group_id

    def test_admin_cannot_transfer_ownership(self, client):
        token_owner, _ = _register(client, "xadm-own@groups-test.com", full_name="Owner")
        token_admin, _ = _register(client, "xadm-adm@groups-test.com", full_name="Admin")
        _register(client, "xadm-tgt@groups-test.com", full_name="Target")

        resp = client.post("/api/v1/groups", json={"name": "XAdm Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "xadm-adm@groups-test.com", "role": "admin"},
            headers=_auth_header(token_owner),
        )
        add_resp = client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "xadm-tgt@groups-test.com", "role": "member"},
            headers=_auth_header(token_owner),
        )
        target_id = add_resp.json()["user_id"]

        resp2 = client.patch(
            f"/api/v1/groups/{group_id}/members/{target_id}",
            json={"role": "owner"},
            headers=_auth_header(token_admin),
        )
        assert resp2.status_code == 403
        assert resp2.json()["code"] == "FORBIDDEN_NOT_OWNER"

    def test_member_cannot_transfer_ownership(self, client):
        token_owner, _ = _register(client, "xmbr-own@groups-test.com", full_name="Owner")
        token_member, _ = _register(client, "xmbr-mbr@groups-test.com", full_name="Member")
        _register(client, "xmbr-tgt@groups-test.com", full_name="Target")

        resp = client.post("/api/v1/groups", json={"name": "XMbr Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "xmbr-mbr@groups-test.com", "role": "member"},
            headers=_auth_header(token_owner),
        )
        add_resp = client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "xmbr-tgt@groups-test.com", "role": "member"},
            headers=_auth_header(token_owner),
        )
        target_id = add_resp.json()["user_id"]

        resp2 = client.patch(
            f"/api/v1/groups/{group_id}/members/{target_id}",
            json={"role": "owner"},
            headers=_auth_header(token_member),
        )
        assert resp2.status_code == 403
        assert resp2.json()["code"] == "FORBIDDEN_NOT_ADMIN"

    def test_owner_cannot_transfer_to_self(self, client, pg_engine):
        token_owner, owner_id = _register(client, "xself-own@groups-test.com", full_name="Owner")

        resp = client.post("/api/v1/groups", json={"name": "XSelf Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        resp2 = client.patch(
            f"/api/v1/groups/{group_id}/members/{owner_id}",
            json={"role": "owner"},
            headers=_auth_header(token_owner),
        )
        assert resp2.status_code == 400
        assert resp2.json()["code"] == "CANNOT_TRANSFER_TO_SELF"

    def test_transfer_non_member_fails(self, client, pg_engine):
        token_owner, _ = _register(client, "xnm-own@groups-test.com", full_name="Owner")
        _register(client, "xnm-ghost@groups-test.com", full_name="Ghost")

        resp = client.post("/api/v1/groups", json={"name": "XNM Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        ghost_id = _get_user_id_by_email(pg_engine, "xnm-ghost@groups-test.com")

        resp2 = client.patch(
            f"/api/v1/groups/{group_id}/members/{ghost_id}",
            json={"role": "owner"},
            headers=_auth_header(token_owner),
        )
        assert resp2.status_code == 404
        assert resp2.json()["code"] == "NOT_GROUP_MEMBER"


# ---------------------------------------------------------------------------
# POST /groups/{group_id}/members/{user_id}/reset-password (ADR-011 #3)
# ---------------------------------------------------------------------------

class TestResetMemberPassword:
    def test_admin_resets_member_password(self, client, pg_engine):
        token_owner, _ = _register(client, "rst-own@groups-test.com", full_name="Owner")
        _register(client, "rst-mbr@groups-test.com", full_name="Member")

        resp = client.post("/api/v1/groups", json={"name": "Rst Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        add_resp = client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "rst-mbr@groups-test.com", "role": "member"},
            headers=_auth_header(token_owner),
        )
        target_id = add_resp.json()["user_id"]

        # Admin (owner) resets member's password
        resp2 = client.post(
            f"/api/v1/groups/{group_id}/members/{target_id}/reset-password",
            headers=_auth_header(token_owner),
        )
        assert resp2.status_code == 200
        body = resp2.json()
        assert body["user_id"] == target_id
        temp_pw = body["temporary_password"]
        assert len(temp_pw) >= 16

        # Verify temp password hashes correctly in DB
        from app.core.security import verify_password
        with pg_engine.connect() as conn:
            row = conn.execute(
                text("SELECT password_hash FROM users WHERE id = :uid"),
                {"uid": target_id},
            ).fetchone()
            assert verify_password(temp_pw, row[0])

    def test_owner_resets_admin_password(self, client):
        token_owner, _ = _register(client, "rst2-own@groups-test.com", full_name="Owner")
        _register(client, "rst2-adm@groups-test.com", full_name="Admin")

        resp = client.post("/api/v1/groups", json={"name": "Rst2 Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        add_resp = client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "rst2-adm@groups-test.com", "role": "admin"},
            headers=_auth_header(token_owner),
        )
        target_id = add_resp.json()["user_id"]

        resp2 = client.post(
            f"/api/v1/groups/{group_id}/members/{target_id}/reset-password",
            headers=_auth_header(token_owner),
        )
        assert resp2.status_code == 200
        assert "temporary_password" in resp2.json()

    def test_member_cannot_reset_password(self, client):
        token_owner, owner_id = _register(client, "rst3-own@groups-test.com", full_name="Owner")
        token_member, _ = _register(client, "rst3-mbr@groups-test.com", full_name="Member")

        resp = client.post("/api/v1/groups", json={"name": "Rst3 Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "rst3-mbr@groups-test.com", "role": "member"},
            headers=_auth_header(token_owner),
        )

        resp2 = client.post(
            f"/api/v1/groups/{group_id}/members/{owner_id}/reset-password",
            headers=_auth_header(token_member),
        )
        assert resp2.status_code == 403
        assert resp2.json()["code"] == "FORBIDDEN_NOT_ADMIN"

    def test_reset_non_member_fails(self, client, pg_engine):
        token_owner, _ = _register(client, "rst4-own@groups-test.com", full_name="Owner")
        _register(client, "rst4-ghost@groups-test.com", full_name="Ghost")

        resp = client.post("/api/v1/groups", json={"name": "Rst4 Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        ghost_id = _get_user_id_by_email(pg_engine, "rst4-ghost@groups-test.com")

        resp2 = client.post(
            f"/api/v1/groups/{group_id}/members/{ghost_id}/reset-password",
            headers=_auth_header(token_owner),
        )
        assert resp2.status_code == 404
        assert resp2.json()["code"] == "NOT_GROUP_MEMBER"

    def test_reset_creates_audit_log(self, client, pg_engine):
        token_owner, owner_id = _register(client, "rst5-own@groups-test.com", full_name="Owner")
        _register(client, "rst5-mbr@groups-test.com", full_name="Member")

        resp = client.post("/api/v1/groups", json={"name": "Rst5 Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        add_resp = client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "rst5-mbr@groups-test.com", "role": "member"},
            headers=_auth_header(token_owner),
        )
        target_id = add_resp.json()["user_id"]

        resp2 = client.post(
            f"/api/v1/groups/{group_id}/members/{target_id}/reset-password",
            headers=_auth_header(token_owner),
        )
        assert resp2.status_code == 200

        log = _query_audit_log(pg_engine, entity_type="User", entity_id=target_id, action="user.password_reset")
        assert log is not None
        assert log["actor_user_id"] == owner_id
        assert log["group_id"] == group_id
        assert log["metadata"] is None  # password never in metadata

    def test_reset_revokes_old_refresh_tokens(self, client, pg_engine):
        token_owner, _ = _register(client, "rst6-own@groups-test.com", full_name="Owner")
        token_member, _ = _register(client, "rst6-mbr@groups-test.com", full_name="Member")

        resp = client.post("/api/v1/groups", json={"name": "Rst6 Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        add_resp = client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "rst6-mbr@groups-test.com", "role": "member"},
            headers=_auth_header(token_owner),
        )
        target_id = add_resp.json()["user_id"]

        # Member has at least one refresh token (from login)
        with pg_engine.connect() as conn:
            before_count = conn.execute(
                text("SELECT count(*) FROM refresh_tokens WHERE user_id = :uid AND revoked_at IS NULL"),
                {"uid": target_id},
            ).scalar()
            assert before_count >= 1

        # Reset password
        resp2 = client.post(
            f"/api/v1/groups/{group_id}/members/{target_id}/reset-password",
            headers=_auth_header(token_owner),
        )
        assert resp2.status_code == 200

        # All old tokens are revoked
        with pg_engine.connect() as conn:
            active_count = conn.execute(
                text("SELECT count(*) FROM refresh_tokens WHERE user_id = :uid AND revoked_at IS NULL"),
                {"uid": target_id},
            ).scalar()
            assert active_count == 0

    def test_temp_password_works_for_login(self, client, pg_engine):
        token_owner, _ = _register(client, "rst7-own@groups-test.com", full_name="Owner")
        _register(client, "rst7-mbr@groups-test.com", full_name="Member")

        resp = client.post("/api/v1/groups", json={"name": "Rst7 Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        add_resp = client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "rst7-mbr@groups-test.com", "role": "member"},
            headers=_auth_header(token_owner),
        )
        target_id = add_resp.json()["user_id"]

        # Reset password
        resp2 = client.post(
            f"/api/v1/groups/{group_id}/members/{target_id}/reset-password",
            headers=_auth_header(token_owner),
        )
        temp_pw = resp2.json()["temporary_password"]

        # Login with temp password
        login_resp = client.post("/api/v1/auth/login", json={
            "email": "rst7-mbr@groups-test.com",
            "password": temp_pw,
        })
        assert login_resp.status_code == 200
        assert "access_token" in login_resp.json()
