"""Audit log integration tests — requires real PostgreSQL."""
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
def _clean_audit_tables(pg_engine):
    _do_cleanup(pg_engine)
    yield
    _do_cleanup(pg_engine)


def _do_cleanup(pg_engine):
    with pg_engine.connect() as conn:
        conn.execute(text("DELETE FROM audit_logs"))
        conn.execute(text("DELETE FROM payments"))
        conn.execute(text("DELETE FROM obligation_periods"))
        conn.execute(text("DELETE FROM obligations"))
        conn.execute(text("DELETE FROM payment_methods"))
        conn.execute(text("DELETE FROM categories WHERE group_id IS NOT NULL"))
        conn.execute(text("DELETE FROM group_memberships"))
        conn.execute(text("DELETE FROM group_invite_codes"))
        conn.execute(text(
            "DELETE FROM groups WHERE created_by IN "
            "(SELECT id FROM users WHERE email LIKE '%@audit-test%%')"
        ))
        conn.execute(text(
            "DELETE FROM refresh_tokens WHERE user_id IN "
            "(SELECT id FROM users WHERE email LIKE '%@audit-test%%')"
        ))
        conn.execute(text("DELETE FROM users WHERE email LIKE '%@audit-test%%'"))
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


def _get_user_id_by_email(pg_engine, email: str) -> int:
    with pg_engine.connect() as conn:
        row = conn.execute(
            text("SELECT id FROM users WHERE email = :e"),
            {"e": email},
        ).fetchone()
        return row[0]


def _query_audit_log(pg_engine, *, entity_type: str, entity_id: int, action: str) -> dict | None:
    """Query audit_logs for a specific entry. Returns the row as a dict or None."""
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
# Tests: group.created
# ---------------------------------------------------------------------------

class TestAuditGroupCreated:
    def test_audit_group_created(self, client, pg_engine):
        token, user_id = _register(client, "audit-grp-create@audit-test.com", full_name="Audit Creator")
        resp = client.post("/api/v1/groups", json={"name": "Audit Group"}, headers=_auth_header(token))
        assert resp.status_code == 201
        group_id = resp.json()["id"]

        log = _query_audit_log(pg_engine, entity_type="Group", entity_id=group_id, action="group.created")
        assert log is not None
        assert log["actor_user_id"] == user_id
        assert log["group_id"] == group_id
        assert log["metadata"]["name"] == "Audit Group"


# ---------------------------------------------------------------------------
# Tests: membership.added
# ---------------------------------------------------------------------------

class TestAuditMembershipAdded:
    def test_audit_membership_added(self, client, pg_engine):
        token_owner, owner_id = _register(client, "audit-add@audit-test.com", full_name="Owner")
        _register(client, "audit-add-mbr@audit-test.com", full_name="Member")
        resp = client.post("/api/v1/groups", json={"name": "Add Audit Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        resp2 = client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "audit-add-mbr@audit-test.com", "role": "member"},
            headers=_auth_header(token_owner),
        )
        assert resp2.status_code == 201
        target_user_id = resp2.json()["user_id"]

        log = _query_audit_log(pg_engine, entity_type="GroupMembership", entity_id=target_user_id, action="membership.added")
        assert log is not None
        assert log["actor_user_id"] == owner_id
        assert log["group_id"] == group_id
        assert log["metadata"]["role"] == "member"


# ---------------------------------------------------------------------------
# Tests: membership.role_changed
# ---------------------------------------------------------------------------

class TestAuditMembershipRoleChanged:
    def test_audit_membership_role_changed(self, client, pg_engine):
        token_owner, owner_id = _register(client, "audit-role@audit-test.com", full_name="Owner")
        _register(client, "audit-role-mbr@audit-test.com", full_name="Member")
        resp = client.post("/api/v1/groups", json={"name": "Role Audit Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        add_resp = client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "audit-role-mbr@audit-test.com", "role": "member"},
            headers=_auth_header(token_owner),
        )
        target_user_id = add_resp.json()["user_id"]

        resp2 = client.patch(
            f"/api/v1/groups/{group_id}/members/{target_user_id}",
            json={"role": "admin"},
            headers=_auth_header(token_owner),
        )
        assert resp2.status_code == 200

        log = _query_audit_log(pg_engine, entity_type="GroupMembership", entity_id=target_user_id, action="membership.role_changed")
        assert log is not None
        assert log["actor_user_id"] == owner_id
        assert log["group_id"] == group_id
        assert log["metadata"]["new_role"] == "admin"


# ---------------------------------------------------------------------------
# Tests: membership.removed
# ---------------------------------------------------------------------------

class TestAuditMembershipRemoved:
    def test_audit_membership_removed(self, client, pg_engine):
        token_owner, owner_id = _register(client, "audit-rm@audit-test.com", full_name="Owner")
        _register(client, "audit-rm-mbr@audit-test.com", full_name="Member")
        resp = client.post("/api/v1/groups", json={"name": "Remove Audit Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        add_resp = client.post(
            f"/api/v1/groups/{group_id}/members",
            json={"email": "audit-rm-mbr@audit-test.com", "role": "member"},
            headers=_auth_header(token_owner),
        )
        target_user_id = add_resp.json()["user_id"]

        resp2 = client.delete(
            f"/api/v1/groups/{group_id}/members/{target_user_id}",
            headers=_auth_header(token_owner),
        )
        assert resp2.status_code == 204

        log = _query_audit_log(pg_engine, entity_type="GroupMembership", entity_id=target_user_id, action="membership.removed")
        assert log is not None
        assert log["actor_user_id"] == owner_id
        assert log["group_id"] == group_id


# ---------------------------------------------------------------------------
# Tests: membership.joined_via_code
# ---------------------------------------------------------------------------

class TestAuditMembershipJoinedViaCode:
    def test_audit_membership_joined_via_code(self, client, pg_engine):
        token_owner, owner_id = _register(client, "audit-join-own@audit-test.com", full_name="Owner")
        resp = client.post("/api/v1/groups", json={"name": "Join Audit Group"}, headers=_auth_header(token_owner))
        group_id = resp.json()["id"]

        code_resp = client.post(
            f"/api/v1/groups/{group_id}/invite-codes",
            json={"role_to_assign": "member"},
            headers=_auth_header(token_owner),
        )
        assert code_resp.status_code == 201
        invite_code = code_resp.json()["code"]

        token_member, member_id = _register(client, "audit-join-mbr@audit-test.com", full_name="Member")
        join_resp = client.post(
            "/api/v1/groups/join",
            json={"code": invite_code},
            headers=_auth_header(token_member),
        )
        assert join_resp.status_code == 201

        log = _query_audit_log(pg_engine, entity_type="GroupMembership", entity_id=member_id, action="membership.joined_via_code")
        assert log is not None
        assert log["actor_user_id"] == member_id
        assert log["group_id"] == group_id


# ---------------------------------------------------------------------------
# Tests: obligation.created
# ---------------------------------------------------------------------------

class TestAuditObligationCreated:
    def test_audit_obligation_created(self, client, pg_engine):
        token, user_id = _register(client, "audit-obl-create@audit-test.com", full_name="Admin")
        resp = client.post("/api/v1/groups", json={"name": "Obl Audit Group"}, headers=_auth_header(token))
        group_id = resp.json()["id"]

        resp2 = client.post(
            f"/api/v1/groups/{group_id}/obligations",
            json={
                "name": "Internet",
                "expected_amount_cents": 8000000,
                "due_day": 15,
                "periodicity": "MONTHLY",
                "start_date": "2026-01-01",
            },
            headers=_auth_header(token),
        )
        assert resp2.status_code == 201
        obl_id = resp2.json()["id"]

        log = _query_audit_log(pg_engine, entity_type="Obligation", entity_id=obl_id, action="obligation.created")
        assert log is not None
        assert log["actor_user_id"] == user_id
        assert log["group_id"] == group_id
        assert log["metadata"]["name"] == "Internet"


# ---------------------------------------------------------------------------
# Tests: obligation.updated
# ---------------------------------------------------------------------------

class TestAuditObligationUpdated:
    def test_audit_obligation_updated(self, client, pg_engine):
        token, user_id = _register(client, "audit-obl-upd@audit-test.com", full_name="Admin")
        resp = client.post("/api/v1/groups", json={"name": "Obl Upd Audit Group"}, headers=_auth_header(token))
        group_id = resp.json()["id"]

        create_resp = client.post(
            f"/api/v1/groups/{group_id}/obligations",
            json={
                "name": "Arriendo",
                "expected_amount_cents": 500000000,
                "due_day": 1,
                "periodicity": "MONTHLY",
                "start_date": "2026-01-01",
            },
            headers=_auth_header(token),
        )
        obl_id = create_resp.json()["id"]

        resp2 = client.patch(
            f"/api/v1/groups/{group_id}/obligations/{obl_id}",
            json={"name": "Arriendo Actualizado"},
            headers=_auth_header(token),
        )
        assert resp2.status_code == 200

        log = _query_audit_log(pg_engine, entity_type="Obligation", entity_id=obl_id, action="obligation.updated")
        assert log is not None
        assert log["actor_user_id"] == user_id
        assert log["group_id"] == group_id
        assert "name" in log["metadata"]["fields"]


# ---------------------------------------------------------------------------
# Tests: obligation.deactivated
# ---------------------------------------------------------------------------

class TestAuditObligationDeactivated:
    def test_audit_obligation_deactivated(self, client, pg_engine):
        token, user_id = _register(client, "audit-obl-deact@audit-test.com", full_name="Admin")
        resp = client.post("/api/v1/groups", json={"name": "Obl Deact Audit Group"}, headers=_auth_header(token))
        group_id = resp.json()["id"]

        create_resp = client.post(
            f"/api/v1/groups/{group_id}/obligations",
            json={
                "name": "Netflix",
                "expected_amount_cents": 5000000,
                "due_day": 10,
                "periodicity": "MONTHLY",
                "start_date": "2026-01-01",
            },
            headers=_auth_header(token),
        )
        obl_id = create_resp.json()["id"]

        resp2 = client.delete(
            f"/api/v1/groups/{group_id}/obligations/{obl_id}",
            headers=_auth_header(token),
        )
        assert resp2.status_code == 204

        log = _query_audit_log(pg_engine, entity_type="Obligation", entity_id=obl_id, action="obligation.deactivated")
        assert log is not None
        assert log["actor_user_id"] == user_id
        assert log["group_id"] == group_id


# ---------------------------------------------------------------------------
# Tests: payment.registered
# ---------------------------------------------------------------------------

class TestAuditPaymentRegistered:
    def test_audit_payment_registered(self, client, pg_engine):
        token, user_id = _register(client, "audit-pay-reg@audit-test.com", full_name="Admin")
        resp = client.post("/api/v1/groups", json={"name": "Pay Audit Group"}, headers=_auth_header(token))
        group_id = resp.json()["id"]

        client.post(
            f"/api/v1/groups/{group_id}/obligations",
            json={
                "name": "Servicio",
                "expected_amount_cents": 10000000,
                "due_day": 15,
                "periodicity": "MONTHLY",
                "start_date": "2026-01-01",
            },
            headers=_auth_header(token),
        )
        periods_resp = client.get(
            f"/api/v1/groups/{group_id}/periods?status=PENDIENTE",
            headers=_auth_header(token),
        )
        period_id = periods_resp.json()[0]["id"]

        pay_resp = client.post(
            f"/api/v1/groups/{group_id}/periods/{period_id}/payments",
            json={
                "amount_cents": 10000000,
                "currency": "COP",
                "paid_at": _today().isoformat(),
            },
            headers=_auth_header(token),
        )
        assert pay_resp.status_code == 201
        payment_id = pay_resp.json()["id"]

        log = _query_audit_log(pg_engine, entity_type="Payment", entity_id=payment_id, action="payment.registered")
        assert log is not None
        assert log["actor_user_id"] == user_id
        assert log["group_id"] == group_id
        assert log["metadata"]["amount_cents"] == 10000000
        assert log["metadata"]["currency"] == "COP"


# ---------------------------------------------------------------------------
# Tests: payment.voided
# ---------------------------------------------------------------------------

class TestAuditPaymentVoided:
    def test_audit_payment_voided(self, client, pg_engine):
        token, user_id = _register(client, "audit-pay-void@audit-test.com", full_name="Admin")
        resp = client.post("/api/v1/groups", json={"name": "Pay Void Audit Group"}, headers=_auth_header(token))
        group_id = resp.json()["id"]

        client.post(
            f"/api/v1/groups/{group_id}/obligations",
            json={
                "name": "Seguro",
                "expected_amount_cents": 20000000,
                "due_day": 5,
                "periodicity": "MONTHLY",
                "start_date": "2026-01-01",
            },
            headers=_auth_header(token),
        )
        periods_resp = client.get(
            f"/api/v1/groups/{group_id}/periods?status=PENDIENTE",
            headers=_auth_header(token),
        )
        period_id = periods_resp.json()[0]["id"]

        pay_resp = client.post(
            f"/api/v1/groups/{group_id}/periods/{period_id}/payments",
            json={
                "amount_cents": 20000000,
                "currency": "COP",
                "paid_at": _today().isoformat(),
            },
            headers=_auth_header(token),
        )
        payment_id = pay_resp.json()["id"]

        void_resp = client.post(
            f"/api/v1/groups/{group_id}/payments/{payment_id}/void",
            headers=_auth_header(token),
        )
        assert void_resp.status_code == 200

        log = _query_audit_log(pg_engine, entity_type="Payment", entity_id=payment_id, action="payment.voided")
        assert log is not None
        assert log["actor_user_id"] == user_id
        assert log["group_id"] == group_id
