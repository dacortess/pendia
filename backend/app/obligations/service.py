"""Business logic for obligations and period generation."""
from __future__ import annotations

import calendar
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.audit.service import log_action
from app.groups.repository import get_membership
from app.obligations import repository as repo

BOGOTA = ZoneInfo("America/Bogota")

_INTERVAL_MAP = {
    "MONTHLY": 1,
    "BIMONTHLY": 2,
    "QUARTERLY": 3,
    "SEMIANNUAL": 6,
    "ANNUAL": 12,
}


class ObligationError(Exception):
    """Expected obligation business logic failure."""

    def __init__(self, detail: str, code: str, status_code: int):
        self.detail = detail
        self.code = code
        self.status_code = status_code


def _last_day_of_month(year: int, month: int) -> int:
    """Return the last day of the given year/month."""
    return calendar.monthrange(year, month)[1]


def _compute_due_date(year: int, month: int, due_day: int) -> date:
    """Compute due_date with clamping: min(due_day, last day of month)."""
    day = min(due_day, _last_day_of_month(year, month))
    return date(year, month, day)


def _months_interval_for_periodicity(periodicity: str) -> int:
    """Return the number of months between periods."""
    return _INTERVAL_MAP[periodicity]


def _validate_category(db: Session, category_id: int, group_id: int) -> None:
    """Verify category belongs to the group or is a system category."""
    from sqlalchemy import select, or_
    from app.categories.models import Category
    cat = db.execute(
        select(Category).where(Category.id == category_id)
    ).scalar_one_or_none()
    if cat is None:
        return
    if cat.group_id is not None and cat.group_id != group_id:
        raise ObligationError(
            "La categoría pertenece a otro grupo",
            "CATEGORY_NOT_IN_GROUP",
            400,
        )


def _validate_payment_method(
    db: Session, payment_method_id: int, group_id: int
) -> None:
    """Verify payment method belongs to the same group."""
    from sqlalchemy import select
    from app.payment_methods.models import PaymentMethod
    pm = db.execute(
        select(PaymentMethod).where(PaymentMethod.id == payment_method_id)
    ).scalar_one_or_none()
    if pm is None:
        return
    if pm.group_id != group_id:
        raise ObligationError(
            "El medio de pago pertenece a otro grupo",
            "PAYMENT_METHOD_NOT_IN_GROUP",
            400,
        )


def _validate_responsible(
    db: Session, responsible_user_id: int, group_id: int
) -> None:
    """Verify responsible user is a member of the group."""
    membership = get_membership(db, responsible_user_id, group_id)
    if membership is None:
        raise ObligationError(
            "El usuario responsable no es miembro del grupo",
            "RESPONSIBLE_NOT_GROUP_MEMBER",
            400,
        )


def generate_periods_for_obligation(
    db: Session, obligation
) -> None:
    """Generate ObligationPeriod rows for an obligation.

    Lazy generation: creates periods from start_date up to (current month + 1).
    Idempotent: uses upsert to avoid duplicates. Also updates existing
    PENDIENTE periods that have become overdue to VENCIDO.
    """
    today = datetime.now(BOGOTA).date()
    current_year, current_month = today.year, today.month

    # Upper limit: current month + 1
    limit_year = current_year if current_month < 12 else current_year + 1
    limit_month = current_month + 1 if current_month < 12 else 1
    limit_date = date(limit_year, limit_month, 1)

    periodicity = obligation.periodicity
    start_date = obligation.start_date
    due_day = obligation.due_day
    end_date = obligation.end_date

    if periodicity == "ANNUAL":
        due_month = obligation.due_month
        start_year = start_date.year
        # Find the first year where the due_month is >= start_date
        first_candidate_year = start_year
        first_candidate_date = date(first_candidate_year, due_month, 1)
        if first_candidate_date < start_date:
            first_candidate_year += 1

        year = first_candidate_year
        while True:
            period_month = date(year, due_month, 1)
            if period_month > limit_date:
                break
            if end_date is not None and period_month > end_date:
                break
            due_date = _compute_due_date(year, due_month, due_day)
            status = "VENCIDO" if due_date < today else "PENDIENTE"
            repo.upsert_period(
                db,
                obligation_id=obligation.id,
                period_month=period_month,
                due_date=due_date,
                status=status,
            )
            year += 1
    else:
        interval = _months_interval_for_periodicity(periodicity)
        year = start_date.year
        month = start_date.month
        while True:
            period_month = date(year, month, 1)
            if period_month > limit_date:
                break
            if end_date is not None and period_month > end_date:
                break
            due_date = _compute_due_date(year, month, due_day)
            status = "VENCIDO" if due_date < today else "PENDIENTE"
            repo.upsert_period(
                db,
                obligation_id=obligation.id,
                period_month=period_month,
                due_date=due_date,
                status=status,
            )
            month += interval
            while month > 12:
                month -= 12
                year += 1

    # Update existing PENDIENTE periods that are now overdue
    for period in repo.get_periods_for_obligation(db, obligation.id):
        if period.status == "PENDIENTE" and period.due_date < today:
            repo.update_period_status(db, period.id, "VENCIDO")


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def create_obligation(
    db: Session,
    *,
    group_id: int,
    name: str,
    provider_name: str | None = None,
    external_reference: str | None = None,
    notes: str | None = None,
    currency: str = "COP",
    expected_amount_cents: int = 0,
    is_variable_amount: bool = False,
    is_subscription: bool = False,
    auto_debit: bool = False,
    is_essential: bool = True,
    periodicity: str = "MONTHLY",
    due_day: int = 1,
    due_month: int | None = None,
    start_date: date,
    end_date: date | None = None,
    category_id: int | None = None,
    payment_method_id: int | None = None,
    responsible_user_id: int | None = None,
    actor_user_id: int | None = None,
) -> "Obligation":
    """Create a new obligation and generate initial periods."""
    if category_id is not None:
        _validate_category(db, category_id, group_id)
    if payment_method_id is not None:
        _validate_payment_method(db, payment_method_id, group_id)
    if responsible_user_id is not None:
        _validate_responsible(db, responsible_user_id, group_id)

    obligation = repo.create_obligation(
        db,
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

    generate_periods_for_obligation(db, obligation)
    log_action(
        db,
        actor_user_id=actor_user_id,
        group_id=group_id,
        action="obligation.created",
        entity_type="Obligation",
        entity_id=obligation.id,
        metadata={"name": name},
    )
    db.commit()
    db.refresh(obligation)
    return obligation


def list_obligations(
    db: Session, group_id: int
) -> list:
    """Return active obligations for a group."""
    return repo.list_obligations_for_group(db, group_id, only_active=True)


def get_obligation(
    db: Session, id: int, group_id: int
):
    """Return an obligation by id within the group. Raises 404 if not found."""
    obligation = repo.get_obligation_by_id(db, id, group_id)
    if obligation is None:
        raise ObligationError(
            "Obligación no encontrada",
            "OBLIGATION_NOT_FOUND",
            404,
        )
    return obligation


def update_obligation(
    db: Session, id: int, group_id: int, *, actor_user_id: int | None = None, **fields
):
    """Update an obligation. Raises 404 if not found."""
    obligation = repo.get_obligation_by_id(db, id, group_id)
    if obligation is None:
        raise ObligationError(
            "Obligación no encontrada",
            "OBLIGATION_NOT_FOUND",
            404,
        )

    # Validate related entities if they are being updated
    if "category_id" in fields and fields["category_id"] is not None:
        _validate_category(db, fields["category_id"], group_id)
    if "payment_method_id" in fields and fields["payment_method_id"] is not None:
        _validate_payment_method(db, fields["payment_method_id"], group_id)
    if "responsible_user_id" in fields and fields["responsible_user_id"] is not None:
        _validate_responsible(db, fields["responsible_user_id"], group_id)

    for key, value in fields.items():
        setattr(obligation, key, value)

    log_action(
        db,
        actor_user_id=actor_user_id,
        group_id=group_id,
        action="obligation.updated",
        entity_type="Obligation",
        entity_id=obligation.id,
        metadata={"fields": list(fields.keys())},
    )
    db.commit()
    db.refresh(obligation)
    return obligation


def deactivate_obligation(
    db: Session, id: int, group_id: int, *, actor_user_id: int | None = None
) -> None:
    """Soft-delete an obligation (is_active=False). Raises 404 if not found."""
    obligation = repo.deactivate_obligation(db, id, group_id)
    if obligation is None:
        raise ObligationError(
            "Obligación no encontrada",
            "OBLIGATION_NOT_FOUND",
            404,
        )
    log_action(
        db,
        actor_user_id=actor_user_id,
        group_id=group_id,
        action="obligation.deactivated",
        entity_type="Obligation",
        entity_id=id,
        metadata=None,
    )
    db.commit()


# ---------------------------------------------------------------------------
# Periods
# ---------------------------------------------------------------------------


def _ensure_periods_generated_for_group(db: Session, group_id: int) -> None:
    """Generate/refresh periods for every active obligation in the group."""
    obligations = repo.list_obligations_for_group(db, group_id, only_active=True)
    for ob in obligations:
        generate_periods_for_obligation(db, ob)


def list_periods(
    db: Session,
    group_id: int,
    *,
    status: str | None = None,
    month: str | None = None,
) -> list:
    """List periods for a group, regenerating for all active obligations first."""
    _ensure_periods_generated_for_group(db, group_id)
    return repo.list_periods_for_group(db, group_id, status=status, month=month)


def get_period(
    db: Session, id: int, group_id: int
):
    """Return a period by id within the group. Raises 404 if not found."""
    period = repo.get_period_by_id(db, id, group_id)
    if period is None:
        raise ObligationError(
            "Período no encontrado",
            "PERIOD_NOT_FOUND",
            404,
        )
    return period
