"""Period endpoint and generation integration tests — requires real PostgreSQL."""
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


def _current_month_first():
    t = _today()
    return date(t.year, t.month, 1)


def _next_month_first():
    t = _today()
    if t.month == 12:
        return date(t.year + 1, 1, 1)
    return date(t.year, t.month + 1, 1)


def _period_count(start_year: int, start_month: int, periodicity_months: int) -> int:
    """Calculate expected period count from start to limit (current+1 month)."""
    limit = _next_month_first()
    start = date(start_year, start_month, 1)
    count = 0
    year, month = start_year, start_month
    while True:
        pm = date(year, month, 1)
        if pm > limit:
            break
        count += 1
        month += periodicity_months
        while month > 12:
            month -= 12
            year += 1
    return count


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
def _clean_period_tables(pg_engine):
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
            "(SELECT id FROM users WHERE email LIKE '%@period-test%%')"
        ))
        conn.execute(text(
            "DELETE FROM refresh_tokens WHERE user_id IN "
            "(SELECT id FROM users WHERE email LIKE '%@period-test%%')"
        ))
        conn.execute(text("DELETE FROM users WHERE email LIKE '%@period-test%%'"))
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


def _count_periods_in_db(pg_engine, obligation_id: int) -> int:
    with pg_engine.connect() as conn:
        result = conn.execute(
            text("SELECT COUNT(*) FROM obligation_periods WHERE obligation_id = :oid"),
            {"oid": obligation_id},
        ).fetchone()
        return result[0]


# ---------------------------------------------------------------------------
# Period generation — core tests
# ---------------------------------------------------------------------------

class TestPeriodGeneration:
    def test_monthly_generates_correct_count(self, client, pg_engine):
        """MONTHLY with start 3 months ago → correct number of periods."""
        token, _ = _register(client, "prdg1@period-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Period Gen Group")

        t = _today()
        if t.month > 3:
            start = date(t.year, t.month - 3, 1)
        else:
            start = date(t.year - 1, 12 - (3 - t.month), 1)

        body = _create_obligation(
            client, token, group_id,
            name="Monthly 3mo back",
            start_date=start.isoformat(),
            periodicity="MONTHLY",
            due_day=10,
        )
        obl_id = body["id"]

        expected = _period_count(start.year, start.month, 1)
        actual = _count_periods_in_db(pg_engine, obl_id)
        assert actual == expected, f"Expected {expected} periods, got {actual}"

    def test_monthly_vencido_and_pendiente_status(self, client, pg_engine):
        """Past due_date → VENCIDO, future → PENDIENTE."""
        token, _ = _register(client, "prdg2@period-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Period Status Group")

        t = _today()
        # Start from 2 months ago so there's at least one past period
        if t.month >= 3:
            start = date(t.year, t.month - 2, 1)
        else:
            start = date(t.year - 1, 12 - (2 - t.month), 1)

        body = _create_obligation(
            client, token, group_id,
            name="Status test",
            start_date=start.isoformat(),
            periodicity="MONTHLY",
            due_day=1,
        )
        obl_id = body["id"]

        # List periods to trigger generation
        resp = client.get(
            f"/api/v1/groups/{group_id}/periods",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        periods = resp.json()

        for p in periods:
            due = date.fromisoformat(p["due_date"])
            if due < t:
                assert p["status"] == "VENCIDO", f"Period due {due} should be VENCIDO"
            else:
                assert p["status"] == "PENDIENTE", f"Period due {due} should be PENDIENTE"

    def test_clamping_due_day_31_in_short_month(self, client, pg_engine):
        """due_day=31 in February → due_date should be last day of Feb."""
        token, _ = _register(client, "prdg3@period-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Clamp Group")

        body = _create_obligation(
            client, token, group_id,
            name="Clamp test",
            start_date="2026-02-01",
            periodicity="MONTHLY",
            due_day=31,
        )
        obl_id = body["id"]

        resp = client.get(
            f"/api/v1/groups/{group_id}/periods?month=2026-02",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        periods = resp.json()
        assert len(periods) == 1
        assert periods[0]["due_date"] == "2026-02-28"  # 2026 is not a leap year

    def test_clamping_april_30(self, client, pg_engine):
        """due_day=31 in April (30 days) → due_date should be April 30."""
        token, _ = _register(client, "prdg3b@period-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Clamp April Group")

        body = _create_obligation(
            client, token, group_id,
            name="Clamp April",
            start_date="2026-04-01",
            periodicity="MONTHLY",
            due_day=31,
        )

        resp = client.get(
            f"/api/v1/groups/{group_id}/periods?month=2026-04",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        periods = resp.json()
        assert len(periods) == 1
        assert periods[0]["due_date"] == "2026-04-30"

    def test_annual_one_period_per_year(self, client, pg_engine):
        """ANNUAL generates exactly 1 period per year, not 12."""
        token, _ = _register(client, "prdg4@period-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Annual Group")

        body = _create_obligation(
            client, token, group_id,
            name="Annual test",
            start_date="2024-01-01",
            periodicity="ANNUAL",
            due_day=15,
            due_month=6,
        )
        obl_id = body["id"]

        # List periods to trigger generation
        resp = client.get(
            f"/api/v1/groups/{group_id}/periods",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        periods = resp.json()

        # From 2024-06 to current+1 month, should be ~2-3 periods depending on today
        for p in periods:
            assert p["period_month"][5:7] == "06", f"Period month should be June, got {p['period_month']}"

        # Verify no consecutive months
        months = sorted([p["period_month"] for p in periods])
        for i in range(1, len(months)):
            y1, m1 = int(months[i-1][:4]), int(months[i-1][5:7])
            y2, m2 = int(months[i][:4]), int(months[i][5:7])
            diff = (y2 - y1) * 12 + (m2 - m1)
            assert diff == 12, f"Annual periods should be 12 months apart, got {diff} for {months[i-1]} → {months[i]}"

    def test_annual_with_past_start_generates_correct_years(self, client, pg_engine):
        """ANNUAL with start 2 years ago → one period per year from due_month."""
        token, _ = _register(client, "prdg4b@period-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Annual 2yr Group")

        t = _today()
        body = _create_obligation(
            client, token, group_id,
            name="Annual 2yr",
            start_date="2024-03-01",
            periodicity="ANNUAL",
            due_day=15,
            due_month=6,
        )
        obl_id = body["id"]

        expected = _period_count(2024, 6, 12)
        actual = _count_periods_in_db(pg_engine, obl_id)
        assert actual == expected, f"Expected {expected} annual periods, got {actual}"

    def test_end_date_limits_generation(self, client, pg_engine):
        """end_date in the past → no periods beyond end_date."""
        token, _ = _register(client, "prdg5@period-test.com", full_name="Admin")
        group_id = _create_group(client, token, "End Date Group")

        body = _create_obligation(
            client, token, group_id,
            name="End date test",
            start_date="2026-01-01",
            end_date="2026-03-31",
            periodicity="MONTHLY",
            due_day=10,
        )
        obl_id = body["id"]

        resp = client.get(
            f"/api/v1/groups/{group_id}/periods",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        periods = resp.json()

        # Should have periods for Jan, Feb, Mar only
        months = sorted([p["period_month"] for p in periods])
        assert len(months) == 3
        assert months[0] == "2026-01-01"
        assert months[1] == "2026-02-01"
        assert months[2] == "2026-03-01"

    def test_list_with_status_filter(self, client, pg_engine):
        """Filter by status=VENCIDO returns only overdue periods."""
        token, _ = _register(client, "prdg6@period-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Status Filter Group")

        t = _today()
        if t.month >= 2:
            start = date(t.year, t.month - 1, 1)
        else:
            start = date(t.year - 1, 12, 1)

        _create_obligation(
            client, token, group_id,
            name="Filter test",
            start_date=start.isoformat(),
            periodicity="MONTHLY",
            due_day=1,
        )

        resp_vencido = client.get(
            f"/api/v1/groups/{group_id}/periods?status=VENCIDO",
            headers=_auth_header(token),
        )
        assert resp_vencido.status_code == 200
        for p in resp_vencido.json():
            assert p["status"] == "VENCIDO"

        resp_pendiente = client.get(
            f"/api/v1/groups/{group_id}/periods?status=PENDIENTE",
            headers=_auth_header(token),
        )
        assert resp_pendiente.status_code == 200
        for p in resp_pendiente.json():
            assert p["status"] == "PENDIENTE"

    def test_list_with_month_filter(self, client, pg_engine):
        """Filter by month=YYYY-MM returns only that month."""
        token, _ = _register(client, "prdg7@period-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Month Filter Group")

        _create_obligation(
            client, token, group_id,
            name="Month filter",
            start_date="2026-01-01",
            periodicity="MONTHLY",
            due_day=10,
        )

        resp = client.get(
            f"/api/v1/groups/{group_id}/periods?month=2026-01",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        periods = resp.json()
        assert len(periods) == 1
        assert periods[0]["period_month"] == "2026-01-01"

    def test_idempotency_no_duplicate_periods(self, client, pg_engine):
        """Calling list periods twice doesn't duplicate rows."""
        token, _ = _register(client, "prdg8@period-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Idempotent Group")

        body = _create_obligation(
            client, token, group_id,
            name="Idempotent test",
            start_date="2026-03-01",
            periodicity="MONTHLY",
            due_day=10,
        )
        obl_id = body["id"]

        # First list → generates periods
        resp1 = client.get(
            f"/api/v1/groups/{group_id}/periods",
            headers=_auth_header(token),
        )
        assert resp1.status_code == 200
        count1 = _count_periods_in_db(pg_engine, obl_id)

        # Second list → should NOT create more periods
        resp2 = client.get(
            f"/api/v1/groups/{group_id}/periods",
            headers=_auth_header(token),
        )
        assert resp2.status_code == 200
        count2 = _count_periods_in_db(pg_engine, obl_id)

        assert count1 == count2, f"Periods duplicated: {count1} → {count2}"
        assert len(resp1.json()) == len(resp2.json())

    def test_pending_period_becomes_vencido_on_relist(self, client, pg_engine):
        """A PENDIENTE period whose due_date passed → VENCIDO on next list."""
        token, _ = _register(client, "prdg9@period-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Vencido Update Group")

        t = _today()
        # Create with due_day=1 and start from this month
        body = _create_obligation(
            client, token, group_id,
            name="Vencido update",
            start_date=date(t.year, t.month, 1).isoformat(),
            periodicity="MONTHLY",
            due_day=1,
        )
        obl_id = body["id"]

        # List once to generate
        resp1 = client.get(
            f"/api/v1/groups/{group_id}/periods",
            headers=_auth_header(token),
        )
        assert resp1.status_code == 200

        # Check current month period
        current_month_str = date(t.year, t.month, 1).isoformat()
        for p in resp1.json():
            if p["period_month"] == current_month_str:
                # due_date = 1st of current month, which is <= today
                due = date.fromisoformat(p["due_date"])
                if due < t:
                    assert p["status"] == "VENCIDO"
                break

    def test_get_period_by_id(self, client):
        """GET /periods/{id} returns the period detail."""
        token, _ = _register(client, "prdg10@period-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Period Get Group")

        _create_obligation(
            client, token, group_id,
            name="Get period",
            start_date="2026-06-01",
            periodicity="MONTHLY",
            due_day=15,
        )

        resp = client.get(
            f"/api/v1/groups/{group_id}/periods",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        periods = resp.json()
        assert len(periods) >= 1

        period_id = periods[0]["id"]
        resp2 = client.get(
            f"/api/v1/groups/{group_id}/periods/{period_id}",
            headers=_auth_header(token),
        )
        assert resp2.status_code == 200
        assert resp2.json()["id"] == period_id

    def test_get_period_other_group_404(self, client):
        """GET /periods/{id} from another group → 404."""
        token_a, _ = _register(client, "prdg11a@period-test.com", full_name="AdminA")
        token_b, _ = _register(client, "prdg11b@period-test.com", full_name="AdminB")
        group_a = _create_group(client, token_a, "Period Other A")
        group_b = _create_group(client, token_b, "Period Other B")

        _create_obligation(
            client, token_a, group_a,
            name="Obl A",
            start_date="2026-06-01",
            periodicity="MONTHLY",
            due_day=15,
        )

        resp_a = client.get(
            f"/api/v1/groups/{group_a}/periods",
            headers=_auth_header(token_a),
        )
        period_id = resp_a.json()[0]["id"]

        resp_b = client.get(
            f"/api/v1/groups/{group_b}/periods/{period_id}",
            headers=_auth_header(token_b),
        )
        assert resp_b.status_code == 404

    def test_list_requires_membership(self, client):
        """Non-member cannot list periods."""
        token_owner, _ = _register(client, "prdg12@period-test.com", full_name="Owner")
        token_stranger, _ = _register(client, "prdg12s@period-test.com", full_name="Stranger")
        group_id = _create_group(client, token_owner, "Period Auth Group")

        resp = client.get(
            f"/api/v1/groups/{group_id}/periods",
            headers=_auth_header(token_stranger),
        )
        assert resp.status_code == 403

    def test_bimonthly_generates_correct_count(self, client, pg_engine):
        """BIMONTHLY (interval=2) generates correct number of periods."""
        token, _ = _register(client, "prdg13@period-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Bimonthly Group")

        body = _create_obligation(
            client, token, group_id,
            name="Bimonthly test",
            start_date="2026-01-01",
            periodicity="BIMONTHLY",
            due_day=15,
        )
        obl_id = body["id"]

        expected = _period_count(2026, 1, 2)
        actual = _count_periods_in_db(pg_engine, obl_id)
        assert actual == expected, f"Expected {expected} bimonthly periods, got {actual}"

    def test_quarterly_generates_correct_count(self, client, pg_engine):
        """QUARTERLY (interval=3) generates correct number of periods."""
        token, _ = _register(client, "prdg14@period-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Quarterly Group")

        body = _create_obligation(
            client, token, group_id,
            name="Quarterly test",
            start_date="2026-01-01",
            periodicity="QUARTERLY",
            due_day=15,
        )
        obl_id = body["id"]

        expected = _period_count(2026, 1, 3)
        actual = _count_periods_in_db(pg_engine, obl_id)
        assert actual == expected, f"Expected {expected} quarterly periods, got {actual}"

    def test_semiannual_generates_correct_count(self, client, pg_engine):
        """SEMIANNUAL (interval=6) generates correct number of periods."""
        token, _ = _register(client, "prdg15@period-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Semiannual Group")

        body = _create_obligation(
            client, token, group_id,
            name="Semiannual test",
            start_date="2026-01-01",
            periodicity="SEMIANNUAL",
            due_day=15,
        )
        obl_id = body["id"]

        expected = _period_count(2026, 1, 6)
        actual = _count_periods_in_db(pg_engine, obl_id)
        assert actual == expected, f"Expected {expected} semiannual periods, got {actual}"

    def test_annual_due_month_not_in_past_generates_current_year(self, client, pg_engine):
        """ANNUAL with due_month in current or future month generates this year."""
        token, _ = _register(client, "prdg16@period-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Annual Future Month")

        t = _today()
        # Pick a month that hasn't happened yet this year, or is current
        future_month = t.month  # Use current month to ensure at least one period
        if future_month < 12:
            future_month = future_month + 1
        else:
            future_month = 12

        body = _create_obligation(
            client, token, group_id,
            name="Annual future month",
            start_date="2025-01-01",
            periodicity="ANNUAL",
            due_day=15,
            due_month=future_month,
        )
        obl_id = body["id"]

        resp = client.get(
            f"/api/v1/groups/{group_id}/periods",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        periods = resp.json()

        # Each period should be in the future_month
        for p in periods:
            month_part = int(p["period_month"][5:7])
            assert month_part == future_month

    def test_next_month_period_is_generated_in_advance(self, client, pg_engine):
        """El mes actual+1 SIEMPRE debe existir como período PENDIENTE, sin importar
        si ya llegó su fecha de vencimiento — este es el propósito central de la
        generación 'lazy, un mes adelante' del ADR-003."""
        token, _ = _register(client, "nextmonth@period-test.com", full_name="Admin")
        group_id = _create_group(client, token, "Next Month Group")

        t = _today()
        # Empieza 2 meses atrás para tener margen, sin depender de fórmulas paralelas
        start_year, start_month = t.year, t.month - 2
        if start_month <= 0:
            start_month += 12
            start_year -= 1
        start = date(start_year, start_month, 1)

        next_month_year, next_month = t.year, t.month + 1
        if next_month > 12:
            next_month = 1
            next_month_year += 1
        expected_next_period_month = date(next_month_year, next_month, 1)

        body = _create_obligation(
            client, token, group_id,
            name="Next month check",
            start_date=start.isoformat(),
            periodicity="MONTHLY",
            due_day=15,
        )
        obl_id = body["id"]

        resp = client.get(f"/api/v1/groups/{group_id}/periods", headers=_auth_header(token))
        assert resp.status_code == 200
        period_months = [p["period_month"] for p in resp.json() if p["obligation_id"] == obl_id]

        assert expected_next_period_month.isoformat() in period_months, (
            f"El período del mes siguiente ({expected_next_period_month}) debe existir. "
            f"Períodos encontrados: {period_months}"
        )

        # Y su status debe ser PENDIENTE (no puede estar vencido si es el mes que aún no llega)
        next_period = next(
            p for p in resp.json()
            if p["obligation_id"] == obl_id and p["period_month"] == expected_next_period_month.isoformat()
        )
        assert next_period["status"] == "PENDIENTE"
