"""Obligation endpoint integration tests — requires real PostgreSQL."""
import os
from datetime import date, timedelta

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
def _clean_obligation_tables(pg_engine):
    _do_cleanup(pg_engine)
    yield
    _do_cleanup(pg_engine)


def _do_cleanup(pg_engine):
    with pg_engine.connect() as conn:
        conn.execute(text("DELETE FROM obligation_periods"))
        conn.execute(text("DELETE FROM obligations"))
        conn.execute(text("DELETE FROM payment_methods"))
        conn.execute(text("DELETE FROM categories WHERE group_id IS NOT NULL"))
        conn.execute(text("DELETE FROM group_memberships"))
        conn.execute(text("DELETE FROM group_invite_codes"))
        conn.execute(text(
            "DELETE FROM groups WHERE created_by IN "
            "(SELECT id FROM users WHERE email LIKE '%@obl-test%%')"
        ))
        conn.execute(text(
            "DELETE FROM refresh_tokens WHERE user_id IN "
            "(SELECT id FROM users WHERE email LIKE '%@obl-test%%')"
        ))
        conn.execute(text("DELETE FROM users WHERE email LIKE '%@obl-test%%'"))
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


def _add_member(client, owner_token: str, group_id: int, member_email: str, role: str = "member"):
    resp = client.post(
        f"/api/v1/groups/{group_id}/members",
        json={"email": member_email, "role": role},
        headers=_auth_header(owner_token),
    )
    assert resp.status_code == 201


def _create_obligation(client, token: str, group_id: int, **overrides) -> dict:
    data = {
        "name": "Internet mensual",
        "expected_amount_cents": 8000000,
        "due_day": 15,
        "start_date": "2026-01-01",
        "periodicity": "MONTHLY",
    }
    data.update(overrides)
    resp = client.post(
        f"/api/v1/groups/{group_id}/obligations",
        json=data,
        headers=_auth_header(token),
    )
    assert resp.status_code == 201, f"Create obligation failed: {resp.status_code} {resp.json()}"
    return resp.json()


# ---------------------------------------------------------------------------
# POST /groups/{group_id}/obligations — create obligation
# ---------------------------------------------------------------------------

class TestCreateObligation:
    def test_create_minimal_monthly(self, client):
        token, _ = _register(client, "oblcrt1@obl-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Obl Minimal Group")

        body = _create_obligation(client, token, group_id)
        assert body["name"] == "Internet mensual"
        assert body["periodicity"] == "MONTHLY"
        assert body["due_day"] == 15
        assert body["due_month"] is None
        assert body["is_active"] is True
        assert body["currency"] == "COP"

    def test_create_with_all_fields(self, client):
        token, _ = _register(client, "oblcrt2@obl-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Obl Full Group")

        resp = client.post(
            f"/api/v1/groups/{group_id}/obligations",
            json={
                "name": "Seguro vehicular",
                "provider_name": "Seguros Bolívar",
                "external_reference": "POL-12345",
                "notes": "Pagar antes del 15",
                "currency": "COP",
                "expected_amount_cents": 120000000,
                "is_variable_amount": False,
                "is_subscription": False,
                "auto_debit": True,
                "is_essential": True,
                "periodicity": "ANNUAL",
                "due_day": 15,
                "due_month": 3,
                "start_date": "2025-01-01",
                "end_date": "2028-12-31",
            },
            headers=_auth_header(token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["periodicity"] == "ANNUAL"
        assert body["due_month"] == 3
        assert body["provider_name"] == "Seguros Bolívar"
        assert body["external_reference"] == "POL-12345"
        assert body["auto_debit"] is True

    def test_create_annual_without_due_month_rejected(self, client):
        token, _ = _register(client, "oblcrt3@obl-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Obl Annual No Month")

        resp = client.post(
            f"/api/v1/groups/{group_id}/obligations",
            json={
                "name": "Annual without month",
                "expected_amount_cents": 100000,
                "due_day": 15,
                "periodicity": "ANNUAL",
                "start_date": "2026-01-01",
            },
            headers=_auth_header(token),
        )
        assert resp.status_code == 422

    def test_create_monthly_with_due_month_rejected(self, client):
        token, _ = _register(client, "oblcrt4@obl-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Obl Monthly With Month")

        resp = client.post(
            f"/api/v1/groups/{group_id}/obligations",
            json={
                "name": "Monthly with due_month",
                "expected_amount_cents": 100000,
                "due_day": 15,
                "due_month": 6,
                "periodicity": "MONTHLY",
                "start_date": "2026-01-01",
            },
            headers=_auth_header(token),
        )
        assert resp.status_code == 422

    def test_create_end_date_before_start_date_rejected(self, client):
        token, _ = _register(client, "oblcrt5@obl-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Obl Bad Dates")

        resp = client.post(
            f"/api/v1/groups/{group_id}/obligations",
            json={
                "name": "Bad dates",
                "expected_amount_cents": 100000,
                "due_day": 15,
                "periodicity": "MONTHLY",
                "start_date": "2026-06-01",
                "end_date": "2026-01-01",
            },
            headers=_auth_header(token),
        )
        assert resp.status_code == 422

    def test_create_category_from_other_group_rejected(self, client):
        token_a, _ = _register(client, "oblcrt6a@obl-test.com", full_name="AdminA")
        token_b, _ = _register(client, "oblcrt6b@obl-test.com", full_name="AdminB")
        group_a = _create_group(client, token_a, "Obl Group A")
        group_b = _create_group(client, token_b, "Obl Group B")

        # Create custom category in group A
        cat_resp = client.post(
            f"/api/v1/groups/{group_a}/categories",
            json={"name": "My Custom Cat"},
            headers=_auth_header(token_a),
        )
        assert cat_resp.status_code == 201
        cat_id = cat_resp.json()["id"]

        # Try to use it in group B
        resp = client.post(
            f"/api/v1/groups/{group_b}/obligations",
            json={
                "name": "Cross-group cat",
                "expected_amount_cents": 100000,
                "due_day": 15,
                "periodicity": "MONTHLY",
                "start_date": "2026-01-01",
                "category_id": cat_id,
            },
            headers=_auth_header(token_b),
        )
        assert resp.status_code == 400
        assert resp.json()["code"] == "CATEGORY_NOT_IN_GROUP"

    def test_create_responsible_not_member_rejected(self, client):
        token, _ = _register(client, "oblcrt7@obl-test.com", full_name="Admin")
        token_stranger, stranger_id = _register(client, "oblcrt7str@obl-test.com", full_name="Stranger")
        group_id = _create_group(client, token, "Obl Responsible Group")

        resp = client.post(
            f"/api/v1/groups/{group_id}/obligations",
            json={
                "name": "Bad responsible",
                "expected_amount_cents": 100000,
                "due_day": 15,
                "periodicity": "MONTHLY",
                "start_date": "2026-01-01",
                "responsible_user_id": stranger_id,
            },
            headers=_auth_header(token),
        )
        assert resp.status_code == 400
        assert resp.json()["code"] == "RESPONSIBLE_NOT_GROUP_MEMBER"

    def test_create_member_forbidden(self, client):
        token_owner, _ = _register(client, "oblcrt8@obl-test.com", full_name="Owner")
        token_member, _ = _register(client, "oblcrt8m@obl-test.com", full_name="Member")
        group_id = _create_group(client, token_owner, "Obl Member Forbidden")
        _add_member(client, token_owner, group_id, "oblcrt8m@obl-test.com")

        resp = client.post(
            f"/api/v1/groups/{group_id}/obligations",
            json={
                "name": "Should fail",
                "expected_amount_cents": 100000,
                "due_day": 15,
                "periodicity": "MONTHLY",
                "start_date": "2026-01-01",
            },
            headers=_auth_header(token_member),
        )
        assert resp.status_code == 403
        assert resp.json()["code"] == "FORBIDDEN_NOT_ADMIN"

    def test_create_generates_periods(self, client):
        token, _ = _register(client, "oblcrt9@obl-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Obl Periods Gen")

        _create_obligation(
            client, token, group_id,
            name="Auto periods",
            start_date="2026-06-01",
            periodicity="MONTHLY",
            due_day=10,
        )

        resp = client.get(
            f"/api/v1/groups/{group_id}/periods",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        periods = resp.json()
        assert len(periods) >= 1  # At least one period generated


# ---------------------------------------------------------------------------
# GET /groups/{group_id}/obligations — list obligations
# ---------------------------------------------------------------------------

class TestListObligations:
    def test_list_empty_group(self, client):
        token, _ = _register(client, "obllst1@obl-test.com", full_name="Lister")
        group_id = _create_group(client, token, "Obl Empty List")

        resp = client.get(
            f"/api/v1/groups/{group_id}/obligations",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_includes_active(self, client):
        token, _ = _register(client, "obllst2@obl-test.com", full_name="Lister")
        group_id = _create_group(client, token, "Obl List Active")

        _create_obligation(client, token, group_id, name="Active Obl")
        _create_obligation(client, token, group_id, name="Active Obl 2")

        resp = client.get(
            f"/api/v1/groups/{group_id}/obligations",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_excludes_deactivated(self, client):
        token, _ = _register(client, "obllst3@obl-test.com", full_name="Lister")
        group_id = _create_group(client, token, "Obl List No Deact")

        body = _create_obligation(client, token, group_id, name="To Deactivate")
        obl_id = body["id"]

        # Deactivate it
        client.delete(
            f"/api/v1/groups/{group_id}/obligations/{obl_id}",
            headers=_auth_header(token),
        )

        resp = client.get(
            f"/api/v1/groups/{group_id}/obligations",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_list_requires_membership(self, client):
        token_owner, _ = _register(client, "obllst4@obl-test.com", full_name="Owner")
        token_stranger, _ = _register(client, "obllst4s@obl-test.com", full_name="Stranger")
        group_id = _create_group(client, token_owner, "Obl Private List")

        resp = client.get(
            f"/api/v1/groups/{group_id}/obligations",
            headers=_auth_header(token_stranger),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /groups/{group_id}/obligations/{id} — get obligation
# ---------------------------------------------------------------------------

class TestGetObligation:
    def test_get_success(self, client):
        token, _ = _register(client, "oblget1@obl-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Obl Get Group")

        body = _create_obligation(client, token, group_id)
        obl_id = body["id"]

        resp = client.get(
            f"/api/v1/groups/{group_id}/obligations/{obl_id}",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == obl_id

    def test_get_not_found(self, client):
        token, _ = _register(client, "oblget2@obl-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Obl Get NF")

        resp = client.get(
            f"/api/v1/groups/{group_id}/obligations/999999",
            headers=_auth_header(token),
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == "OBLIGATION_NOT_FOUND"

    def test_get_other_group_forbidden(self, client):
        token_a, _ = _register(client, "oblget3a@obl-test.com", full_name="AdminA")
        token_b, _ = _register(client, "oblget3b@obl-test.com", full_name="AdminB")
        group_a = _create_group(client, token_a, "Obl Get Group A")
        group_b = _create_group(client, token_b, "Obl Get Group B")

        body = _create_obligation(client, token_a, group_a)
        obl_id = body["id"]

        resp = client.get(
            f"/api/v1/groups/{group_b}/obligations/{obl_id}",
            headers=_auth_header(token_b),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /groups/{group_id}/obligations/{id} — update obligation
# ---------------------------------------------------------------------------

class TestUpdateObligation:
    def test_update_name(self, client):
        token, _ = _register(client, "oblupd1@obl-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Obl Update Group")

        body = _create_obligation(client, token, group_id)
        obl_id = body["id"]

        resp = client.patch(
            f"/api/v1/groups/{group_id}/obligations/{obl_id}",
            json={"name": "Updated Name"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"

    def test_update_not_found(self, client):
        token, _ = _register(client, "oblupd2@obl-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Obl Update NF")

        resp = client.patch(
            f"/api/v1/groups/{group_id}/obligations/999999",
            json={"name": "Ghost"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 404

    def test_update_member_forbidden(self, client):
        token_owner, _ = _register(client, "oblupd3@obl-test.com", full_name="Owner")
        token_member, _ = _register(client, "oblupd3m@obl-test.com", full_name="Member")
        group_id = _create_group(client, token_owner, "Obl Update Forbidden")
        _add_member(client, token_owner, group_id, "oblupd3m@obl-test.com")

        body = _create_obligation(client, token_owner, group_id)
        obl_id = body["id"]

        resp = client.patch(
            f"/api/v1/groups/{group_id}/obligations/{obl_id}",
            json={"name": "Hacked"},
            headers=_auth_header(token_member),
        )
        assert resp.status_code == 403

    def test_update_empty_body_rejected(self, client):
        token, _ = _register(client, "oblupd4@obl-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Obl Update Empty")

        body = _create_obligation(client, token, group_id)
        obl_id = body["id"]

        resp = client.patch(
            f"/api/v1/groups/{group_id}/obligations/{obl_id}",
            json={},
            headers=_auth_header(token),
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /groups/{group_id}/obligations/{id} — soft-delete
# ---------------------------------------------------------------------------

class TestDeactivateObligation:
    def test_deactivate_success(self, client, pg_engine):
        token, _ = _register(client, "obldel1@obl-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Obl Delete Group")

        body = _create_obligation(client, token, group_id)
        obl_id = body["id"]

        resp = client.delete(
            f"/api/v1/groups/{group_id}/obligations/{obl_id}",
            headers=_auth_header(token),
        )
        assert resp.status_code == 204

        # Verify it's soft-deleted, not hard-deleted
        with pg_engine.connect() as conn:
            result = conn.execute(
                text("SELECT is_active FROM obligations WHERE id = :id"),
                {"id": obl_id},
            ).fetchone()
            assert result is not None
            assert result[0] is False

    def test_deactivate_not_found(self, client):
        token, _ = _register(client, "obldel2@obl-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Obl Delete NF")

        resp = client.delete(
            f"/api/v1/groups/{group_id}/obligations/999999",
            headers=_auth_header(token),
        )
        assert resp.status_code == 404

    def test_deactivate_member_forbidden(self, client):
        token_owner, _ = _register(client, "obldel3@obl-test.com", full_name="Owner")
        token_member, _ = _register(client, "obldel3m@obl-test.com", full_name="Member")
        group_id = _create_group(client, token_owner, "Obl Del Forbidden")
        _add_member(client, token_owner, group_id, "obldel3m@obl-test.com")

        body = _create_obligation(client, token_owner, group_id)
        obl_id = body["id"]

        resp = client.delete(
            f"/api/v1/groups/{group_id}/obligations/{obl_id}",
            headers=_auth_header(token_member),
        )
        assert resp.status_code == 403

    def test_deactivate_preserves_row(self, client, pg_engine):
        token, _ = _register(client, "obldel4@obl-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Obl Del Preserves")

        body = _create_obligation(client, token, group_id)
        obl_id = body["id"]

        client.delete(
            f"/api/v1/groups/{group_id}/obligations/{obl_id}",
            headers=_auth_header(token),
        )

        # The row still exists
        with pg_engine.connect() as conn:
            result = conn.execute(
                text("SELECT COUNT(*) FROM obligations WHERE id = :id"),
                {"id": obl_id},
            ).fetchone()
            assert result[0] == 1
