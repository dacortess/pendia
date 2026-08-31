"""Obligation and period endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_membership, require_admin
from app.database.session import get_db_session
from app.groups.models import GroupMembership
from app.obligations import service
from app.obligations.schemas import (
    ObligationCreate,
    ObligationPeriodResponse,
    ObligationResponse,
    ObligationUpdate,
)

router = APIRouter(
    prefix="/groups/{group_id}/obligations", tags=["obligations"]
)


# ---------------------------------------------------------------------------
# POST /groups/{group_id}/obligations — create obligation (admin+)
# ---------------------------------------------------------------------------

@router.post("", response_model=ObligationResponse, status_code=201)
def create_obligation(
    group_id: int,
    body: ObligationCreate,
    membership: GroupMembership = Depends(get_current_membership),
    db: Session = Depends(get_db_session),
):
    require_admin(membership)
    try:
        return service.create_obligation(
            db,
            group_id=group_id,
            name=body.name,
            provider_name=body.provider_name,
            external_reference=body.external_reference,
            notes=body.notes,
            currency=body.currency,
            expected_amount_cents=body.expected_amount_cents,
            is_variable_amount=body.is_variable_amount,
            is_subscription=body.is_subscription,
            auto_debit=body.auto_debit,
            is_essential=body.is_essential,
            periodicity=body.periodicity,
            due_day=body.due_day,
            due_month=body.due_month,
            start_date=body.start_date,
            end_date=body.end_date,
            category_id=body.category_id,
            payment_method_id=body.payment_method_id,
            responsible_user_id=body.responsible_user_id,
            actor_user_id=membership.user_id,
        )
    except service.ObligationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"detail": exc.detail, "code": exc.code},
        )


# ---------------------------------------------------------------------------
# GET /groups/{group_id}/obligations — list active obligations (any member)
# ---------------------------------------------------------------------------

@router.get("", response_model=list[ObligationResponse])
def list_obligations(
    group_id: int,
    membership: GroupMembership = Depends(get_current_membership),
    db: Session = Depends(get_db_session),
):
    return service.list_obligations(db, group_id)


# ---------------------------------------------------------------------------
# GET /groups/{group_id}/obligations/{id} — obligation detail (any member)
# ---------------------------------------------------------------------------

@router.get("/{id}", response_model=ObligationResponse)
def get_obligation(
    group_id: int,
    id: int,
    membership: GroupMembership = Depends(get_current_membership),
    db: Session = Depends(get_db_session),
):
    try:
        return service.get_obligation(db, id, group_id)
    except service.ObligationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"detail": exc.detail, "code": exc.code},
        )


# ---------------------------------------------------------------------------
# PATCH /groups/{group_id}/obligations/{id} — update obligation (admin+)
# ---------------------------------------------------------------------------

@router.patch("/{id}", response_model=ObligationResponse)
def update_obligation(
    group_id: int,
    id: int,
    body: ObligationUpdate,
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
    # Handle special "unset" sentinel values for nullable fields
    if "end_date" in update_fields and update_fields["end_date"] == "unset":
        update_fields["end_date"] = None
    if "category_id" in update_fields and update_fields["category_id"] == "unset":
        update_fields["category_id"] = None
    if "payment_method_id" in update_fields and update_fields["payment_method_id"] == "unset":
        update_fields["payment_method_id"] = None
    if "responsible_user_id" in update_fields and update_fields["responsible_user_id"] == "unset":
        update_fields["responsible_user_id"] = None

    try:
        return service.update_obligation(db, id, group_id, actor_user_id=membership.user_id, **update_fields)
    except service.ObligationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"detail": exc.detail, "code": exc.code},
        )


# ---------------------------------------------------------------------------
# DELETE /groups/{group_id}/obligations/{id} — soft-delete (admin+)
# ---------------------------------------------------------------------------

@router.delete("/{id}", status_code=204)
def deactivate_obligation(
    group_id: int,
    id: int,
    membership: GroupMembership = Depends(get_current_membership),
    db: Session = Depends(get_db_session),
):
    require_admin(membership)
    try:
        service.deactivate_obligation(db, id, group_id, actor_user_id=membership.user_id)
    except service.ObligationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"detail": exc.detail, "code": exc.code},
        )
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# GET /groups/{group_id}/periods — list periods (any member)
# ---------------------------------------------------------------------------

periods_router = APIRouter(
    prefix="/groups/{group_id}/periods", tags=["periods"]
)


@periods_router.get("", response_model=list[ObligationPeriodResponse])
def list_periods(
    group_id: int,
    status: str | None = Query(default=None),
    month: str | None = Query(default=None),
    membership: GroupMembership = Depends(get_current_membership),
    db: Session = Depends(get_db_session),
):
    periods = service.list_periods(db, group_id, status=status, month=month)
    db.commit()
    return periods


# ---------------------------------------------------------------------------
# GET /groups/{group_id}/periods/{id} — period detail (any member)
# ---------------------------------------------------------------------------

@periods_router.get("/{id}", response_model=ObligationPeriodResponse)
def get_period(
    group_id: int,
    id: int,
    membership: GroupMembership = Depends(get_current_membership),
    db: Session = Depends(get_db_session),
):
    try:
        return service.get_period(db, id, group_id)
    except service.ObligationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"detail": exc.detail, "code": exc.code},
        )
