"""Payment endpoint integration tests — requires real PostgreSQL."""
import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

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

BOGOTA = ZoneInfo("America/Bogota")


def _today():
    return datetime.now(BOGOTA).date()


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
def _clean_payment_tables(pg_engine):
    _do_cleanup(pg_engine)
    yield
    _do_cleanup(pg_engine)


def _do_cleanup(pg_engine):
    with pg_engine.connect() as conn:
        conn.execute(text("DELETE FROM payments"))
        conn.execute(text("DELETE FROM obligation_periods"))
        conn.execute(text("DELETE FROM obligations"))
        conn.execute(text("DELETE FROM payment_methods"))
        conn.execute(text("DELETE FROM categories WHERE group_id IS NOT NULL"))
        conn.execute(text("DELETE FROM group_memberships"))
        conn.execute(text("DELETE FROM group_invite_codes"))
        conn.execute(text(
            "DELETE FROM groups WHERE created_by IN "
            "(SELECT id FROM users WHERE email LIKE '%@pay-test%%')"
        ))
        conn.execute(text(
            "DELETE FROM refresh_tokens WHERE user_id IN "
            "(SELECT id FROM users WHERE email LIKE '%@pay-test%%')"
        ))
        conn.execute(text("DELETE FROM users WHERE email LIKE '%@pay-test%%'"))
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
        "name": "Test obligation",
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


def _get_future_period(client, token: str, group_id: int) -> dict:
    """Get a PENDIENTE period from the group (one that hasn't been paid)."""
    resp = client.get(
        f"/api/v1/groups/{group_id}/periods?status=PENDIENTE",
        headers=_auth_header(token),
    )
    assert resp.status_code == 200
    periods = resp.json()
    assert len(periods) > 0, "No PENDIENTE periods found"
    return periods[0]


def _get_past_period(client, token: str, group_id: int) -> dict:
    """Get a VENCIDO period from the group."""
    resp = client.get(
        f"/api/v1/groups/{group_id}/periods?status=VENCIDO",
        headers=_auth_header(token),
    )
    assert resp.status_code == 200
    periods = resp.json()
    assert len(periods) > 0, "No VENCIDO periods found"
    return periods[0]


def _register_payment(client, token: str, group_id: int, period_id: int, **overrides) -> dict:
    data = {
        "amount_cents": 8000000,
        "currency": "COP",
        "paid_at": _today().isoformat(),
    }
    data.update(overrides)
    resp = client.post(
        f"/api/v1/groups/{group_id}/periods/{period_id}/payments",
        json=data,
        headers=_auth_header(token),
    )
    return resp


# ---------------------------------------------------------------------------
# POST /groups/{group_id}/periods/{id}/payments — register payment
# ---------------------------------------------------------------------------

class TestRegisterPayment:
    def test_register_as_owner(self, client, pg_engine):
        """Owner can register a payment → 201, period becomes PAGADO."""
        token, _ = _register(client, "payrt1@pay-test.com", full_name="Owner")
        group_id = _create_group(client, token, "Pay Owner Group")
        _create_obligation(client, token, group_id, name="Obl 1", start_date="2026-06-01")
        period = _get_future_period(client, token, group_id)

        resp = _register_payment(client, token, group_id, period["id"])
        assert resp.status_code == 201
        body = resp.json()
        assert body["obligation_period_id"] == period["id"]
        assert body["amount_cents"] == 8000000
        assert body["currency"] == "COP"
        assert body["voided_at"] is None

        # Verify period status changed to PAGADO
        resp_period = client.get(
            f"/api/v1/groups/{group_id}/periods/{period['id']}",
            headers=_auth_header(token),
        )
        assert resp_period.status_code == 200
        assert resp_period.json()["status"] == "PAGADO"

    def test_register_as_admin(self, client):
        """Admin can register a payment → 201."""
        token_owner, _ = _register(client, "payrt2o@pay-test.com", full_name="Owner")
        token_admin, _ = _register(client, "payrt2a@pay-test.com", full_name="Admin")
        group_id = _create_group(client, token_owner, "Pay Admin Group")
        _add_member(client, token_owner, group_id, "payrt2a@pay-test.com", role="admin")
        _create_obligation(client, token_owner, group_id, name="Obl 2", start_date="2026-06-01")
        period = _get_future_period(client, token_owner, group_id)

        resp = _register_payment(client, token_admin, group_id, period["id"])
        assert resp.status_code == 201

    def test_register_as_responsible_member(self, client):
        """Member who is responsible for the obligation can register → 201."""
        token_owner, owner_id = _register(client, "payrt3o@pay-test.com", full_name="Owner")
        token_member, member_id = _register(client, "payrt3m@pay-test.com", full_name="Member")
        group_id = _create_group(client, token_owner, "Pay Responsible Group")
        _add_member(client, token_owner, group_id, "payrt3m@pay-test.com")

        _create_obligation(
            client, token_owner, group_id,
            name="Obl responsible",
            start_date="2026-06-01",
            responsible_user_id=member_id,
        )
        period = _get_future_period(client, token_owner, group_id)

        resp = _register_payment(client, token_member, group_id, period["id"])
        assert resp.status_code == 201

    def test_register_as_non_responsible_member_forbidden(self, client):
        """Member NOT responsible → 403 FORBIDDEN_NOT_RESPONSIBLE."""
        token_owner, owner_id = _register(client, "payrt4o@pay-test.com", full_name="Owner")
        token_member, member_id = _register(client, "payrt4m@pay-test.com", full_name="Member")
        group_id = _create_group(client, token_owner, "Pay Forbidden Group")
        _add_member(client, token_owner, group_id, "payrt4m@pay-test.com")

        # Obligation responsible is the OWNER, not the member
        _create_obligation(
            client, token_owner, group_id,
            name="Obl not responsible",
            start_date="2026-06-01",
            responsible_user_id=owner_id,
        )
        period = _get_future_period(client, token_owner, group_id)

        resp = _register_payment(client, token_member, group_id, period["id"])
        assert resp.status_code == 403
        assert resp.json()["code"] == "FORBIDDEN_NOT_RESPONSIBLE"

    def test_register_second_payment_on_paid_period(self, client):
        """Second payment on already-PAGADO period → 409 PERIOD_ALREADY_PAID."""
        token, _ = _register(client, "payrt5@pay-test.com", full_name="Owner")
        group_id = _create_group(client, token, "Pay Already Paid Group")
        _create_obligation(client, token, group_id, name="Obl dup", start_date="2026-06-01")
        period = _get_future_period(client, token, group_id)

        # First payment succeeds
        resp1 = _register_payment(client, token, group_id, period["id"])
        assert resp1.status_code == 201

        # Second payment on same period fails
        resp2 = _register_payment(client, token, group_id, period["id"])
        assert resp2.status_code == 409
        assert resp2.json()["code"] == "PERIOD_ALREADY_PAID"

    def test_register_currency_mismatch(self, client):
        """Payment currency differs from obligation currency → 400 CURRENCY_MISMATCH."""
        token, _ = _register(client, "payrt6@pay-test.com", full_name="Owner")
        group_id = _create_group(client, token, "Pay Currency Group")
        _create_obligation(
            client, token, group_id,
            name="Obl COP",
            start_date="2026-06-01",
            currency="COP",
        )
        period = _get_future_period(client, token, group_id)

        resp = _register_payment(client, token, group_id, period["id"], currency="USD")
        assert resp.status_code == 400
        assert resp.json()["code"] == "CURRENCY_MISMATCH"

    def test_register_on_other_group_period(self, client):
        """Payment on period from another group → 404 PERIOD_NOT_FOUND."""
        token_a, _ = _register(client, "payrt7a@pay-test.com", full_name="AdminA")
        token_b, _ = _register(client, "payrt7b@pay-test.com", full_name="AdminB")
        group_a = _create_group(client, token_a, "Pay Cross A")
        group_b = _create_group(client, token_b, "Pay Cross B")

        _create_obligation(client, token_a, group_a, name="Obl A", start_date="2026-06-01")
        resp_a = client.get(
            f"/api/v1/groups/{group_a}/periods?status=PENDIENTE",
            headers=_auth_header(token_a),
        )
        period_id = resp_a.json()[0]["id"]

        # Try to pay period from group_a using group_b's endpoint
        resp = _register_payment(client, token_b, group_b, period_id)
        assert resp.status_code == 404
        assert resp.json()["code"] == "PERIOD_NOT_FOUND"


# ---------------------------------------------------------------------------
# GET /groups/{group_id}/payments — list payment history
# ---------------------------------------------------------------------------

class TestListPayments:
    def test_list_empty_group(self, client):
        """No payments → empty list."""
        token, _ = _register(client, "paylst1@pay-test.com", full_name="Owner")
        group_id = _create_group(client, token, "Pay List Empty")

        resp = client.get(
            f"/api/v1/groups/{group_id}/payments",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_includes_created_payments(self, client):
        """Created payments appear in the list."""
        token, _ = _register(client, "paylst2@pay-test.com", full_name="Owner")
        group_id = _create_group(client, token, "Pay List Has")
        _create_obligation(client, token, group_id, name="Obl list", start_date="2026-06-01")
        period = _get_future_period(client, token, group_id)

        _register_payment(client, token, group_id, period["id"])

        resp = client.get(
            f"/api/v1/groups/{group_id}/payments",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        payments = resp.json()
        assert len(payments) == 1
        assert payments[0]["obligation_period_id"] == period["id"]

    def test_list_includes_voided_payments(self, client):
        """Voided payments still appear in the list (with voided_at visible)."""
        token, _ = _register(client, "paylst3@pay-test.com", full_name="Owner")
        group_id = _create_group(client, token, "Pay List Voided")
        _create_obligation(client, token, group_id, name="Obl voided list", start_date="2026-06-01")
        period = _get_future_period(client, token, group_id)

        resp_pay = _register_payment(client, token, group_id, period["id"])
        payment_id = resp_pay.json()["id"]

        # Void it
        client.post(
            f"/api/v1/groups/{group_id}/payments/{payment_id}/void",
            headers=_auth_header(token),
        )

        resp = client.get(
            f"/api/v1/groups/{group_id}/payments",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        payments = resp.json()
        assert len(payments) == 1
        assert payments[0]["voided_at"] is not None

    def test_list_requires_membership(self, client):
        """Non-member cannot list payments."""
        token_owner, _ = _register(client, "paylst4@pay-test.com", full_name="Owner")
        token_stranger, _ = _register(client, "paylst4s@pay-test.com", full_name="Stranger")
        group_id = _create_group(client, token_owner, "Pay List Auth")

        resp = client.get(
            f"/api/v1/groups/{group_id}/payments",
            headers=_auth_header(token_stranger),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /groups/{group_id}/payments/{id}/void — void payment
# ---------------------------------------------------------------------------

class TestVoidPayment:
    def test_void_sets_voided_at(self, client, pg_engine):
        """Voiding a payment sets voided_at and reverts period status."""
        token, _ = _register(client, "payv1@pay-test.com", full_name="Owner")
        group_id = _create_group(client, token, "Pay Void Group")
        _create_obligation(client, token, group_id, name="Obl void", start_date="2026-06-01")
        period = _get_future_period(client, token, group_id)

        resp_pay = _register_payment(client, token, group_id, period["id"])
        payment_id = resp_pay.json()["id"]

        resp = client.post(
            f"/api/v1/groups/{group_id}/payments/{payment_id}/void",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["voided_at"] is not None
        assert body["voided_by_user_id"] is not None

        # Verify period status reverted
        resp_period = client.get(
            f"/api/v1/groups/{group_id}/periods/{period['id']}",
            headers=_auth_header(token),
        )
        assert resp_period.status_code == 200
        period_status = resp_period.json()["status"]
        # Should be PENDIENTE or VENCIDO depending on due_date
        assert period_status in ("PENDIENTE", "VENCIDO")

    def test_void_overdue_period_reverts_to_vencido(self, client):
        """Voiding a payment on an overdue period → status becomes VENCIDO."""
        token, _ = _register(client, "payv2@pay-test.com", full_name="Owner")
        group_id = _create_group(client, token, "Pay Void Vencido")
        _create_obligation(client, token, group_id, name="Obl vencido", start_date="2026-06-01")
        period = _get_past_period(client, token, group_id)

        resp_pay = _register_payment(client, token, group_id, period["id"])
        payment_id = resp_pay.json()["id"]

        resp = client.post(
            f"/api/v1/groups/{group_id}/payments/{payment_id}/void",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200

        resp_period = client.get(
            f"/api/v1/groups/{group_id}/periods/{period['id']}",
            headers=_auth_header(token),
        )
        assert resp_period.json()["status"] == "VENCIDO"

    def test_void_future_period_reverts_to_pendiente(self, client):
        """Voiding a payment on a future period → status becomes PENDIENTE."""
        token, _ = _register(client, "payv3@pay-test.com", full_name="Owner")
        group_id = _create_group(client, token, "Pay Void Pendiente")
        _create_obligation(client, token, group_id, name="Obl pendiente", start_date="2026-06-01")
        period = _get_future_period(client, token, group_id)

        resp_pay = _register_payment(client, token, group_id, period["id"])
        payment_id = resp_pay.json()["id"]

        resp = client.post(
            f"/api/v1/groups/{group_id}/payments/{payment_id}/void",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200

        resp_period = client.get(
            f"/api/v1/groups/{group_id}/periods/{period['id']}",
            headers=_auth_header(token),
        )
        assert resp_period.json()["status"] == "PENDIENTE"

    def test_void_already_voided(self, client):
        """Voiding an already-voided payment → 409 PAYMENT_ALREADY_VOIDED."""
        token, _ = _register(client, "payv4@pay-test.com", full_name="Owner")
        group_id = _create_group(client, token, "Pay Void Double")
        _create_obligation(client, token, group_id, name="Obl double void", start_date="2026-06-01")
        period = _get_future_period(client, token, group_id)

        resp_pay = _register_payment(client, token, group_id, period["id"])
        payment_id = resp_pay.json()["id"]

        # First void succeeds
        resp1 = client.post(
            f"/api/v1/groups/{group_id}/payments/{payment_id}/void",
            headers=_auth_header(token),
        )
        assert resp1.status_code == 200

        # Second void fails
        resp2 = client.post(
            f"/api/v1/groups/{group_id}/payments/{payment_id}/void",
            headers=_auth_header(token),
        )
        assert resp2.status_code == 409
        assert resp2.json()["code"] == "PAYMENT_ALREADY_VOIDED"

    def test_void_other_group_payment(self, client):
        """Voiding a payment from another group → 404 PAYMENT_NOT_FOUND."""
        token_a, _ = _register(client, "payv5a@pay-test.com", full_name="AdminA")
        token_b, _ = _register(client, "payv5b@pay-test.com", full_name="AdminB")
        group_a = _create_group(client, token_a, "Pay Void Cross A")
        group_b = _create_group(client, token_b, "Pay Void Cross B")

        _create_obligation(client, token_a, group_a, name="Obl A", start_date="2026-06-01")
        period_a = _get_future_period(client, token_a, group_a)
        resp_pay = _register_payment(client, token_a, group_a, period_a["id"])
        payment_id = resp_pay.json()["id"]

        resp = client.post(
            f"/api/v1/groups/{group_b}/payments/{payment_id}/void",
            headers=_auth_header(token_b),
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == "PAYMENT_NOT_FOUND"

    def test_full_corrections_flow_pay_void_repay(self, client):
        """Complete correction flow: pay → void → pay again on the same period."""
        token, _ = _register(client, "payv6@pay-test.com", full_name="Owner")
        group_id = _create_group(client, token, "Pay Correction Flow")
        _create_obligation(client, token, group_id, name="Obl correction", start_date="2026-06-01")
        period = _get_future_period(client, token, group_id)

        # 1. Register first payment (wrong amount)
        resp1 = _register_payment(
            client, token, group_id, period["id"],
            amount_cents=5000000,
        )
        assert resp1.status_code == 201
        payment1_id = resp1.json()["id"]

        # Verify period is PAGADO
        resp_p1 = client.get(
            f"/api/v1/groups/{group_id}/periods/{period['id']}",
            headers=_auth_header(token),
        )
        assert resp_p1.json()["status"] == "PAGADO"

        # 2. Void the wrong payment
        resp_void = client.post(
            f"/api/v1/groups/{group_id}/payments/{payment1_id}/void",
            headers=_auth_header(token),
        )
        assert resp_void.status_code == 200
        assert resp_void.json()["voided_at"] is not None

        # Verify period reverted
        resp_p2 = client.get(
            f"/api/v1/groups/{group_id}/periods/{period['id']}",
            headers=_auth_header(token),
        )
        assert resp_p2.json()["status"] == "PENDIENTE"

        # 3. Register correct payment
        resp2 = _register_payment(
            client, token, group_id, period["id"],
            amount_cents=8000000,
        )
        assert resp2.status_code == 201
        payment2_id = resp2.json()["id"]
        assert payment2_id != payment1_id

        # Verify period is PAGADO again
        resp_p3 = client.get(
            f"/api/v1/groups/{group_id}/periods/{period['id']}",
            headers=_auth_header(token),
        )
        assert resp_p3.json()["status"] == "PAGADO"

        # 4. List payments: should show both (one voided, one active)
        resp_list = client.get(
            f"/api/v1/groups/{group_id}/payments",
            headers=_auth_header(token),
        )
        assert resp_list.status_code == 200
        payments = resp_list.json()
        assert len(payments) == 2
        voided = [p for p in payments if p["voided_at"] is not None]
        active = [p for p in payments if p["voided_at"] is None]
        assert len(voided) == 1
        assert len(active) == 1
        assert voided[0]["id"] == payment1_id
        assert active[0]["id"] == payment2_id
