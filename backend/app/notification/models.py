"""Notification models (rule and event).

Terreno preparado para alertas (ADR-012). No se activa ningún envío en el MVP.
"""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Date,
    ForeignKey,
    Index,
    JSON,
    SmallInteger,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, ENUM as PG_ENUM
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, BigInt


class SmallIntArray(TypeDecorator):
    """Array of SmallInteger for cross-database compatibility."""
    impl = Text
    cache_ok = True
    
    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(ARRAY(SmallInteger))
        return dialect.type_descriptor(JSON())
    
    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return [int(x) for x in value]
    
    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return list(value)
        return list(value)


notification_channel_enum = PG_ENUM(
    "WHATSAPP", "EMAIL",
    name="notification_channel",
    create_type=False,
)


class NotificationRule(Base):
    """Rule for sending notifications about an obligation."""
    __tablename__ = "notification_rules"
    
    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    group_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    obligation_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("obligations.id", ondelete="CASCADE"),
        nullable=True,
    )
    days_before_due: Mapped[list] = mapped_column(
        SmallIntArray,
        nullable=False,
        default=lambda: [3, 1],
    )
    notify_on_due_day: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_on_overdue: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    overdue_repeat_every_days: Mapped[Optional[int]] = mapped_column(
        SmallInteger,
        nullable=True,
    )
    channel: Mapped[str] = mapped_column(
        notification_channel_enum,
        nullable=False,
        default="WHATSAPP",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now,
    )
    
    __table_args__ = (
        Index(
            "idx_notification_rules_group",
            "group_id",
            postgresql_where="is_active",
        ),
    )
    
    def __repr__(self) -> str:
        return f"<NotificationRule(id={self.id}, group_id={self.group_id})>"


class NotificationEvent(Base):
    """Record of a notification event that was triggered."""
    __tablename__ = "notification_events"
    
    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    obligation_period_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("obligation_periods.id", ondelete="CASCADE"),
        nullable=False,
    )
    rule_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("notification_rules.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(
        PG_ENUM("DUE_SOON", "DUE_TODAY", "OVERDUE", name="notification_event_type", create_type=False),
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(
        notification_channel_enum,
        nullable=False,
        default="WHATSAPP",
    )
    scheduled_for: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        PG_ENUM("PENDING", "SENT", "FAILED", "SKIPPED", name="notification_status", create_type=False),
        nullable=False,
        default="PENDING",
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now,
    )
    
    __table_args__ = (
        UniqueConstraint(
            "obligation_period_id",
            "event_type",
            "scheduled_for",
            name="uq_notification_event",
        ),
        Index(
            "idx_notification_events_pending",
            "status",
            "scheduled_for",
            postgresql_where="status = 'PENDING'",
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"<NotificationEvent(id={self.id}, period_id={self.obligation_period_id}, "
            f"status={self.status})>"
        )