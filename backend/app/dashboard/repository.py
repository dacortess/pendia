"""Database queries for dashboard aggregations."""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select, and_
from sqlalchemy.orm import Session

from app.obligations.models import Obligation, ObligationPeriod
from app.payments.models import Payment


def get_totals_by_currency(
    db: Session, group_id: int, month_date: date
) -> list[dict]:
    """Sum expected_amount_cents per currency for periods in the given month.

    Uses SQL aggregation (func.sum + GROUP BY) as required by ADR-004.
    """
    stmt = (
        select(
            Obligation.currency,
            func.sum(Obligation.expected_amount_cents).label("total_cents"),
        )
        .join(ObligationPeriod, ObligationPeriod.obligation_id == Obligation.id)
        .where(
            ObligationPeriod.period_month == month_date,
            Obligation.group_id == group_id,
            Obligation.is_active.is_(True),
        )
        .group_by(Obligation.currency)
    )
    rows = db.execute(stmt).all()
    return [{"currency": r.currency, "total_cents": r.total_cents} for r in rows]


def get_paid_by_currency(
    db: Session, group_id: int, month_date: date
) -> list[dict]:
    """Sum non-voided payment amounts per currency for periods in the given month.

    Uses SQL aggregation (func.sum + GROUP BY) as required by ADR-004.
    """
    stmt = (
        select(
            Obligation.currency,
            func.sum(Payment.amount_cents).label("paid_cents"),
        )
        .join(ObligationPeriod, Payment.obligation_period_id == ObligationPeriod.id)
        .join(Obligation, ObligationPeriod.obligation_id == Obligation.id)
        .where(
            ObligationPeriod.period_month == month_date,
            Obligation.group_id == group_id,
            Obligation.is_active.is_(True),
            Payment.voided_at.is_(None),
        )
        .group_by(Obligation.currency)
    )
    rows = db.execute(stmt).all()
    return [{"currency": r.currency, "paid_cents": r.paid_cents} for r in rows]


def get_upcoming_periods(
    db: Session, group_id: int, today: date, week_end: date
) -> list[dict]:
    """Return PENDIENTE periods due in [today, week_end] with obligation name.

    Independent of the ?month= parameter — always "next 7 days from today".
    """
    stmt = (
        select(
            ObligationPeriod.id.label("period_id"),
            Obligation.id.label("obligation_id"),
            Obligation.name.label("obligation_name"),
            ObligationPeriod.due_date,
            Obligation.expected_amount_cents,
            Obligation.currency,
        )
        .join(Obligation, ObligationPeriod.obligation_id == Obligation.id)
        .where(
            ObligationPeriod.status == "PENDIENTE",
            ObligationPeriod.due_date >= today,
            ObligationPeriod.due_date <= week_end,
            Obligation.group_id == group_id,
            Obligation.is_active.is_(True),
        )
        .order_by(ObligationPeriod.due_date.asc())
    )
    rows = db.execute(stmt).all()
    return [
        {
            "period_id": r.period_id,
            "obligation_id": r.obligation_id,
            "obligation_name": r.obligation_name,
            "due_date": r.due_date,
            "expected_amount_cents": r.expected_amount_cents,
            "currency": r.currency,
        }
        for r in rows
    ]
