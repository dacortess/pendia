"""Payment method models."""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, BigInt

payment_method_kind_enum = PG_ENUM(
    "CASH", "BANK_ACCOUNT", "DIGITAL_WALLET", "DEBIT_CARD",
    "CREDIT_CARD", "BRE_B", "PSE", "OTHER",
    name="payment_method_kind",
    create_type=False,
)


class PaymentMethod(Base):
    """Payment method associated with a group."""
    __tablename__ = "payment_methods"
    
    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    group_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(payment_method_kind_enum, nullable=False)
    provider_name: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    last4: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    masked_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    holder_name: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now,
    )
    
    __table_args__ = (
        CheckConstraint(
            "(kind = 'CASH' AND last4 IS NULL AND masked_key IS NULL) "
            "OR (kind IN ('BANK_ACCOUNT', 'DEBIT_CARD', 'CREDIT_CARD') AND last4 IS NOT NULL) "
            "OR (kind IN ('DIGITAL_WALLET', 'BRE_B', 'PSE') AND masked_key IS NOT NULL) "
            "OR (kind = 'OTHER')",
            name="chk_payment_method_reference",
        ),
        CheckConstraint(
            "masked_key IS NULL OR length(masked_key) <= 20",
            name="chk_masked_key_length",
        ),
        Index(
            "idx_payment_methods_group",
            "group_id",
            postgresql_where="is_active",
        ),
    )
    
    def __repr__(self) -> str:
        return f"<PaymentMethod(id={self.id}, kind={self.kind}, group_id={self.group_id})>"