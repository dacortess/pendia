"""Payment endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_membership, get_current_user, require_admin_or_responsible
from app.database.session import get_db_session
from app.groups.models import GroupMembership
from app.payments import service
from app.payments.schemas import PaymentCreate, PaymentResponse
from app.users.models import User

router = APIRouter(prefix="/groups/{group_id}/payments", tags=["payments"])


# ---------------------------------------------------------------------------
# POST /groups/{group_id}/periods/{id}/payments — register payment
# ---------------------------------------------------------------------------

period_payments_router = APIRouter(
    prefix="/groups/{group_id}/periods", tags=["payments"]
)


@period_payments_router.post(
    "/{period_id}/payments",
    response_model=PaymentResponse,
    status_code=201,
)
def register_payment(
    group_id: int,
    period_id: int,
    body: PaymentCreate,
    membership: GroupMembership = Depends(get_current_membership),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    from app.obligations.repository import get_period_by_id

    period = get_period_by_id(db, period_id, group_id)
    if period is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Período no encontrado", "code": "PERIOD_NOT_FOUND"},
        )
    obligation = period.obligation
    if obligation is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Obligación asociada no encontrada", "code": "OBLIGATION_NOT_FOUND"},
        )

    require_admin_or_responsible(membership, obligation.responsible_user_id, current_user)

    try:
        return service.register_payment(
            db,
            group_id=group_id,
            period_id=period_id,
            current_user_id=current_user.id,
            amount_cents=body.amount_cents,
            currency=body.currency,
            paid_at=body.paid_at,
            notes=body.notes,
            receipt_url=body.receipt_url,
        )
    except service.PaymentError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"detail": exc.detail, "code": exc.code},
        )


# ---------------------------------------------------------------------------
# GET /groups/{group_id}/payments — list payment history (any member)
# ---------------------------------------------------------------------------

@router.get("", response_model=list[PaymentResponse])
def list_payments(
    group_id: int,
    membership: GroupMembership = Depends(get_current_membership),
    db: Session = Depends(get_db_session),
):
    return service.list_payments(db, group_id)


# ---------------------------------------------------------------------------
# POST /groups/{group_id}/payments/{id}/void — void a payment
# ---------------------------------------------------------------------------

@router.post("/{payment_id}/void", response_model=PaymentResponse)
def void_payment(
    group_id: int,
    payment_id: int,
    membership: GroupMembership = Depends(get_current_membership),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    from app.payments.repository import get_payment_by_id as _get_payment
    from app.obligations.models import ObligationPeriod

    payment = _get_payment(db, payment_id, group_id)
    if payment is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Pago no encontrado", "code": "PAYMENT_NOT_FOUND"},
        )
    period = db.get(ObligationPeriod, payment.obligation_period_id)
    if period is not None:
        obligation = period.obligation
        if obligation is not None:
            require_admin_or_responsible(membership, obligation.responsible_user_id, current_user)

    try:
        return service.void_payment(
            db,
            group_id=group_id,
            payment_id=payment_id,
            voided_by_user_id=current_user.id,
        )
    except service.PaymentError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"detail": exc.detail, "code": exc.code},
        )
