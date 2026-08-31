"""Payment method endpoint integration tests — requires real PostgreSQL."""
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
def _clean_pm_tables(pg_engine):
    _do_cleanup(pg_engine)
    yield
    _do_cleanup(pg_engine)


def _do_cleanup(pg_engine):
    with pg_engine.connect() as conn:
        conn.execute(text("DELETE FROM payment_methods"))
        conn.execute(text("DELETE FROM group_memberships"))
        conn.execute(text("DELETE FROM group_invite_codes"))
        conn.execute(text(
            "DELETE FROM groups WHERE created_by IN "
            "(SELECT id FROM users WHERE email LIKE '%@pm-test%%')"
        ))
        conn.execute(text(
            "DELETE FROM refresh_tokens WHERE user_id IN "
            "(SELECT id FROM users WHERE email LIKE '%@pm-test%%')"
        ))
        conn.execute(text("DELETE FROM users WHERE email LIKE '%@pm-test%%'"))
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
# POST /groups/{group_id}/payment-methods — create payment method
# ---------------------------------------------------------------------------

class TestCreatePaymentMethod:
    def test_create_cash_success(self, client):
        token, _ = _register(client, "cash1@pm-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Cash PM Group")

        resp = client.post(
            f"/api/v1/groups/{group_id}/payment-methods",
            json={
                "kind": "CASH",
                "provider_name": "Efectivo",
                "label": "Efectivo general",
                "holder_name": "Juan Pérez",
            },
            headers=_auth_header(token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["kind"] == "CASH"
        assert body["last4"] is None
        assert body["masked_key"] is None
        assert body["is_active"] is True

    def test_create_cash_with_last4_rejected(self, client):
        token, _ = _register(client, "cash2@pm-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Cash Rejected Group")

        resp = client.post(
            f"/api/v1/groups/{group_id}/payment-methods",
            json={
                "kind": "CASH",
                "provider_name": "Efectivo",
                "label": "Bad Cash",
                "holder_name": "Juan",
                "last4": "1234",
            },
            headers=_auth_header(token),
        )
        assert resp.status_code == 422

    def test_create_bank_account_without_last4_rejected(self, client):
        token, _ = _register(client, "bank1@pm-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Bank Rejected Group")

        resp = client.post(
            f"/api/v1/groups/{group_id}/payment-methods",
            json={
                "kind": "BANK_ACCOUNT",
                "provider_name": "Bancolombia",
                "label": "Cuenta Ahorros",
                "holder_name": "María",
            },
            headers=_auth_header(token),
        )
        assert resp.status_code == 422

    def test_create_bank_account_with_last4_success(self, client):
        token, _ = _register(client, "bank2@pm-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Bank Success Group")

        resp = client.post(
            f"/api/v1/groups/{group_id}/payment-methods",
            json={
                "kind": "BANK_ACCOUNT",
                "provider_name": "Bancolombia",
                "label": "Cuenta Ahorros",
                "last4": "1234",
                "holder_name": "María",
            },
            headers=_auth_header(token),
        )
        assert resp.status_code == 201
        assert resp.json()["last4"] == "1234"

    def test_create_bank_account_invalid_last4_rejected(self, client):
        token, _ = _register(client, "bank3@pm-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Bank Invalid Group")

        resp = client.post(
            f"/api/v1/groups/{group_id}/payment-methods",
            json={
                "kind": "BANK_ACCOUNT",
                "provider_name": "Bancolombia",
                "label": "Cuenta",
                "last4": "12",
                "holder_name": "María",
            },
            headers=_auth_header(token),
        )
        assert resp.status_code == 422

    def test_create_digital_wallet_without_masked_key_rejected(self, client):
        token, _ = _register(client, "wallet1@pm-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Wallet Rejected Group")

        resp = client.post(
            f"/api/v1/groups/{group_id}/payment-methods",
            json={
                "kind": "DIGITAL_WALLET",
                "provider_name": "Nequi",
                "label": "Nequi",
                "holder_name": "Carlos",
            },
            headers=_auth_header(token),
        )
        assert resp.status_code == 422

    def test_create_digital_wallet_with_masked_key_success(self, client):
        token, _ = _register(client, "wallet2@pm-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Wallet Success Group")

        resp = client.post(
            f"/api/v1/groups/{group_id}/payment-methods",
            json={
                "kind": "DIGITAL_WALLET",
                "provider_name": "Nequi",
                "label": "Nequi",
                "masked_key": "****1234",
                "holder_name": "Carlos",
            },
            headers=_auth_header(token),
        )
        assert resp.status_code == 201
        assert resp.json()["masked_key"] == "****1234"

    def test_create_debit_card_requires_last4(self, client):
        token, _ = _register(client, "debit1@pm-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Debit Rejected Group")

        resp = client.post(
            f"/api/v1/groups/{group_id}/payment-methods",
            json={
                "kind": "DEBIT_CARD",
                "provider_name": "Banco AV Villas",
                "label": "Débito",
                "holder_name": "Ana",
            },
            headers=_auth_header(token),
        )
        assert resp.status_code == 422

    def test_create_credit_card_requires_last4(self, client):
        token, _ = _register(client, "credit1@pm-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Credit Rejected Group")

        resp = client.post(
            f"/api/v1/groups/{group_id}/payment-methods",
            json={
                "kind": "CREDIT_CARD",
                "provider_name": "Banco Davivienda",
                "label": "Crédito",
                "holder_name": "Pedro",
            },
            headers=_auth_header(token),
        )
        assert resp.status_code == 422

    def test_create_bre_b_requires_masked_key(self, client):
        token, _ = _register(client, "bre1@pm-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Bre Rejected Group")

        resp = client.post(
            f"/api/v1/groups/{group_id}/payment-methods",
            json={
                "kind": "BRE_B",
                "provider_name": "Bre-B",
                "label": "Bre-B",
                "holder_name": "Luis",
            },
            headers=_auth_header(token),
        )
        assert resp.status_code == 422

    def test_create_pse_requires_masked_key(self, client):
        token, _ = _register(client, "pse1@pm-test.com", full_name="Admin")
        group_id = _create_group(client, token, "PSE Rejected Group")

        resp = client.post(
            f"/api/v1/groups/{group_id}/payment-methods",
            json={
                "kind": "PSE",
                "provider_name": "PSE",
                "label": "PSE",
                "holder_name": "Sandra",
            },
            headers=_auth_header(token),
        )
        assert resp.status_code == 422

    def test_create_other_no_reference_required(self, client):
        token, _ = _register(client, "other1@pm-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Other PM Group")

        resp = client.post(
            f"/api/v1/groups/{group_id}/payment-methods",
            json={
                "kind": "OTHER",
                "provider_name": "Otro",
                "label": "Otro medio",
                "holder_name": "Roberto",
            },
            headers=_auth_header(token),
        )
        assert resp.status_code == 201
        assert resp.json()["last4"] is None
        assert resp.json()["masked_key"] is None

    def test_create_member_forbidden(self, client):
        token_owner, _ = _register(client, "pmown@pm-test.com", full_name="Owner")
        token_member, _ = _register(client, "pmmem@pm-test.com", full_name="Member")
        group_id = _create_group(client, token_owner, "PM Forbidden Group")

        client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "pmmem@pm-test.com", "role": "member"},
            headers=_auth_header(token_owner),
        )

        resp = client.post(
            f"/api/v1/groups/{group_id}/payment-methods",
            json={
                "kind": "CASH",
                "provider_name": "Efectivo",
                "label": "Test",
                "holder_name": "Member",
            },
            headers=_auth_header(token_member),
        )
        assert resp.status_code == 403
        assert resp.json()["code"] == "FORBIDDEN_NOT_ADMIN"


# ---------------------------------------------------------------------------
# GET /groups/{group_id}/payment-methods — list payment methods
# ---------------------------------------------------------------------------

class TestListPaymentMethods:
    def test_list_empty_group(self, client):
        token, _ = _register(client, "pmlist1@pm-test.com", full_name="Lister")
        group_id = _create_group(client, token, "Empty PM Group")

        resp = client.get(
            f"/api/v1/groups/{group_id}/payment-methods",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_includes_created(self, client):
        token, _ = _register(client, "pmlist2@pm-test.com", full_name="Lister")
        group_id = _create_group(client, token, "PM List Group")

        # Create two payment methods
        client.post(
            f"/api/v1/groups/{group_id}/payment-methods",
            json={
                "kind": "CASH",
                "provider_name": "Efectivo",
                "label": "Efectivo",
                "holder_name": "A",
            },
            headers=_auth_header(token),
        )
        client.post(
            f"/api/v1/groups/{group_id}/payment-methods",
            json={
                "kind": "BANK_ACCOUNT",
                "provider_name": "Bancolombia",
                "label": "Cuenta",
                "last4": "5678",
                "holder_name": "B",
            },
            headers=_auth_header(token),
        )

        resp = client.get(
            f"/api/v1/groups/{group_id}/payment-methods",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_requires_membership(self, client):
        token_owner, _ = _register(client, "pmlistown@pm-test.com", full_name="Owner")
        token_stranger, _ = _register(client, "pmliststr@pm-test.com", full_name="Stranger")
        group_id = _create_group(client, token_owner, "Private PM Group")

        resp = client.get(
            f"/api/v1/groups/{group_id}/payment-methods",
            headers=_auth_header(token_stranger),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /groups/{group_id}/payment-methods/{id} — update payment method
# ---------------------------------------------------------------------------

class TestUpdatePaymentMethod:
    def test_update_label_success(self, client):
        token, _ = _register(client, "pmupd1@pm-test.com", full_name="Admin")
        group_id = _create_group(client, token, "PM Update Group")

        create_resp = client.post(
            f"/api/v1/groups/{group_id}/payment-methods",
            json={
                "kind": "CASH",
                "provider_name": "Efectivo",
                "label": "Old Label",
                "holder_name": "Test",
            },
            headers=_auth_header(token),
        )
        pm_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/groups/{group_id}/payment-methods/{pm_id}",
            json={"label": "New Label"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        assert resp.json()["label"] == "New Label"

    def test_update_is_active_success(self, client):
        token, _ = _register(client, "pmupd2@pm-test.com", full_name="Admin")
        group_id = _create_group(client, token, "PM Deactivate Group")

        create_resp = client.post(
            f"/api/v1/groups/{group_id}/payment-methods",
            json={
                "kind": "CASH",
                "provider_name": "Efectivo",
                "label": "Active PM",
                "holder_name": "Test",
            },
            headers=_auth_header(token),
        )
        pm_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/groups/{group_id}/payment-methods/{pm_id}",
            json={"is_active": False},
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_update_not_found(self, client):
        token, _ = _register(client, "pmupd3@pm-test.com", full_name="Admin")
        group_id = _create_group(client, token, "PM NF Group")

        resp = client.patch(
            f"/api/v1/groups/{group_id}/payment-methods/999999",
            json={"label": "Ghost"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == "PAYMENT_METHOD_NOT_FOUND"

    def test_update_other_group_forbidden(self, client):
        token_a, _ = _register(client, "pmupda@pm-test.com", full_name="AdminA")
        token_b, _ = _register(client, "pmupdb@pm-test.com", full_name="AdminB")
        group_a = _create_group(client, token_a, "PM Group A")
        group_b = _create_group(client, token_b, "PM Group B")

        create_resp = client.post(
            f"/api/v1/groups/{group_a}/payment-methods",
            json={
                "kind": "CASH",
                "provider_name": "Efectivo",
                "label": "PM A",
                "holder_name": "A",
            },
            headers=_auth_header(token_a),
        )
        pm_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/groups/{group_b}/payment-methods/{pm_id}",
            json={"label": "Hacked"},
            headers=_auth_header(token_b),
        )
        assert resp.status_code == 404

    def test_update_member_forbidden(self, client):
        token_owner, _ = _register(client, "pmupdow@pm-test.com", full_name="Owner")
        token_member, _ = _register(client, "pmupdmem@pm-test.com", full_name="Member")
        group_id = _create_group(client, token_owner, "PM Upd Forbidden Group")

        client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "pmupdmem@pm-test.com", "role": "member"},
            headers=_auth_header(token_owner),
        )

        create_resp = client.post(
            f"/api/v1/groups/{group_id}/payment-methods",
            json={
                "kind": "CASH",
                "provider_name": "Efectivo",
                "label": "Test",
                "holder_name": "Test",
            },
            headers=_auth_header(token_owner),
        )
        pm_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/groups/{group_id}/payment-methods/{pm_id}",
            json={"label": "Hacked"},
            headers=_auth_header(token_member),
        )
        assert resp.status_code == 403
        assert resp.json()["code"] == "FORBIDDEN_NOT_ADMIN"

    def test_update_empty_body_rejected(self, client):
        token, _ = _register(client, "pmupd4@pm-test.com", full_name="Admin")
        group_id = _create_group(client, token, "PM Empty Update Group")

        create_resp = client.post(
            f"/api/v1/groups/{group_id}/payment-methods",
            json={
                "kind": "CASH",
                "provider_name": "Efectivo",
                "label": "Test",
                "holder_name": "Test",
            },
            headers=_auth_header(token),
        )
        pm_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/groups/{group_id}/payment-methods/{pm_id}",
            json={},
            headers=_auth_header(token),
        )
        assert resp.status_code == 422
