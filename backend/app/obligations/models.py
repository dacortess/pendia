"""Obligation models."""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Date,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, BigInt

periodicity_enum = PG_ENUM(
    "MONTHLY", "BIMONTHLY", "QUARTERLY", "SEMIANNUAL", "ANNUAL",
    name="periodicity",
    create_type=False,
)

supported_currency_enum = PG_ENUM(
    "COP", "USD",
    name="supported_currency",
    create_type=False,
)


class Obligation(Base):
    """Financial obligation (bill) for a group."""
    __tablename__ = "obligations"
    
    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    group_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    payment_method_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("payment_methods.id", ondelete="SET NULL"),
        nullable=True,
    )
    responsible_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )
    
    name: Mapped[str] = mapped_column(Text, nullable=False)
    provider_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    external_reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    currency: Mapped[str] = mapped_column(supported_currency_enum, nullable=False, default="COP")
    expected_amount_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    is_variable_amount: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    is_subscription: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_debit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_essential: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    periodicity: Mapped[str] = mapped_column(periodicity_enum, nullable=False, default="MONTHLY")
    due_day: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    due_month: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
    )
    
    # Relationships for FK constraints
    responsible: Mapped[Optional["GroupMembership"]] = relationship(
        "GroupMembership",
        primaryjoin="and_(Obligation.responsible_user_id==GroupMembership.user_id, "
                    "Obligation.group_id==GroupMembership.group_id)",
        foreign_keys=[responsible_user_id, group_id],
        viewonly=True,
    )
    
    __table_args__ = (
        CheckConstraint("expected_amount_cents >= 0", name="chk_amount_non_negative"),
        CheckConstraint("due_day BETWEEN 1 AND 31", name="chk_due_day_range"),
        CheckConstraint("due_month BETWEEN 1 AND 12", name="chk_due_month_range"),
        CheckConstraint(
            "(periodicity = 'ANNUAL' AND due_month IS NOT NULL) "
            "OR (periodicity <> 'ANNUAL' AND due_month IS NULL)",
            name="chk_due_month_only_if_annual",
        ),
        CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="chk_end_date_after_start",
        ),
        Index(
            "idx_obligations_group",
            "group_id",
            postgresql_where="is_active",
        ),
    )


period_status_enum = PG_ENUM(
    "PENDIENTE", "PAGADO", "VENCIDO",
    name="period_status",
    create_type=False,
)


class ObligationPeriod(Base):
    """Periodic instance of an obligation."""
    __tablename__ = "obligation_periods"
    
    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    obligation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("obligations.id", ondelete="CASCADE"),
        nullable=False,
    )
    period_month: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(period_status_enum, nullable=False, default="PENDIENTE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now,
    )

    obligation: Mapped[Optional["Obligation"]] = relationship(
        "Obligation",
        primaryjoin="ObligationPeriod.obligation_id == Obligation.id",
        viewonly=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "obligation_id",
            "period_month",
            name="uq_obligation_period_month",
        ),
        Index(
            "idx_obligation_periods_status",
            "status",
            "due_date",
        ),
    )