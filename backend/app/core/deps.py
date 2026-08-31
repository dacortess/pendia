"""FastAPI dependencies for authentication and authorization."""
from __future__ import annotations

from typing import TYPE_CHECKING

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.users.models import User

from app.auth.repository import get_user_by_id
from app.core.security import decode_access_token
from app.database.session import get_db_session
from app.users.models import User
from app.groups.models import GroupMembership


def get_current_user(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db_session),
) -> User:
    """Validate Bearer token from Authorization header and return the current user.

    Raises HTTPException 401 with distinct codes for each failure mode:
    - MISSING_TOKEN: no header or malformed "Bearer <token>"
    - TOKEN_EXPIRED: JWT has expired
    - INVALID_TOKEN: JWT signature/structure invalid
    - USER_NOT_FOUND: user id from token no longer exists in DB
    - USER_INACTIVE: user exists but is_active is False
    """
    # --- Parse Authorization header ---
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"detail": "Missing or invalid authorization header", "code": "MISSING_TOKEN"},
        )
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=401,
            detail={"detail": "Missing or invalid authorization header", "code": "MISSING_TOKEN"},
        )

    # --- Decode JWT (propagates exceptions → caught below) ---
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail={"detail": "Token has expired", "code": "TOKEN_EXPIRED"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail={"detail": "Invalid token", "code": "INVALID_TOKEN"},
        )

    # --- Resolve user from DB ---
    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(
            status_code=401,
            detail={"detail": "Invalid token", "code": "INVALID_TOKEN"},
        )
    try:
        user_id = int(sub)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=401,
            detail={"detail": "Invalid token", "code": "INVALID_TOKEN"},
        )

    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail={"detail": "User not found", "code": "USER_NOT_FOUND"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=401,
            detail={"detail": "User account is inactive", "code": "USER_INACTIVE"},
        )

    return user


def get_current_membership(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> GroupMembership:
    """Validate the current user belongs to `group_id` and return their membership.

    FastAPI resolves `group_id` automatically from the path parameter of the
    endpoint that uses this dependency, as long as the name matches.
    """
    from app.groups.repository import get_membership

    # Verify group exists
    from app.groups.repository import get_group_by_id

    group = get_group_by_id(db, group_id)
    if group is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Group not found", "code": "GROUP_NOT_FOUND"},
        )

    membership = get_membership(db, current_user.id, group_id)
    if membership is None:
        raise HTTPException(
            status_code=403,
            detail={"detail": "Not a member of this group", "code": "NOT_GROUP_MEMBER"},
        )

    return membership


def require_owner(membership: GroupMembership) -> None:
    """Raise 403 if membership.role is not 'owner'."""
    if membership.role != "owner":
        raise HTTPException(
            status_code=403,
            detail={"detail": "Only the group owner can perform this action", "code": "FORBIDDEN_NOT_OWNER"},
        )


def require_admin(membership: GroupMembership) -> None:
    """Raise 403 if membership.role is not 'owner' or 'admin'."""
    if membership.role not in ("owner", "admin"):
        raise HTTPException(
            status_code=403,
            detail={"detail": "Only admins or owners can perform this action", "code": "FORBIDDEN_NOT_ADMIN"},
        )


def require_admin_or_responsible(
    membership: GroupMembership, responsible_user_id: int | None, current_user: "User"
) -> None:
    """Raise 403 unless caller is owner/admin, or is the member responsible
    for this specific obligation.

    Unlike require_owner/require_admin this allows a ``member`` to pass when
    ``obligation.responsible_user_id == current_user.id``.
    """
    if membership.role in ("owner", "admin"):
        return
    if responsible_user_id is not None and responsible_user_id == current_user.id:
        return
    raise HTTPException(
        status_code=403,
        detail={
            "detail": "Solo el responsable de la obligación o un admin puede hacer esto",
            "code": "FORBIDDEN_NOT_RESPONSIBLE",
        },
    )
