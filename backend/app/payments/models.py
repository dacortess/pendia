"""Payment models (immutable - only INSERT allowed).

RNF-DATA-01 (ADR-011 #1): Ningún UPDATE ni DELETE sobre payments.
Corrección = anulación (voided_at) + nuevo registro.
This immutability is enforced at the service/repository layer — no repository
method performs UPDATE or DELETE on this table.
"""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Date,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, BigInt

supported_currency_enum = PG_ENUM(
    "COP", "USD",
    name="supported_currency",
    create_type=False,
)


class Payment(Base):
    """Payment record - IMMUTABLE (only INSERT, void via voided_at)."""
    __tablename__ = "payments"
    
    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    obligation_period_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("obligation_periods.id", ondelete="RESTRICT"),
        nullable=False,
    )
    registered_by_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
    )
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(supported_currency_enum, nullable=False)
    paid_at: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    receipt_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    voided_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    voided_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now,
    )
    
    __table_args__ = (
        CheckConstraint("amount_cents >= 0", name="chk_payment_amount_non_negative"),
        Index(
            "idx_payments_period",
            "obligation_period_id",
            postgresql_where="voided_at IS NULL",
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"<Payment(id={self.id}, period_id={self.obligation_period_id}, "
            f"amount_cents={self.amount_cents})>"
        )