"""Database queries for payment methods."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.payment_methods.models import PaymentMethod


def list_payment_methods_for_group(
    db: Session, group_id: int
) -> list[PaymentMethod]:
    """Return all payment methods for a group, ordered by created_at desc."""
    stmt = (
        select(PaymentMethod)
        .where(PaymentMethod.group_id == group_id)
        .order_by(PaymentMethod.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


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
) -> PaymentMethod:
    """Insert a new payment method. Caller must commit."""
    pm = PaymentMethod(
        group_id=group_id,
        kind=kind,
        provider_name=provider_name,
        label=label,
        last4=last4,
        masked_key=masked_key,
        holder_name=holder_name,
    )
    db.add(pm)
    db.flush()
    return pm


def get_payment_method_by_id(
    db: Session, id: int, group_id: int
) -> PaymentMethod | None:
    """Return a payment method by id, filtered by group_id (isolation between groups)."""
    return db.execute(
        select(PaymentMethod).where(
            PaymentMethod.id == id,
            PaymentMethod.group_id == group_id,
        )
    ).scalar_one_or_none()


def update_payment_method(
    db: Session, id: int, group_id: int, **fields
) -> PaymentMethod | None:
    """Update fields on a payment method. Returns the updated method or None."""
    pm = get_payment_method_by_id(db, id, group_id)
    if pm is None:
        return None
    for key, value in fields.items():
        setattr(pm, key, value)
    db.flush()
    return pm
