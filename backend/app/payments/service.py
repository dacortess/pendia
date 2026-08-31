"""Business logic for payments."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.audit.service import log_action
from app.obligations import repository as obl_repo
from app.payments import repository as pay_repo

BOGOTA = ZoneInfo("America/Bogota")


class PaymentError(Exception):
    """Expected payment business logic failure."""

    def __init__(self, detail: str, code: str, status_code: int):
        self.detail = detail
        self.code = code
        self.status_code = status_code


def _period_status_for_due_date(due_date, today) -> str:
    """Return PENDIENTE or VENCIDO based on due_date vs today."""
    return "VENCIDO" if due_date < today else "PENDIENTE"


def register_payment(
    db: Session,
    *,
    group_id: int,
    period_id: int,
    current_user_id: int,
    amount_cents: int,
    currency: str,
    paid_at,
    notes: str | None,
    receipt_url: str | None,
):
    """Register a payment for an obligation period.

    Raises PaymentError on business rule violations.
    Returns the created Payment on success (caller must commit).
    """
    period = obl_repo.get_period_by_id(db, period_id, group_id)
    if period is None:
        raise PaymentError(
            "Período no encontrado",
            "PERIOD_NOT_FOUND",
            404,
        )

    if period.status == "PAGADO":
        raise PaymentError(
            "Este período ya tiene un pago registrado. Anule el pago existente primero.",
            "PERIOD_ALREADY_PAID",
            409,
        )

    obligation = period.obligation
    if obligation is None:
        raise PaymentError(
            "Obligación asociada no encontrada",
            "OBLIGATION_NOT_FOUND",
            404,
        )

    if currency != obligation.currency:
        raise PaymentError(
            f"La moneda del pago ({currency}) no coincide con la de la obligación ({obligation.currency})",
            "CURRENCY_MISMATCH",
            400,
        )

    payment = pay_repo.create_payment(
        db,
        obligation_period_id=period.id,
        registered_by_user_id=current_user_id,
        amount_cents=amount_cents,
        currency=currency,
        paid_at=paid_at,
        notes=notes,
        receipt_url=receipt_url,
    )

    obl_repo.update_period_status(db, period.id, "PAGADO")
    log_action(
        db,
        actor_user_id=current_user_id,
        group_id=group_id,
        action="payment.registered",
        entity_type="Payment",
        entity_id=payment.id,
        metadata={"amount_cents": amount_cents, "currency": currency},
    )

    db.commit()
    db.refresh(payment)
    return payment


def void_payment(
    db: Session,
    *,
    group_id: int,
    payment_id: int,
    voided_by_user_id: int,
):
    """Void (anul) a payment and revert its period status.

    Raises PaymentError on business rule violations.
    Returns the voided Payment on success (caller must commit).
    """
    payment = pay_repo.get_payment_by_id(db, payment_id, group_id)
    if payment is None:
        raise PaymentError(
            "Pago no encontrado",
            "PAYMENT_NOT_FOUND",
            404,
        )

    if payment.voided_at is not None:
        raise PaymentError(
            "Este pago ya fue anulado",
            "PAYMENT_ALREADY_VOIDED",
            409,
        )

    pay_repo.void_payment(db, payment.id, voided_by_user_id=voided_by_user_id)

    period = db.get(obl_repo.ObligationPeriod, payment.obligation_period_id)
    if period is not None:
        today = datetime.now(BOGOTA).date()
        new_status = _period_status_for_due_date(period.due_date, today)
        obl_repo.update_period_status(db, period.id, new_status)

    log_action(
        db,
        actor_user_id=voided_by_user_id,
        group_id=group_id,
        action="payment.voided",
        entity_type="Payment",
        entity_id=payment.id,
        metadata=None,
    )

    db.commit()
    db.refresh(payment)
    return payment


def list_payments(db: Session, group_id: int) -> list:
    """List all payments for a group (including voided)."""
    return pay_repo.list_payments_for_group(db, group_id)
