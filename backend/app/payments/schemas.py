"""Pydantic schemas for payment endpoints."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PaymentCreate(BaseModel):
    """Request body for POST /groups/{group_id}/periods/{id}/payments."""
    amount_cents: int = Field(ge=0)
    currency: Literal["COP", "USD"]
    paid_at: date
    notes: str | None = None
    receipt_url: str | None = None


class PaymentResponse(BaseModel):
    """Payment detail."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    obligation_period_id: int
    registered_by_user_id: int
    amount_cents: int
    currency: str
    paid_at: date
    notes: str | None
    receipt_url: str | None
    voided_at: datetime | None
    voided_by_user_id: int | None
    created_at: datetime
