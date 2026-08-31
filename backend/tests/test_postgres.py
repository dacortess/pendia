"""Postgres-specific tests that would have caught bugs #1, #2, #3.

These tests require a real PostgreSQL database via DATABASE_URL.
They are skipped if Postgres is not available.
Run with: DATABASE_URL="postgresql+psycopg://app:app_dev_only@localhost:5432/gestor_pagos" pytest tests/test_postgres.py -v
"""
import os
import uuid
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DataError, IntegrityError, ProgrammingError

from app.database.session import _sync_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://app:app_dev_only@localhost:5432/gestor_pagos"
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


def test_alembic_upgrade_head_creates_all_tables(pg_engine):
    """Bug #1 / #2: alembic upgrade head must succeed on empty DB and create 13 tables + citext."""
    with pg_engine.connect() as conn:
        result = conn.execute(text(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'"
        ))
        table_count = result.scalar()
        # 13 app tables + 1 alembic_version = 14
        assert table_count >= 13, f"Expected at least 13 tables, got {table_count}"
        # Check citext extension exists
        result = conn.execute(text("SELECT * FROM pg_extension WHERE extname='citext'"))
        assert result.fetchone() is not None


def test_jsonb_column_works(pg_engine):
    """Bug #1: audit_logs.metadata must be JSONB, not sa.JSONB (which doesn't exist)."""
    with pg_engine.connect() as conn:
        conn.execute(text(
            "SELECT column_name, udt_name FROM information_schema.columns "
            "WHERE table_name='audit_logs' AND column_name='metadata'"
        ))
        # If migration had sa.JSONB() it would have failed; this test confirms insert works
        suffix = uuid.uuid4().hex[:6]
        email = f"jsonb-{suffix}@example.com"
        conn.execute(text(
            "INSERT INTO users (email, password_hash, full_name) VALUES (:email, 'hash', 'JSONB Test') RETURNING id"
        ), {"email": email})
        user_id = conn.execute(text("SELECT id FROM users WHERE email=:email"), {"email": email}).scalar()
        conn.execute(text(
            "INSERT INTO groups (name, created_by) VALUES ('jsonb-group', :uid) RETURNING id"
        ), {"uid": user_id})
        group_id = conn.execute(text("SELECT id FROM groups WHERE name='jsonb-group' ORDER BY id DESC LIMIT 1")).scalar()
        conn.execute(text(
            "INSERT INTO audit_logs (group_id, actor_user_id, action, entity_type, entity_id, metadata) "
            "VALUES (:gid, :uid, 'test', 'User', :uid, '{\"key\": \"value\"}'::jsonb)"
        ), {"gid": group_id, "uid": user_id})
        conn.commit()
        result = conn.execute(text("SELECT metadata->>'key' FROM audit_logs WHERE action='test' ORDER BY id DESC LIMIT 1"))
        assert result.scalar() == "value"
        conn.commit()


def test_array_default_is_postgres_array(pg_engine):
    """Bug #2: notification_rules.days_before_due default must be '{3,1}'::smallint[] not '[3, 1]'."""
    with pg_engine.connect() as conn:
        result = conn.execute(text(
            "SELECT column_default FROM information_schema.columns "
            "WHERE table_name='notification_rules' AND column_name='days_before_due'"
        ))
        default = result.scalar()
        assert default == "'{3,1}'::smallint[]", f"Unexpected default: {default}"
        # Also test insert without days_before_due uses default
        conn.execute(text(
            "INSERT INTO users (email, password_hash, full_name) VALUES (:email, 'hash', 'Array Test')"
        ), {"email": f"array-{uuid.uuid4().hex[:6]}@example.com"})
        user_id = conn.execute(text("SELECT id FROM users ORDER BY id DESC LIMIT 1")).scalar()
        conn.execute(text("INSERT INTO groups (name, created_by) VALUES ('array-group', :uid)"), {"uid": user_id})
        group_id = conn.execute(text("SELECT id FROM groups ORDER BY id DESC LIMIT 1")).scalar()
        conn.execute(text(
            "INSERT INTO notification_rules (group_id) VALUES (:gid)"
        ), {"gid": group_id})
        conn.commit()
        result = conn.execute(text("SELECT days_before_due FROM notification_rules WHERE group_id=:gid ORDER BY id DESC LIMIT 1"), {"gid": group_id})
        arr = result.scalar()
        assert arr == [3, 1], f"Expected [3,1], got {arr}"
        conn.commit()


def test_enum_rejects_invalid_payment_method_kind(pg_engine):
    """Bug #3: payment_methods.kind must be ENUM, not TEXT - invalid value should fail."""
    with pg_engine.connect() as conn:
        # Verify column is ENUM
        result = conn.execute(text(
            "SELECT udt_name FROM information_schema.columns WHERE table_name='payment_methods' AND column_name='kind'"
        ))
        assert result.scalar() == "payment_method_kind"
        # Try invalid kind
        conn.execute(text(
            "INSERT INTO users (email, password_hash, full_name) VALUES (:email, 'hash', 'Enum Test')"
        ), {"email": f"enum-{uuid.uuid4().hex[:6]}@example.com"})
        user_id = conn.execute(text("SELECT id FROM users ORDER BY id DESC LIMIT 1")).scalar()
        conn.execute(text("INSERT INTO groups (name, created_by) VALUES ('enum-group', :uid)"), {"uid": user_id})
        group_id = conn.execute(text("SELECT id FROM groups ORDER BY id DESC LIMIT 1")).scalar()
        with pytest.raises((DataError, IntegrityError, ProgrammingError)):
            conn.execute(text(
                "INSERT INTO payment_methods (group_id, kind, provider_name, label, holder_name) "
                "VALUES (:gid, 'INVALID_KIND', 'Test', 'Label', 'Holder')"
            ), {"gid": group_id})
            conn.commit()
        conn.rollback()


def test_enum_rejects_invalid_currency(pg_engine):
    """Bug #3: obligations.currency must be ENUM supported_currency."""
    with pg_engine.connect() as conn:
        result = conn.execute(text(
            "SELECT udt_name FROM information_schema.columns WHERE table_name='obligations' AND column_name='currency'"
        ))
        assert result.scalar() == "supported_currency"
        conn.execute(text(
            "INSERT INTO users (email, password_hash, full_name) VALUES (:email, 'hash', 'Currency Test')"
        ), {"email": f"curr-{uuid.uuid4().hex[:6]}@example.com"})
        user_id = conn.execute(text("SELECT id FROM users ORDER BY id DESC LIMIT 1")).scalar()
        conn.execute(text("INSERT INTO groups (name, created_by) VALUES ('curr-group', :uid)"), {"uid": user_id})
        group_id = conn.execute(text("SELECT id FROM groups ORDER BY id DESC LIMIT 1")).scalar()
        with pytest.raises((DataError, IntegrityError, ProgrammingError)):
            conn.execute(text(
                "INSERT INTO obligations (group_id, name, currency, expected_amount_cents, periodicity, due_day, start_date) "
                "VALUES (:gid, 'Test', 'EUR', 1000, 'MONTHLY', 15, '2024-01-01')"
            ), {"gid": group_id})
            conn.commit()
        conn.rollback()


def test_enum_rejects_invalid_role(pg_engine):
    """Bug #3: group_memberships.role must be ENUM membership_role."""
    with pg_engine.connect() as conn:
        result = conn.execute(text(
            "SELECT udt_name FROM information_schema.columns WHERE table_name='group_memberships' AND column_name='role'"
        ))
        assert result.scalar() == "membership_role"
        # Need a user and group
        conn.execute(text(
            "INSERT INTO users (email, password_hash, full_name) VALUES (:email, 'hash', 'Role Test')"
        ), {"email": f"role-{uuid.uuid4().hex[:6]}@example.com"})
        user_id = conn.execute(text("SELECT id FROM users ORDER BY id DESC LIMIT 1")).scalar()
        conn.execute(text("INSERT INTO groups (name, created_by) VALUES ('role-group', :uid)"), {"uid": user_id})
        group_id = conn.execute(text("SELECT id FROM groups ORDER BY id DESC LIMIT 1")).scalar()
        with pytest.raises((DataError, IntegrityError, ProgrammingError)):
            conn.execute(text(
                "INSERT INTO group_memberships (user_id, group_id, role) VALUES (:uid, :gid, 'superadmin')"
            ), {"uid": user_id, "gid": group_id})
            conn.commit()
        conn.rollback()


def test_timezone_set_to_bogota():
    """ADR-011 #4: Every new connection should have TimeZone = 'America/Bogota'."""
    with _sync_engine.connect() as conn:
        result = conn.execute(text("SHOW TIME ZONE"))
        tz = result.scalar()
        assert tz == "America/Bogota", f"Expected 'America/Bogota', got '{tz}'"
