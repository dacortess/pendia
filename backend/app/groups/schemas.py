"""Pydantic schemas for group endpoints."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class GroupCreate(BaseModel):
    """Request body for POST /groups."""
    name: str = Field(min_length=1, max_length=200)


class GroupUpdate(BaseModel):
    """Request body for PATCH /groups/{group_id}."""
    name: str = Field(min_length=1, max_length=200)


class GroupResponse(BaseModel):
    """Group detail — includes my_role for the requesting user."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_by: int
    created_at: datetime
    updated_at: datetime
    my_role: str


class MemberAdd(BaseModel):
    """Request body for POST /groups/{group_id}/members."""
    email: EmailStr
    role: Literal["admin", "member"] = "member"


class MemberRoleUpdate(BaseModel):
    """Request body for PATCH /groups/{group_id}/members/{user_id}."""
    role: Literal["owner", "admin", "member"]


class MemberResponse(BaseModel):
    """Member detail with user info."""
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    email: str
    full_name: str
    role: str
    joined_at: datetime


# ---------------------------------------------------------------------------
# Invite codes
# ---------------------------------------------------------------------------

class InviteCodeCreate(BaseModel):
    """Request body for POST /groups/{group_id}/invite-codes."""
    role_to_assign: Literal["admin", "member"] = "member"
    max_uses: int | None = None
    expires_at: datetime | None = None

    @field_validator("role_to_assign")
    @classmethod
    def never_owner(cls, v: str) -> str:
        if v == "owner":
            raise ValueError("role_to_assign cannot be 'owner'")
        return v


class InviteCodeResponse(BaseModel):
    """Invite code detail."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    role_to_assign: str
    max_uses: int | None
    uses_count: int
    expires_at: datetime | None
    is_active: bool
    created_at: datetime


class JoinPreviewResponse(BaseModel):
    """Response for GET /groups/join/preview — only group name."""
    group_name: str


class JoinRequest(BaseModel):
    """Request body for POST /groups/join."""
    code: str


class JoinResponse(BaseModel):
    """Response after joining a group via code."""
    group_id: int
    group_name: str
    role: str


class PasswordResetResponse(BaseModel):
    """Response for POST .../reset-password — temporary password (admin+ only)."""
    user_id: int
    temporary_password: str
