"""Dashboard endpoint integration tests — requires real PostgreSQL."""
import os
from datetime import date, datetime, timedelta
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


def _current_month():
    today = _today()
    return today.strftime("%Y-%m")


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
def _clean_dashboard_tables(pg_engine):
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
            "(SELECT id FROM users WHERE email LIKE '%@dash-test%%')"
        ))
        conn.execute(text(
            "DELETE FROM refresh_tokens WHERE user_id IN "
            "(SELECT id FROM users WHERE email LIKE '%@dash-test%%')"
        ))
        conn.execute(text("DELETE FROM users WHERE email LIKE '%@dash-test%%'"))
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

def _register(client, email, password="Str0ngP@ss!", full_name="Test User"):
    resp = client.post("/api/v1/auth/register", json={
        "email": email, "password": password, "full_name": full_name,
    })
    assert resp.status_code == 201, f"Register failed: {resp.json()}"
    token = resp.json()["access_token"]
    me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    return token, me.json()["id"]


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def _create_group(client, token, name="Test Group"):
    resp = client.post("/api/v1/groups", json={"name": name}, headers=_auth_header(token))
    assert resp.status_code == 201
    return resp.json()["id"]


def _add_member(client, owner_token, group_id, member_email, role="member"):
    resp = client.post(
        f"/api/v1/groups/{group_id}/members",
        json={"email": member_email, "role": role},
        headers=_auth_header(owner_token),
    )
    assert resp.status_code == 201


def _create_obligation(client, token, group_id, **overrides):
    data = {
        "name": "Internet mensual",
        "expected_amount_cents": 80000,
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


def _register_payment(client, token, group_id, period_id, **overrides):
    data = {
        "amount_cents": 80000,
        "currency": "COP",
        "paid_at": _today().isoformat(),
    }
    data.update(overrides)
    resp = client.post(
        f"/api/v1/groups/{group_id}/periods/{period_id}/payments",
        json=data,
        headers=_auth_header(token),
    )
    assert resp.status_code == 201, f"Register payment failed: {resp.status_code} {resp.json()}"
    return resp.json()


def _void_payment(client, token, group_id, payment_id):
    resp = client.post(
        f"/api/v1/groups/{group_id}/payments/{payment_id}/void",
        headers=_auth_header(token),
    )
    assert resp.status_code == 200, f"Void payment failed: {resp.status_code} {resp.json()}"
    return resp.json()


# ---------------------------------------------------------------------------
# GET /groups/{group_id}/dashboard
# ---------------------------------------------------------------------------

class TestDashboardEmptyGroup:
    def test_empty_group_returns_200(self, client):
        token, _ = _register(client, "dashe1@dash-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Dash Empty Group")

        resp = client.get(
            f"/api/v1/groups/{group_id}/dashboard",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["month"] == _current_month()
        assert body["totals"] == []
        assert body["vencen_esta_semana"] == []


class TestDashboardTotals:
    def test_one_obligation_one_paid_one_pending(self, client):
        """One COP obligation: one paid period, one pending in current month."""
        token, _ = _register(client, "dasst1@dash-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Dash Totals Group")

        today = _today()
        # start_date in a past month so periods exist for current month
        start = date(today.year, max(1, today.month - 2), 1)
        obl = _create_obligation(
            client, token, group_id,
            name="Internet",
            expected_amount_cents=80000,
            due_day=15,
            start_date=start.isoformat(),
            currency="COP",
        )

        # Get periods for current month
        periods_resp = client.get(
            f"/api/v1/groups/{group_id}/periods?month={_current_month()}",
            headers=_auth_header(token),
        )
        assert periods_resp.status_code == 200
        periods = periods_resp.json()
        assert len(periods) >= 1, "Expected at least one period for current month"

        # Pay the first period
        paid_period = periods[0]
        payment = _register_payment(
            client, token, group_id, paid_period["id"],
            amount_cents=80000, currency="COP",
        )

        resp = client.get(
            f"/api/v1/groups/{group_id}/dashboard",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["month"] == _current_month()

        cop_totals = [t for t in body["totals"] if t["currency"] == "COP"]
        assert len(cop_totals) == 1
        t = cop_totals[0]
        # total_cents = sum of expected_amount_cents of all periods in the month
        # There should be exactly 1 period this month (monthly obligation)
        assert t["total_cents"] == 80000
        assert t["paid_cents"] == 80000
        assert t["pending_cents"] == 0

    def test_two_obligations_different_currencies(self, client):
        """Two obligations (COP + USD) → two entries in totals."""
        token, _ = _register(client, "dasst2@dash-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Dash Multi Currency")

        today = _today()
        start = date(today.year, max(1, today.month - 2), 1)
        _create_obligation(
            client, token, group_id,
            name="Internet COP",
            expected_amount_cents=100000,
            due_day=10,
            start_date=start.isoformat(),
            currency="COP",
        )
        _create_obligation(
            client, token, group_id,
            name="Netflix USD",
            expected_amount_cents=1500,
            due_day=5,
            start_date=start.isoformat(),
            currency="USD",
        )

        resp = client.get(
            f"/api/v1/groups/{group_id}/dashboard",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        body = resp.json()

        totals = body["totals"]
        assert len(totals) == 2

        cop = next(t for t in totals if t["currency"] == "COP")
        usd = next(t for t in totals if t["currency"] == "USD")
        assert cop["total_cents"] == 100000
        assert cop["paid_cents"] == 0
        assert cop["pending_cents"] == 100000
        assert usd["total_cents"] == 1500
        assert usd["paid_cents"] == 0
        assert usd["pending_cents"] == 1500

    def test_voided_payment_not_counted(self, client):
        """A voided payment should NOT count in paid_cents."""
        token, _ = _register(client, "dasst3@dash-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Dash Void Group")

        today = _today()
        start = date(today.year, max(1, today.month - 2), 1)
        _create_obligation(
            client, token, group_id,
            name="Servicio",
            expected_amount_cents=50000,
            due_day=10,
            start_date=start.isoformat(),
            currency="COP",
        )

        periods_resp = client.get(
            f"/api/v1/groups/{group_id}/periods?month={_current_month()}",
            headers=_auth_header(token),
        )
        periods = periods_resp.json()
        assert len(periods) >= 1
        period = periods[0]

        # Register and then void the payment
        payment = _register_payment(
            client, token, group_id, period["id"],
            amount_cents=50000, currency="COP",
        )
        _void_payment(client, token, group_id, payment["id"])

        resp = client.get(
            f"/api/v1/groups/{group_id}/dashboard",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        cop_totals = [t for t in body["totals"] if t["currency"] == "COP"]
        assert len(cop_totals) == 1
        t = cop_totals[0]
        assert t["total_cents"] == 50000
        assert t["paid_cents"] == 0
        assert t["pending_cents"] == 50000


class TestDashboardMonthFilter:
    def test_different_month_shows_correct_totals(self, client):
        """Querying a different month returns totals for that month, not the current one."""
        token, _ = _register(client, "dasmf1@dash-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Dash Month Filter")

        # Create obligation starting well in the past so periods exist for many months
        _create_obligation(
            client, token, group_id,
            name="Servicio",
            expected_amount_cents=20000,
            due_day=1,
            start_date="2026-01-01",
            currency="COP",
        )

        # Query a specific past month
        resp = client.get(
            f"/api/v1/groups/{group_id}/dashboard?month=2026-03",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["month"] == "2026-03"
        cop_totals = [t for t in body["totals"] if t["currency"] == "COP"]
        assert len(cop_totals) == 1
        assert cop_totals[0]["total_cents"] == 20000


class TestDashboardInvalidMonth:
    def test_invalid_month_format_rejected(self, client):
        token, _ = _register(client, "dashinv1@dash-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Dash Invalid Month")

        resp = client.get(
            f"/api/v1/groups/{group_id}/dashboard?month=agosto",
            headers=_auth_header(token),
        )
        assert resp.status_code == 422

    def test_invalid_month_13_rejected(self, client):
        token, _ = _register(client, "dashinv2@dash-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Dash Invalid Month 13")

        resp = client.get(
            f"/api/v1/groups/{group_id}/dashboard?month=2026-13",
            headers=_auth_header(token),
        )
        assert resp.status_code == 422


class TestDashboardUpcoming:
    def test_pending_due_in_3_days_appears(self, client):
        """A PENDIENTE period due in 3 days appears in vencen_esta_semana."""
        token, _ = _register(client, "dashup1@dash-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Dash Upcoming 3d")

        today = _today()
        due_in_3 = today + timedelta(days=3)

        _create_obligation(
            client, token, group_id,
            name="Internet",
            expected_amount_cents=80000,
            due_day=due_in_3.day,
            start_date=date(due_in_3.year, due_in_3.month, 1).isoformat(),
            currency="COP",
        )

        resp = client.get(
            f"/api/v1/groups/{group_id}/dashboard",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        upcoming = resp.json()["vencen_esta_semana"]
        names = [u["obligation_name"] for u in upcoming]
        assert "Internet" in names

    def test_pending_due_in_20_days_not_appears(self, client):
        """A PENDIENTE period due in 20 days does NOT appear."""
        token, _ = _register(client, "dashup2@dash-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Dash Upcoming 20d")

        today = _today()
        due_in_20 = today + timedelta(days=20)

        _create_obligation(
            client, token, group_id,
            name="Seguro Anual",
            expected_amount_cents=500000,
            due_day=due_in_20.day,
            start_date=date(due_in_20.year, due_in_20.month, 1).isoformat(),
            periodicity="MONTHLY",
        )

        resp = client.get(
            f"/api/v1/groups/{group_id}/dashboard",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        upcoming = resp.json()["vencen_esta_semana"]
        names = [u["obligation_name"] for u in upcoming]
        assert "Seguro Anual" not in names

    def test_overdue_period_not_in_upcoming(self, client):
        """An already VENCIDO (overdue) period does NOT appear in vencen_esta_semana."""
        token, _ = _register(client, "dashup3@dash-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Dash Overdue")

        today = _today()
        # Use end_date so only past/current periods exist (no future months to pollute upcoming)
        _create_obligation(
            client, token, group_id,
            name="Servicio Vencido",
            expected_amount_cents=30000,
            due_day=1,
            start_date="2026-01-01",
            end_date=date(today.year, today.month, 1).isoformat(),
            periodicity="MONTHLY",
        )

        # Verify the period for this month exists and is VENCIDO
        periods_resp = client.get(
            f"/api/v1/groups/{group_id}/periods?month={_current_month()}",
            headers=_auth_header(token),
        )
        periods = periods_resp.json()
        vencidos = [p for p in periods if p["status"] == "VENCIDO"]
        assert len(vencidos) >= 1, (
            f"Expected at least one VENCIDO period, got statuses: "
            f"{[p['status'] for p in periods]}"
        )

        resp = client.get(
            f"/api/v1/groups/{group_id}/dashboard",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        upcoming = resp.json()["vencen_esta_semana"]
        names = [u["obligation_name"] for u in upcoming]
        assert "Servicio Vencido" not in names


class TestDashboardDeactivatedObligation:
    def test_deactivated_obligation_not_counted(self, client):
        """Deactivated obligation (is_active=False) contributes nothing."""
        token, _ = _register(client, "dashde1@dash-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Dash Deactivated")

        today = _today()
        start = date(today.year, max(1, today.month - 2), 1)
        obl = _create_obligation(
            client, token, group_id,
            name="Servicio Desactivado",
            expected_amount_cents=100000,
            due_day=10,
            start_date=start.isoformat(),
        )

        # Deactivate the obligation
        resp = client.delete(
            f"/api/v1/groups/{group_id}/obligations/{obl['id']}",
            headers=_auth_header(token),
        )
        assert resp.status_code == 204

        resp = client.get(
            f"/api/v1/groups/{group_id}/dashboard",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        # No totals because the only obligation is deactivated
        assert body["totals"] == []
        assert body["vencen_esta_semana"] == []


class TestDashboardAccessControl:
    def test_non_member_gets_403(self, client):
        token_owner, _ = _register(client, "dashac1@dash-test.com", full_name="Owner")
        token_stranger, _ = _register(client, "dashac1s@dash-test.com", full_name="Stranger")
        group_id = _create_group(client, token_owner, "Dash Private Group")

        resp = client.get(
            f"/api/v1/groups/{group_id}/dashboard",
            headers=_auth_header(token_stranger),
        )
        assert resp.status_code == 403

    def test_member_can_view_dashboard(self, client):
        token_owner, _ = _register(client, "dashac2@dash-test.com", full_name="Owner")
        token_member, _ = _register(client, "dashac2m@dash-test.com", full_name="Member")
        group_id = _create_group(client, token_owner, "Dash Member View")
        _add_member(client, token_owner, group_id, "dashac2m@dash-test.com")

        resp = client.get(
            f"/api/v1/groups/{group_id}/dashboard",
            headers=_auth_header(token_member),
        )
        assert resp.status_code == 200


class TestDashboardUpcomingIndependenceFromMonth:
    def test_upcoming_not_affected_by_month_param(self, client):
        """vencen_esta_semana is always next 7 days, independent of ?month=."""
        token, _ = _register(client, "dashui1@dash-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Dash Upcoming Independent")

        today = _today()
        due_in_5 = today + timedelta(days=5)

        _create_obligation(
            client, token, group_id,
            name="Internet",
            expected_amount_cents=80000,
            due_day=due_in_5.day,
            start_date=date(due_in_5.year, due_in_5.month, 1).isoformat(),
            currency="COP",
        )

        # Query with a different month - upcoming should still show the period
        resp = client.get(
            f"/api/v1/groups/{group_id}/dashboard?month=2026-01",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        upcoming = resp.json()["vencen_esta_semana"]
        names = [u["obligation_name"] for u in upcoming]
        assert "Internet" in names
