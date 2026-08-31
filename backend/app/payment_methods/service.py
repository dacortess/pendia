"""Business logic for payment methods."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.payment_methods import repository as repo


class PaymentMethodError(Exception):
    """Expected payment method business logic failure."""

    def __init__(self, detail: str, code: str, status_code: int):
        self.detail = detail
        self.code = code
        self.status_code = status_code


def list_payment_methods(db: Session, group_id: int) -> list:
    """Return all payment methods for a group."""
    return repo.list_payment_methods_for_group(db, group_id)


def create_payment_method(
    db: Session,
    *,
    group_id: int,
    kind: str,
    provider_name: str,
    label: str,
    last4: str | None,
    masked_key: str | None,
    holder_name: str,
):
    """Create a payment method for a group."""
    pm = repo.create_payment_method(
        db,
        group_id=group_id,
        kind=kind,
        provider_name=provider_name,
        label=label,
        last4=last4,
        masked_key=masked_key,
        holder_name=holder_name,
    )
    db.commit()
    db.refresh(pm)
    return pm


def update_payment_method(
    db: Session, *, id: int, group_id: int, **fields
):
    """Update a payment method. Raises PaymentMethodError 404 if not found."""
    pm = repo.update_payment_method(db, id, group_id, **fields)
    if pm is None:
        raise PaymentMethodError(
            "Medio de pago no encontrado",
            "PAYMENT_METHOD_NOT_FOUND",
            404,
        )
    db.commit()
    db.refresh(pm)
    return pm
