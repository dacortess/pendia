"""Payment method endpoints — list, create, update under a group."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_membership, require_admin
from app.database.session import get_db_session
from app.groups.models import GroupMembership
from app.payment_methods import service
from app.payment_methods.schemas import (
    PaymentMethodCreate,
    PaymentMethodResponse,
    PaymentMethodUpdate,
)

router = APIRouter(
    prefix="/groups/{group_id}/payment-methods", tags=["payment-methods"]
)


# ---------------------------------------------------------------------------
# GET /groups/{group_id}/payment-methods — list (any member)
# ---------------------------------------------------------------------------

@router.get("", response_model=list[PaymentMethodResponse])
def list_payment_methods(
    group_id: int,
    membership: GroupMembership = Depends(get_current_membership),
    db: Session = Depends(get_db_session),
):
    return service.list_payment_methods(db, group_id)


# ---------------------------------------------------------------------------
# POST /groups/{group_id}/payment-methods — create (admin+)
# ---------------------------------------------------------------------------

@router.post("", response_model=PaymentMethodResponse, status_code=201)
def create_payment_method(
    group_id: int,
    body: PaymentMethodCreate,
    membership: GroupMembership = Depends(get_current_membership),
    db: Session = Depends(get_db_session),
):
    require_admin(membership)
    try:
        return service.create_payment_method(
            db,
            group_id=group_id,
            kind=body.kind,
            provider_name=body.provider_name,
            label=body.label,
            last4=body.last4,
            masked_key=body.masked_key,
            holder_name=body.holder_name,
        )
    except service.PaymentMethodError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"detail": exc.detail, "code": exc.code},
        )


# ---------------------------------------------------------------------------
# PATCH /groups/{group_id}/payment-methods/{id} — update (admin+)
# ---------------------------------------------------------------------------

@router.patch("/{id}", response_model=PaymentMethodResponse)
def update_payment_method(
    group_id: int,
    id: int,
    body: PaymentMethodUpdate,
    membership: GroupMembership = Depends(get_current_membership),
    db: Session = Depends(get_db_session),
):
    require_admin(membership)
    update_fields = body.model_dump(exclude_unset=True)
    if not update_fields:
        raise HTTPException(
            status_code=422,
            detail={"detail": "No fields to update", "code": "EMPTY_UPDATE"},
        )
    try:
        return service.update_payment_method(
            db, id=id, group_id=group_id, **update_fields
        )
    except service.PaymentMethodError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"detail": exc.detail, "code": exc.code},
        )
