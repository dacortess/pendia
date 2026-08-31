"""Initial schema migration - 13 tables from schema.sql

Revision ID: 001_initial
Revises: 
Create Date: 2026-08-28

NOTE: The autogenerate couldn't run because Postgres wasn't available.
This migration is written manually based on docs/db/schema.sql.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import (
    ARRAY as PG_ARRAY,
    ENUM as PG_ENUM,
    JSONB,
    SMALLINT as PG_SMALLINT,
)


# revision identifiers
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable citext extension
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    
    # Create ENUMs first (so the column definitions can reference them with create_type=False)
    op.execute("CREATE TYPE membership_role AS ENUM ('owner', 'admin', 'member')")
    op.execute("CREATE TYPE periodicity AS ENUM ('MONTHLY', 'BIMONTHLY', 'QUARTERLY', 'SEMIANNUAL', 'ANNUAL')")
    op.execute("CREATE TYPE period_status AS ENUM ('PENDIENTE', 'PAGADO', 'VENCIDO')")
    op.execute("""
        CREATE TYPE payment_method_kind AS ENUM (
            'CASH', 'BANK_ACCOUNT', 'DIGITAL_WALLET', 'DEBIT_CARD', 
            'CREDIT_CARD', 'BRE_B', 'PSE', 'OTHER'
        )
    """)
    op.execute("CREATE TYPE notification_event_type AS ENUM ('DUE_SOON', 'DUE_TODAY', 'OVERDUE')")
    op.execute("CREATE TYPE notification_status AS ENUM ('PENDING', 'SENT', 'FAILED', 'SKIPPED')")
    op.execute("CREATE TYPE notification_channel AS ENUM ('WHATSAPP', 'EMAIL')")
    op.execute("CREATE TYPE supported_currency AS ENUM ('COP', 'USD')")
    
    # Pre-create ENUM instances with create_type=False so Alembic doesn't try to recreate them
    membership_role_enum = PG_ENUM(
        "owner", "admin", "member",
        name="membership_role",
        create_type=False,
    )
    periodicity_enum = PG_ENUM(
        "MONTHLY", "BIMONTHLY", "QUARTERLY", "SEMIANNUAL", "ANNUAL",
        name="periodicity",
        create_type=False,
    )
    period_status_enum = PG_ENUM(
        "PENDIENTE", "PAGADO", "VENCIDO",
        name="period_status",
        create_type=False,
    )
    payment_method_kind_enum = PG_ENUM(
        "CASH", "BANK_ACCOUNT", "DIGITAL_WALLET", "DEBIT_CARD",
        "CREDIT_CARD", "BRE_B", "PSE", "OTHER",
        name="payment_method_kind",
        create_type=False,
    )
    notification_event_type_enum = PG_ENUM(
        "DUE_SOON", "DUE_TODAY", "OVERDUE",
        name="notification_event_type",
        create_type=False,
    )
    notification_status_enum = PG_ENUM(
        "PENDING", "SENT", "FAILED", "SKIPPED",
        name="notification_status",
        create_type=False,
    )
    notification_channel_enum = PG_ENUM(
        "WHATSAPP", "EMAIL",
        name="notification_channel",
        create_type=False,
    )
    supported_currency_enum = PG_ENUM(
        "COP", "USD",
        name="supported_currency",
        create_type=False,
    )
    
    # users table
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("phone_number", sa.Text(), nullable=True),
        sa.Column("whatsapp_opt_in", sa.Boolean(), nullable=False, server_default="FALSE"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="TRUE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "phone_number IS NULL OR phone_number ~ '^\+[0-9]{8,15}$'",
            name="chk_users_phone_number"
        ),
    )
    # Add CITEXT type workaround - use text with expression
    op.execute("ALTER TABLE users ALTER COLUMN email TYPE citext")
    
    # refresh_tokens table
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_refresh_tokens_user",
        "refresh_tokens",
        ["user_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    
    # groups table
    op.create_table(
        "groups",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    
    # group_invite_codes table
    op.create_table(
        "group_invite_codes",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("group_id", sa.BigInteger(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("role_to_assign", membership_role_enum, nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("max_uses", sa.SmallInteger(), nullable=True),
        sa.Column("uses_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="TRUE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("role_to_assign <> 'owner'", name="chk_invite_code_not_owner"),
        sa.CheckConstraint("max_uses IS NULL OR uses_count <= max_uses", name="chk_uses_within_max"),
    )
    op.create_index(
        "idx_group_invite_codes_lookup",
        "group_invite_codes",
        ["code"],
        postgresql_where=sa.text("is_active"),
    )
    
    # group_memberships table (composite PK)
    op.create_table(
        "group_memberships",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("group_id", sa.BigInteger(), sa.ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", membership_role_enum, nullable=False),
        sa.Column("joined_via_invite_code_id", sa.BigInteger(), sa.ForeignKey("group_invite_codes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "uq_one_owner_per_group",
        "group_memberships",
        ["group_id"],
        unique=True,
        postgresql_where=sa.text("role = 'owner'"),
    )
    
    # categories table
    op.create_table(
        "categories",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("group_id", sa.BigInteger(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("icon", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "uq_category_name_per_group",
        "categories",
        ["group_id", "name"],
        unique=True,
        postgresql_where=sa.text("group_id IS NOT NULL"),
    )
    op.create_index(
        "uq_system_category_name",
        "categories",
        ["name"],
        unique=True,
        postgresql_where=sa.text("group_id IS NULL"),
    )
    
    # payment_methods table
    op.create_table(
        "payment_methods",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("group_id", sa.BigInteger(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", payment_method_kind_enum, nullable=False),
        sa.Column("provider_name", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("last4", sa.CHAR(4), nullable=True),
        sa.Column("masked_key", sa.Text(), nullable=True),
        sa.Column("holder_name", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="TRUE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "(kind = 'CASH' AND last4 IS NULL AND masked_key IS NULL) "
            "OR (kind IN ('BANK_ACCOUNT', 'DEBIT_CARD', 'CREDIT_CARD') AND last4 IS NOT NULL) "
            "OR (kind IN ('DIGITAL_WALLET', 'BRE_B', 'PSE') AND masked_key IS NOT NULL) "
            "OR (kind = 'OTHER')",
            name="chk_payment_method_reference",
        ),
        sa.CheckConstraint("masked_key IS NULL OR length(masked_key) <= 20", name="chk_masked_key_length"),
    )
    op.create_index(
        "idx_payment_methods_group",
        "payment_methods",
        ["group_id"],
        postgresql_where=sa.text("is_active"),
    )
    
    # obligations table
    op.create_table(
        "obligations",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("group_id", sa.BigInteger(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", sa.BigInteger(), sa.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("payment_method_id", sa.BigInteger(), sa.ForeignKey("payment_methods.id", ondelete="SET NULL"), nullable=True),
        sa.Column("responsible_user_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("provider_name", sa.Text(), nullable=True),
        sa.Column("external_reference", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("currency", supported_currency_enum, nullable=False, server_default="COP"),
        sa.Column("expected_amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("is_variable_amount", sa.Boolean(), nullable=False, server_default="FALSE"),
        sa.Column("is_subscription", sa.Boolean(), nullable=False, server_default="FALSE"),
        sa.Column("auto_debit", sa.Boolean(), nullable=False, server_default="FALSE"),
        sa.Column("is_essential", sa.Boolean(), nullable=False, server_default="TRUE"),
        sa.Column("periodicity", periodicity_enum, nullable=False, server_default="MONTHLY"),
        sa.Column("due_day", sa.SmallInteger(), nullable=False),
        sa.Column("due_month", sa.SmallInteger(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="TRUE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("expected_amount_cents >= 0", name="chk_amount_non_negative"),
        sa.CheckConstraint("due_day BETWEEN 1 AND 31", name="chk_due_day_range"),
        sa.CheckConstraint("due_month BETWEEN 1 AND 12", name="chk_due_month_range"),
        sa.CheckConstraint(
            "(periodicity = 'ANNUAL' AND due_month IS NOT NULL) "
            "OR (periodicity <> 'ANNUAL' AND due_month IS NULL)",
            name="chk_due_month_only_if_annual",
        ),
        sa.CheckConstraint("end_date IS NULL OR end_date >= start_date", name="chk_end_date_after_start"),
    )
    # Add composite FK
    op.execute("""
        ALTER TABLE obligations
        ADD CONSTRAINT fk_obligations_responsible_membership
        FOREIGN KEY (responsible_user_id, group_id)
        REFERENCES group_memberships(user_id, group_id)
        DEFERRABLE INITIALLY IMMEDIATE
    """)
    op.create_index(
        "idx_obligations_group",
        "obligations",
        ["group_id"],
        postgresql_where=sa.text("is_active"),
    )
    
    # obligation_periods table
    op.create_table(
        "obligation_periods",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("obligation_id", sa.BigInteger(), sa.ForeignKey("obligations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_month", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", period_status_enum, nullable=False, server_default="PENDIENTE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("obligation_id", "period_month", name="uq_obligation_period_month"),
    )
    op.create_index(
        "idx_obligation_periods_status",
        "obligation_periods",
        ["status", "due_date"],
    )
    
    # payments table (IMMUTABLE - no UPDATE/DELETE allowed)
    op.create_table(
        "payments",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("obligation_period_id", sa.BigInteger(), sa.ForeignKey("obligation_periods.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("registered_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("currency", supported_currency_enum, nullable=False),
        sa.Column("paid_at", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("receipt_url", sa.Text(), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount_cents >= 0", name="chk_payment_amount_non_negative"),
    )
    op.create_index(
        "idx_payments_period",
        "payments",
        ["obligation_period_id"],
        postgresql_where=sa.text("voided_at IS NULL"),
    )
    
    # audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("group_id", sa.BigInteger(), sa.ForeignKey("groups.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column("metadata", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_audit_logs_group_time",
        "audit_logs",
        ["group_id", "created_at"],
        postgresql_where=sa.text("group_id IS NOT NULL"),
    )
    
    # notification_rules table
    op.create_table(
        "notification_rules",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("group_id", sa.BigInteger(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("obligation_id", sa.BigInteger(), sa.ForeignKey("obligations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("days_before_due", PG_ARRAY(sa.SmallInteger()), nullable=False, server_default=sa.text("'{3,1}'::smallint[]")),
        sa.Column("notify_on_due_day", sa.Boolean(), nullable=False, server_default="TRUE"),
        sa.Column("notify_on_overdue", sa.Boolean(), nullable=False, server_default="TRUE"),
        sa.Column("overdue_repeat_every_days", sa.SmallInteger(), nullable=True),
        sa.Column("channel", notification_channel_enum, nullable=False, server_default="WHATSAPP"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="TRUE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_notification_rules_group",
        "notification_rules",
        ["group_id"],
        postgresql_where=sa.text("is_active"),
    )
    
    # notification_events table
    op.create_table(
        "notification_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("obligation_period_id", sa.BigInteger(), sa.ForeignKey("obligation_periods.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_id", sa.BigInteger(), sa.ForeignKey("notification_rules.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", notification_event_type_enum, nullable=False),
        sa.Column("channel", notification_channel_enum, nullable=False, server_default="WHATSAPP"),
        sa.Column("scheduled_for", sa.Date(), nullable=False),
        sa.Column("status", notification_status_enum, nullable=False, server_default="PENDING"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("obligation_period_id", "event_type", "scheduled_for", name="uq_notification_event"),
    )
    op.create_index(
        "idx_notification_events_pending",
        "notification_events",
        ["status", "scheduled_for"],
        postgresql_where=sa.text("status = 'PENDING'"),
    )


def downgrade() -> None:
    op.drop_table("notification_events")
    op.drop_table("notification_rules")
    op.drop_table("audit_logs")
    op.drop_table("payments")
    op.drop_table("obligation_periods")
    op.drop_table("obligations")
    op.drop_table("payment_methods")
    op.drop_table("categories")
    op.drop_table("group_memberships")
    op.drop_table("group_invite_codes")
    op.drop_table("groups")
    op.drop_table("refresh_tokens")
    op.drop_table("users")
    
    op.execute("DROP TYPE IF EXISTS notification_channel")
    op.execute("DROP TYPE IF EXISTS notification_status")
    op.execute("DROP TYPE IF EXISTS notification_event_type")
    op.execute("DROP TYPE IF EXISTS supported_currency")
    op.execute("DROP TYPE IF EXISTS payment_method_kind")
    op.execute("DROP TYPE IF EXISTS period_status")
    op.execute("DROP TYPE IF EXISTS periodicity")
    op.execute("DROP TYPE IF EXISTS membership_role")
    op.execute("DROP EXTENSION IF EXISTS citext")
