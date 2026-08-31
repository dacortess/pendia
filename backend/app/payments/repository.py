"""Database queries for payments."""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.obligations.models import Obligation, ObligationPeriod
from app.payments.models import Payment


def create_payment(
    db: Session,
    *,
    obligation_period_id: int,
    registered_by_user_id: int,
    amount_cents: int,
    currency: str,
    paid_at: date,
    notes: str | None,
    receipt_url: str | None,
) -> Payment:
    """Insert a new payment. Caller must commit."""
    payment = Payment(
        obligation_period_id=obligation_period_id,
        registered_by_user_id=registered_by_user_id,
        amount_cents=amount_cents,
        currency=currency,
        paid_at=paid_at,
        notes=notes,
        receipt_url=receipt_url,
    )
    db.add(payment)
    db.flush()
    return payment


def get_payment_by_id(
    db: Session, id: int, group_id: int
) -> Payment | None:
    """Return a payment by id, filtered by group_id via ObligationPeriod -> Obligation."""
    return db.execute(
        select(Payment)
        .join(ObligationPeriod, Payment.obligation_period_id == ObligationPeriod.id)
        .join(Obligation, ObligationPeriod.obligation_id == Obligation.id)
        .where(
            Payment.id == id,
            Obligation.group_id == group_id,
        )
    ).scalar_one_or_none()


def list_payments_for_group(db: Session, group_id: int) -> list[Payment]:
    """Return all payments for a group (including voided), ordered by paid_at DESC."""
    return list(
        db.execute(
            select(Payment)
            .join(ObligationPeriod, Payment.obligation_period_id == ObligationPeriod.id)
            .join(Obligation, ObligationPeriod.obligation_id == Obligation.id)
            .where(Obligation.group_id == group_id)
            .order_by(Payment.paid_at.desc())
        ).scalars().all()
    )


def void_payment(
    db: Session, id: int, *, voided_by_user_id: int
) -> Payment | None:
    """Mark a payment as voided. Returns None if not found.

    This is the ONLY place in the codebase that touches an existing payment row.
    Only ``voided_at`` and ``voided_by_user_id`` are set — the rest of the row
    remains immutable.
    """
    db.execute(
        update(Payment)
        .where(Payment.id == id)
        .values(
            voided_at=datetime.now(timezone.utc),
            voided_by_user_id=voided_by_user_id,
        )
    )
    db.flush()
    return db.get(Payment, id)
