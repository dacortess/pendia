"""Category endpoints — list + create under a group."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.categories import service
from app.categories.schemas import CategoryCreate, CategoryResponse
from app.core.deps import get_current_membership, require_admin
from app.database.session import get_db_session
from app.groups.models import GroupMembership

router = APIRouter(prefix="/groups/{group_id}/categories", tags=["categories"])


# ---------------------------------------------------------------------------
# GET /groups/{group_id}/categories — list system + group categories (any member)
# ---------------------------------------------------------------------------

@router.get("", response_model=list[CategoryResponse])
def list_categories(
    group_id: int,
    membership: GroupMembership = Depends(get_current_membership),
    db: Session = Depends(get_db_session),
):
    return service.list_categories(db, group_id)


# ---------------------------------------------------------------------------
# POST /groups/{group_id}/categories — create custom category (admin+)
# ---------------------------------------------------------------------------

@router.post("", response_model=CategoryResponse, status_code=201)
def create_category(
    group_id: int,
    body: CategoryCreate,
    membership: GroupMembership = Depends(get_current_membership),
    db: Session = Depends(get_db_session),
):
    require_admin(membership)
    try:
        return service.create_category(
            db, group_id=group_id, name=body.name, icon=body.icon
        )
    except service.CategoryError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"detail": exc.detail, "code": exc.code},
        )
