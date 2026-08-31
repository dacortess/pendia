"""Category endpoint integration tests — requires real PostgreSQL."""
import os

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
def _clean_category_tables(pg_engine):
    _do_cleanup(pg_engine)
    yield
    _do_cleanup(pg_engine)


def _do_cleanup(pg_engine):
    with pg_engine.connect() as conn:
        conn.execute(text("DELETE FROM categories WHERE group_id IS NOT NULL"))
        conn.execute(text("DELETE FROM group_memberships"))
        conn.execute(text("DELETE FROM group_invite_codes"))
        conn.execute(text(
            "DELETE FROM groups WHERE created_by IN "
            "(SELECT id FROM users WHERE email LIKE '%@cat-test%%')"
        ))
        conn.execute(text(
            "DELETE FROM refresh_tokens WHERE user_id IN "
            "(SELECT id FROM users WHERE email LIKE '%@cat-test%%')"
        ))
        conn.execute(text("DELETE FROM users WHERE email LIKE '%@cat-test%%'"))
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


# ---------------------------------------------------------------------------
# GET /groups/{group_id}/categories — list categories
# ---------------------------------------------------------------------------

class TestListCategories:
    def test_list_empty_group(self, client):
        token, _ = _register(client, "list1@cat-test.com", full_name="Lister")
        group_id = _create_group(client, token, "Empty Cat Group")

        resp = client.get(
            f"/api/v1/groups/{group_id}/categories",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        # May include system categories if seeded, but no custom ones yet
        for cat in body:
            assert cat["is_system"] is True or cat["group_id"] is None or cat["group_id"] == group_id

    def test_list_includes_created_custom(self, client):
        token, _ = _register(client, "list2@cat-test.com", full_name="Lister")
        group_id = _create_group(client, token, "Cat List Group")

        # Create a custom category
        resp_create = client.post(
            f"/api/v1/groups/{group_id}/categories",
            json={"name": "Mi Custom Cat", "icon": "star"},
            headers=_auth_header(token),
        )
        assert resp_create.status_code == 201

        resp = client.get(
            f"/api/v1/groups/{group_id}/categories",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert "Mi Custom Cat" in names

    def test_list_includes_system_categories(self, client, pg_engine):
        # Ensure at least one system category exists
        with pg_engine.connect() as conn:
            conn.execute(text(
                "INSERT INTO categories (group_id, name, icon) VALUES (NULL, 'Test System Cat', 'zap') "
                "ON CONFLICT DO NOTHING"
            ))
            conn.commit()

        token, _ = _register(client, "list3@cat-test.com", full_name="Lister")
        group_id = _create_group(client, token, "System Cat Group")

        resp = client.get(
            f"/api/v1/groups/{group_id}/categories",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        system_cats = [c for c in resp.json() if c["is_system"] is True]
        assert len(system_cats) >= 1

    def test_list_requires_membership(self, client):
        token_owner, _ = _register(client, "listown@cat-test.com", full_name="Owner")
        token_stranger, _ = _register(client, "liststr@cat-test.com", full_name="Stranger")
        group_id = _create_group(client, token_owner, "Private Cat Group")

        resp = client.get(
            f"/api/v1/groups/{group_id}/categories",
            headers=_auth_header(token_stranger),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /groups/{group_id}/categories — create category
# ---------------------------------------------------------------------------

class TestCreateCategory:
    def test_create_success(self, client):
        token, _ = _register(client, "create1@cat-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Create Cat Group")

        resp = client.post(
            f"/api/v1/groups/{group_id}/categories",
            json={"name": "Mi Categoría", "icon": "heart"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Mi Categoría"
        assert body["icon"] == "heart"
        assert body["group_id"] == group_id
        assert body["is_system"] is False

    def test_create_without_icon(self, client):
        token, _ = _register(client, "create2@cat-test.com", full_name="Admin")
        group_id = _create_group(client, token, "No Icon Cat Group")

        resp = client.post(
            f"/api/v1/groups/{group_id}/categories",
            json={"name": "Sin Icono"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 201
        assert resp.json()["icon"] is None

    def test_create_duplicate_name_same_group(self, client):
        token, _ = _register(client, "create3@cat-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Dup Cat Group")

        resp1 = client.post(
            f"/api/v1/groups/{group_id}/categories",
            json={"name": "Duplicada"},
            headers=_auth_header(token),
        )
        assert resp1.status_code == 201

        resp2 = client.post(
            f"/api/v1/groups/{group_id}/categories",
            json={"name": "Duplicada"},
            headers=_auth_header(token),
        )
        assert resp2.status_code == 409
        assert resp2.json()["code"] == "CATEGORY_NAME_ALREADY_EXISTS"

    def test_create_same_name_different_groups(self, client):
        token_a, _ = _register(client, "create4a@cat-test.com", full_name="AdminA")
        token_b, _ = _register(client, "create4b@cat-test.com", full_name="AdminB")
        group_a = _create_group(client, token_a, "Group A")
        group_b = _create_group(client, token_b, "Group B")

        resp_a = client.post(
            f"/api/v1/groups/{group_a}/categories",
            json={"name": "Salud"},
            headers=_auth_header(token_a),
        )
        assert resp_a.status_code == 201

        resp_b = client.post(
            f"/api/v1/groups/{group_b}/categories",
            json={"name": "Salud"},
            headers=_auth_header(token_b),
        )
        assert resp_b.status_code == 201

    def test_create_member_forbidden(self, client):
        token_owner, _ = _register(client, "createown@cat-test.com", full_name="Owner")
        token_member, _ = _register(client, "createmem@cat-test.com", full_name="Member")
        group_id = _create_group(client, token_owner, "Member Forbidden Cat Group")

        client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "createmem@cat-test.com", "role": "member"},
            headers=_auth_header(token_owner),
        )

        resp = client.post(
            f"/api/v1/groups/{group_id}/categories",
            json={"name": "Should Fail"},
            headers=_auth_header(token_member),
        )
        assert resp.status_code == 403
        assert resp.json()["code"] == "FORBIDDEN_NOT_ADMIN"

    def test_create_empty_name_rejected(self, client):
        token, _ = _register(client, "create5@cat-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Empty Name Group")

        resp = client.post(
            f"/api/v1/groups/{group_id}/categories",
            json={"name": ""},
            headers=_auth_header(token),
        )
        assert resp.status_code == 422
