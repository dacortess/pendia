"""Dashboard endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_membership
from app.database.session import get_db_session
from app.dashboard import service
from app.dashboard.schemas import DashboardResponse
from app.groups.models import GroupMembership

router = APIRouter(
    prefix="/groups/{group_id}/dashboard", tags=["dashboard"]
)


@router.get("", response_model=DashboardResponse)
def get_dashboard(
    group_id: int,
    month: str | None = Query(default=None),
    membership: GroupMembership = Depends(get_current_membership),
    db: Session = Depends(get_db_session),
):
    try:
        result = service.get_dashboard(db, group_id, month)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"detail": str(exc), "code": "INVALID_MONTH_FORMAT"},
        )
    return result
