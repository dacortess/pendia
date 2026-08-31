"""Group endpoints — CRUD + membership management."""
from __future__ import annotations

import io

import qrcode
import qrcode.image.pil
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import (
    get_current_membership,
    get_current_user,
    require_admin,
    require_owner,
)
from app.database.session import get_db_session
from app.groups import repository as repo
from app.groups import service
from app.groups.models import GroupMembership
from app.groups.schemas import (
    GroupCreate,
    GroupResponse,
    GroupUpdate,
    InviteCodeCreate,
    InviteCodeResponse,
    JoinPreviewResponse,
    JoinRequest,
    JoinResponse,
    MemberAdd,
    MemberResponse,
    MemberRoleUpdate,
    PasswordResetResponse,
)
from app.core.rate_limit import limiter
from app.users.models import User

router = APIRouter(prefix="/groups", tags=["groups"])


# ---------------------------------------------------------------------------
# POST /groups/join — join a group via invite code (authenticated, no membership required)
# ---------------------------------------------------------------------------

@router.post("/join", response_model=JoinResponse, status_code=201)
@limiter.limit("10/minute")
def join_group(
    request: Request,
    body: JoinRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    try:
        result = service.join_group_by_code(db, user_id=current_user.id, code=body.code)
    except service.GroupError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"detail": exc.detail, "code": exc.code},
        )
    db.commit()
    return result


# ---------------------------------------------------------------------------
# GET /groups/join/preview — preview group name for an invite code (public, no auth)
# ---------------------------------------------------------------------------

@router.get("/join/preview", response_model=JoinPreviewResponse)
def join_preview(
    code: str = Query(..., min_length=1),
    db: Session = Depends(get_db_session),
):
    try:
        group_name = service.get_group_name_for_code(db, code)
    except service.GroupError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"detail": exc.detail, "code": exc.code},
        )
    return JoinPreviewResponse(group_name=group_name)


# ---------------------------------------------------------------------------
# POST /groups — create group (creator becomes owner)
# ---------------------------------------------------------------------------

@router.post("", response_model=GroupResponse, status_code=201)
def create_group(
    body: GroupCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    try:
        result = service.create_group(db, name=body.name, user_id=current_user.id)
    except service.GroupError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"detail": exc.detail, "code": exc.code},
        )
    return result


# ---------------------------------------------------------------------------
# GET /groups — list current user's groups
# ---------------------------------------------------------------------------

@router.get("", response_model=list[GroupResponse])
def list_groups(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    groups = repo.list_groups_for_user(db, current_user.id)
    result = []
    for g in groups:
        membership = repo.get_membership(db, current_user.id, g.id)
        result.append({
            "id": g.id,
            "name": g.name,
            "created_by": g.created_by,
            "created_at": g.created_at,
            "updated_at": g.updated_at,
            "my_role": membership.role if membership else "member",
        })
    return result


# ---------------------------------------------------------------------------
# GET /groups/{group_id} — group detail (any member)
# ---------------------------------------------------------------------------

@router.get("/{group_id}", response_model=GroupResponse)
def get_group(
    group_id: int,
    membership: GroupMembership = Depends(get_current_membership),
    db: Session = Depends(get_db_session),
):
    group = repo.get_group_by_id(db, group_id)
    if group is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Group not found", "code": "GROUP_NOT_FOUND"},
        )
    return {
        "id": group.id,
        "name": group.name,
        "created_by": group.created_by,
        "created_at": group.created_at,
        "updated_at": group.updated_at,
        "my_role": membership.role,
    }


# ---------------------------------------------------------------------------
# PATCH /groups/{group_id} — edit name (owner only)
# ---------------------------------------------------------------------------

@router.patch("/{group_id}", response_model=GroupResponse)
def update_group(
    group_id: int,
    body: GroupUpdate,
    membership: GroupMembership = Depends(get_current_membership),
    db: Session = Depends(get_db_session),
):
    require_owner(membership)
    group = repo.update_group_name(db, group_id, body.name)
    db.commit()
    db.refresh(group)
    return {
        "id": group.id,
        "name": group.name,
        "created_by": group.created_by,
        "created_at": group.created_at,
        "updated_at": group.updated_at,
        "my_role": membership.role,
    }


# ---------------------------------------------------------------------------
# POST /groups/{group_id}/invite-codes — create invite code (admin+)
# ---------------------------------------------------------------------------

@router.post(
    "/{group_id}/invite-codes",
    response_model=InviteCodeResponse,
    status_code=201,
)
def create_invite_code(
    group_id: int,
    body: InviteCodeCreate,
    membership: GroupMembership = Depends(get_current_membership),
    db: Session = Depends(get_db_session),
):
    require_admin(membership)
    try:
        invite = service.create_invite_code(
            db,
            group_id=group_id,
            role_to_assign=body.role_to_assign,
            max_uses=body.max_uses,
            expires_at=body.expires_at,
            created_by_user_id=membership.user_id,
        )
    except service.GroupError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"detail": exc.detail, "code": exc.code},
        )
    return invite


# ---------------------------------------------------------------------------
# GET /groups/{group_id}/invite-codes — list invite codes (admin+)
# ---------------------------------------------------------------------------

@router.get(
    "/{group_id}/invite-codes",
    response_model=list[InviteCodeResponse],
)
def list_invite_codes(
    group_id: int,
    membership: GroupMembership = Depends(get_current_membership),
    db: Session = Depends(get_db_session),
):
    require_admin(membership)
    return service.list_invite_codes(db, group_id)


# ---------------------------------------------------------------------------
# PATCH /groups/{group_id}/invite-codes/{id} — revoke invite code (admin+)
# ---------------------------------------------------------------------------

@router.patch(
    "/{group_id}/invite-codes/{id}",
    response_model=InviteCodeResponse,
)
def revoke_invite_code(
    group_id: int,
    id: int,
    membership: GroupMembership = Depends(get_current_membership),
    db: Session = Depends(get_db_session),
):
    require_admin(membership)
    try:
        invite = service.revoke_invite_code(db, id=id, group_id=group_id)
    except service.GroupError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"detail": exc.detail, "code": exc.code},
        )
    return invite


# ---------------------------------------------------------------------------
# GET /groups/{group_id}/invite-codes/{id}/qr — QR code image (admin+)
# ---------------------------------------------------------------------------

@router.get(
    "/{group_id}/invite-codes/{id}/qr",
    response_class=Response,
)
def get_invite_code_qr(
    group_id: int,
    id: int,
    membership: GroupMembership = Depends(get_current_membership),
    db: Session = Depends(get_db_session),
):
    require_admin(membership)
    invite = repo.get_invite_code_by_id(db, id, group_id)
    if invite is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Código de invitación no encontrado", "code": "INVITE_CODE_NOT_FOUND"},
        )
    url = f"{settings.FRONTEND_ORIGIN}/join?code={invite.code}"
    img = qrcode.make(url, image_factory=qrcode.image.pil.PilImage)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


# ---------------------------------------------------------------------------
# POST /groups/{group_id}/members — add member by email (admin+)
# ---------------------------------------------------------------------------

@router.post("/{group_id}/members", response_model=MemberResponse, status_code=201)
def add_member(
    group_id: int,
    body: MemberAdd,
    membership: GroupMembership = Depends(get_current_membership),
    db: Session = Depends(get_db_session),
):
    require_admin(membership)
    try:
        result = service.add_member(
            db, group_id=group_id, email=body.email, role=body.role, actor_user_id=membership.user_id
        )
    except service.GroupError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"detail": exc.detail, "code": exc.code},
        )
    # Fetch full user info for response
    user = repo.get_membership(db, result["user_id"], group_id)
    from app.auth.repository import get_user_by_id
    user_obj = get_user_by_id(db, result["user_id"])
    return {
        "user_id": result["user_id"],
        "email": user_obj.email,
        "full_name": user_obj.full_name,
        "role": result["role"],
        "joined_at": result["joined_at"],
    }


# ---------------------------------------------------------------------------
# PATCH /groups/{group_id}/members/{user_id} — change role (admin+)
# ---------------------------------------------------------------------------

@router.patch("/{group_id}/members/{user_id}", response_model=MemberResponse)
def change_member_role(
    group_id: int,
    user_id: int,
    body: MemberRoleUpdate,
    membership: GroupMembership = Depends(get_current_membership),
    db: Session = Depends(get_db_session),
):
    require_admin(membership)
    try:
        result = service.change_member_role(
            db, group_id=group_id, target_user_id=user_id, new_role=body.role,
            actor_user_id=membership.user_id, caller_membership=membership,
        )
    except service.GroupError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"detail": exc.detail, "code": exc.code},
        )
    from app.auth.repository import get_user_by_id
    user_obj = get_user_by_id(db, user_id)
    return {
        "user_id": result["user_id"],
        "email": user_obj.email,
        "full_name": user_obj.full_name,
        "role": result["role"],
        "joined_at": result["joined_at"],
    }


# ---------------------------------------------------------------------------
# DELETE /groups/{group_id}/members/{user_id} — remove member (admin+)
# ---------------------------------------------------------------------------

@router.delete("/{group_id}/members/{user_id}", status_code=204)
def remove_member(
    group_id: int,
    user_id: int,
    membership: GroupMembership = Depends(get_current_membership),
    db: Session = Depends(get_db_session),
):
    require_admin(membership)
    try:
        service.remove_member(db, group_id=group_id, target_user_id=user_id, actor_user_id=membership.user_id)
    except service.GroupError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"detail": exc.detail, "code": exc.code},
        )
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# POST /groups/{group_id}/members/{user_id}/reset-password — admin+
# ---------------------------------------------------------------------------

@router.post(
    "/{group_id}/members/{user_id}/reset-password",
    response_model=PasswordResetResponse,
)
def reset_member_password(
    group_id: int,
    user_id: int,
    membership: GroupMembership = Depends(get_current_membership),
    db: Session = Depends(get_db_session),
):
    require_admin(membership)
    try:
        result = service.reset_member_password(
            db, group_id=group_id, target_user_id=user_id,
            actor_user_id=membership.user_id,
        )
    except service.GroupError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"detail": exc.detail, "code": exc.code},
        )
    return result
