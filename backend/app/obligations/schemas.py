"""Pydantic schemas for obligation and period endpoints."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ObligationCreate(BaseModel):
    """Request body for POST /groups/{group_id}/obligations."""
    name: str = Field(min_length=1, max_length=200)
    provider_name: str | None = None
    external_reference: str | None = None
    notes: str | None = None
    currency: Literal["COP", "USD"] = "COP"
    expected_amount_cents: int = Field(ge=0, default=0)
    is_variable_amount: bool = False
    is_subscription: bool = False
    auto_debit: bool = False
    is_essential: bool = True
    periodicity: Literal["MONTHLY", "BIMONTHLY", "QUARTERLY", "SEMIANNUAL", "ANNUAL"] = "MONTHLY"
    due_day: int = Field(ge=1, le=31)
    due_month: int | None = None
    start_date: date
    end_date: date | None = None
    category_id: int | None = None
    payment_method_id: int | None = None
    responsible_user_id: int | None = None

    @model_validator(mode="after")
    def validate_annual_due_month(self) -> ObligationCreate:
        if self.periodicity == "ANNUAL" and self.due_month is None:
            raise ValueError("due_month is required when periodicity is ANNUAL")
        if self.periodicity != "ANNUAL" and self.due_month is not None:
            raise ValueError("due_month must be null when periodicity is not ANNUAL")
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date must be >= start_date")
        return self


class ObligationUpdate(BaseModel):
    """Request body for PATCH /groups/{group_id}/obligations/{id}."""
    name: str | None = Field(default=None, min_length=1, max_length=200)
    provider_name: str | None = None
    external_reference: str | None = None
    notes: str | None = None
    currency: Literal["COP", "USD"] | None = None
    expected_amount_cents: int | None = Field(default=None, ge=0)
    is_variable_amount: bool | None = None
    is_subscription: bool | None = None
    auto_debit: bool | None = None
    is_essential: bool | None = None
    periodicity: Literal["MONTHLY", "BIMONTHLY", "QUARTERLY", "SEMIANNUAL", "ANNUAL"] | None = None
    due_day: int | None = Field(default=None, ge=1, le=31)
    due_month: int | None = None
    start_date: date | None = None
    end_date: date | None = "unset"
    category_id: int | None = "unset"
    payment_method_id: int | None = "unset"
    responsible_user_id: int | None = "unset"

    @model_validator(mode="after")
    def validate_update_fields(self) -> ObligationUpdate:
        p = self.periodicity
        dm = self.due_month
        sd = self.start_date
        ed = self.end_date

        if p == "ANNUAL" and dm is None and not self.model_fields_set.intersection({"due_month"}):
            pass  # periodicity changed to ANNUAL but due_month not provided — this is an error only if periodicity is explicitly set
        if p is not None and p == "ANNUAL" and "due_month" in self.model_fields_set and dm is None:
            raise ValueError("due_month is required when periodicity is ANNUAL")
        if p is not None and p != "ANNUAL" and "due_month" in self.model_fields_set and dm is not None:
            raise ValueError("due_month must be null when periodicity is not ANNUAL")

        if ed is not None and ed != "unset" and sd is not None and ed < sd:
            raise ValueError("end_date must be >= start_date")

        return self

    def effective_periodicity(self, current: str) -> str:
        return self.periodicity if self.periodicity is not None else current

    def effective_due_month(self, current_due_month: int | None) -> int | None:
        if "due_month" in self.model_fields_set:
            return self.due_month
        return current_due_month


class ObligationResponse(BaseModel):
    """Obligation detail."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_id: int
    category_id: int | None
    payment_method_id: int | None
    responsible_user_id: int | None
    name: str
    provider_name: str | None
    external_reference: str | None
    notes: str | None
    currency: str
    expected_amount_cents: int
    is_variable_amount: bool
    is_subscription: bool
    auto_debit: bool
    is_essential: bool
    periodicity: str
    due_day: int
    due_month: int | None
    start_date: date
    end_date: date | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ObligationPeriodResponse(BaseModel):
    """Obligation period detail."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    obligation_id: int
    period_month: date
    due_date: date
    status: str
    created_at: datetime
