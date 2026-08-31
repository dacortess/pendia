"""Database queries for obligations and obligation periods."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.obligations.models import Obligation, ObligationPeriod


def create_obligation(
    db: Session,
    *,
    group_id: int,
    name: str,
    provider_name: str | None,
    external_reference: str | None,
    notes: str | None,
    currency: str,
    expected_amount_cents: int,
    is_variable_amount: bool,
    is_subscription: bool,
    auto_debit: bool,
    is_essential: bool,
    periodicity: str,
    due_day: int,
    due_month: int | None,
    start_date: date,
    end_date: date | None,
    category_id: int | None,
    payment_method_id: int | None,
    responsible_user_id: int | None,
) -> Obligation:
    """Insert a new obligation. Caller must commit."""
    obligation = Obligation(
        group_id=group_id,
        name=name,
        provider_name=provider_name,
        external_reference=external_reference,
        notes=notes,
        currency=currency,
        expected_amount_cents=expected_amount_cents,
        is_variable_amount=is_variable_amount,
        is_subscription=is_subscription,
        auto_debit=auto_debit,
        is_essential=is_essential,
        periodicity=periodicity,
        due_day=due_day,
        due_month=due_month,
        start_date=start_date,
        end_date=end_date,
        category_id=category_id,
        payment_method_id=payment_method_id,
        responsible_user_id=responsible_user_id,
    )
    db.add(obligation)
    db.flush()
    return obligation


def get_obligation_by_id(
    db: Session, id: int, group_id: int
) -> Obligation | None:
    """Return an obligation by id, filtered by group_id."""
    return db.execute(
        select(Obligation).where(
            Obligation.id == id,
            Obligation.group_id == group_id,
        )
    ).scalar_one_or_none()


def list_obligations_for_group(
    db: Session, group_id: int, *, only_active: bool = True
) -> list[Obligation]:
    """Return all obligations for a group, optionally only active ones."""
    stmt = select(Obligation).where(Obligation.group_id == group_id)
    if only_active:
        stmt = stmt.where(Obligation.is_active.is_(True))
    stmt = stmt.order_by(Obligation.created_at.desc())
    return list(db.execute(stmt).scalars().all())


def update_obligation(
    db: Session, id: int, group_id: int, **fields
) -> Obligation | None:
    """Update fields on an obligation. Returns the updated obligation or None."""
    obligation = get_obligation_by_id(db, id, group_id)
    if obligation is None:
        return None
    for key, value in fields.items():
        setattr(obligation, key, value)
    db.flush()
    return obligation


def deactivate_obligation(
    db: Session, id: int, group_id: int
) -> Obligation | None:
    """Set is_active=False on an obligation. Returns the obligation or None."""
    return update_obligation(db, id, group_id, is_active=False)


# ---------------------------------------------------------------------------
# Period queries
# ---------------------------------------------------------------------------

def list_periods_for_group(
    db: Session,
    group_id: int,
    *,
    status: str | None = None,
    month: str | None = None,
) -> list[ObligationPeriod]:
    """Return obligation periods for a group, with optional filters.

    Args:
        status: exact status filter (e.g. 'PENDIENTE', 'VENCIDO').
        month: filter by period_month in 'YYYY-MM' format.
    """
    stmt = (
        select(ObligationPeriod)
        .join(Obligation, ObligationPeriod.obligation_id == Obligation.id)
        .where(Obligation.group_id == group_id)
    )
    if status is not None:
        stmt = stmt.where(ObligationPeriod.status == status)
    if month is not None:
        from datetime import date as _date
        year, mon = month.split("-")
        month_date = _date(int(year), int(mon), 1)
        stmt = stmt.where(ObligationPeriod.period_month == month_date)
    stmt = stmt.order_by(ObligationPeriod.period_month.desc())
    return list(db.execute(stmt).scalars().all())


def get_period_by_id(
    db: Session, id: int, group_id: int
) -> ObligationPeriod | None:
    """Return an obligation period by id, filtered by group_id via Obligation."""
    return db.execute(
        select(ObligationPeriod)
        .join(Obligation, ObligationPeriod.obligation_id == Obligation.id)
        .where(
            ObligationPeriod.id == id,
            Obligation.group_id == group_id,
        )
    ).scalar_one_or_none()


def get_periods_for_obligation(
    db: Session, obligation_id: int
) -> list[ObligationPeriod]:
    """Return all periods for a specific obligation, ordered by period_month."""
    stmt = (
        select(ObligationPeriod)
        .where(ObligationPeriod.obligation_id == obligation_id)
        .order_by(ObligationPeriod.period_month)
    )
    return list(db.execute(stmt).scalars().all())


def upsert_period(
    db: Session,
    *,
    obligation_id: int,
    period_month: date,
    due_date: date,
    status: str,
) -> ObligationPeriod:
    """Insert a period if it doesn't exist (by unique obligation_id + period_month).

    If it already exists, returns the existing period WITHOUT updating it.
    """
    existing = db.execute(
        select(ObligationPeriod).where(
            ObligationPeriod.obligation_id == obligation_id,
            ObligationPeriod.period_month == period_month,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    period = ObligationPeriod(
        obligation_id=obligation_id,
        period_month=period_month,
        due_date=due_date,
        status=status,
    )
    db.add(period)
    db.flush()
    return period


def update_period_status(
    db: Session, period_id: int, status: str
) -> None:
    """Update the status of an obligation period."""
    from sqlalchemy import update
    db.execute(
        update(ObligationPeriod)
        .where(ObligationPeriod.id == period_id)
        .values(status=status)
    )
    db.flush()
