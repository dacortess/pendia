"""Pydantic schemas for payment method endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PaymentMethodCreate(BaseModel):
    """Request body for POST /groups/{group_id}/payment-methods."""
    kind: Literal[
        "CASH", "BANK_ACCOUNT", "DIGITAL_WALLET", "DEBIT_CARD",
        "CREDIT_CARD", "BRE_B", "PSE", "OTHER",
    ]
    provider_name: str = Field(min_length=1, max_length=200)
    label: str = Field(min_length=1, max_length=200)
    last4: str | None = None
    masked_key: str | None = None
    holder_name: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_kind_references(self) -> PaymentMethodCreate:
        """Replicate the DB CHECK constraint chk_payment_method_reference."""
        kind = self.kind
        last4 = self.last4
        masked_key = self.masked_key

        if kind == "CASH":
            if last4 is not None or masked_key is not None:
                raise ValueError(
                    "CASH payment methods cannot have last4 or masked_key"
                )
        elif kind in ("BANK_ACCOUNT", "DEBIT_CARD", "CREDIT_CARD"):
            if last4 is None:
                raise ValueError(
                    f"{kind} requires last4 to be provided"
                )
            if len(last4) != 4 or not last4.isdigit():
                raise ValueError("last4 must be exactly 4 digits")
        elif kind in ("DIGITAL_WALLET", "BRE_B", "PSE"):
            if masked_key is None:
                raise ValueError(
                    f"{kind} requires masked_key to be provided"
                )
            if len(masked_key) > 20:
                raise ValueError("masked_key must be at most 20 characters")
        # OTHER: no restrictions

        return self


class PaymentMethodUpdate(BaseModel):
    """Request body for PATCH /groups/{group_id}/payment-methods/{id}."""
    label: str | None = Field(default=None, min_length=1, max_length=200)
    is_active: bool | None = None


class PaymentMethodResponse(BaseModel):
    """Payment method detail."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_id: int
    kind: str
    provider_name: str
    label: str
    last4: str | None
    masked_key: str | None
    holder_name: str
    is_active: bool
    created_at: datetime
