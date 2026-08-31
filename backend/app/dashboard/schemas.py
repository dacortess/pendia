"""Pydantic schemas for dashboard endpoint."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class CurrencyTotal(BaseModel):
    """Aggregated totals for a single currency."""
    currency: str
    total_cents: int
    paid_cents: int
    pending_cents: int


class UpcomingPeriod(BaseModel):
    """Period due within the next 7 days."""
    period_id: int
    obligation_id: int
    obligation_name: str
    due_date: date
    expected_amount_cents: int
    currency: str


class DashboardResponse(BaseModel):
    """Full dashboard response."""
    month: str
    totals: list[CurrencyTotal]
    vencen_esta_semana: list[UpcomingPeriod]
