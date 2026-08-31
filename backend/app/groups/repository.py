"""Database queries for groups — Group, GroupMembership, GroupInviteCode."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.groups.models import Group, GroupInviteCode, GroupMembership
from app.users.models import User


def create_group(db: Session, *, name: str, created_by: int) -> Group:
    """Insert a new group and return it (with id populated)."""
    group = Group(name=name, created_by=created_by)
    db.add(group)
    db.flush()
    return group


def get_group_by_id(db: Session, group_id: int) -> Group | None:
    """Return group by primary key or None."""
    return db.execute(select(Group).where(Group.id == group_id)).scalar_one_or_none()


def list_groups_for_user(db: Session, user_id: int) -> list[Group]:
    """Return all groups where the user has a membership."""
    stmt = (
        select(Group)
        .join(GroupMembership, Group.id == GroupMembership.group_id)
        .where(GroupMembership.user_id == user_id)
        .order_by(Group.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


def create_membership(
    db: Session, *, user_id: int, group_id: int, role: str
) -> GroupMembership:
    """Insert a membership row. Caller must commit."""
    membership = GroupMembership(user_id=user_id, group_id=group_id, role=role)
    db.add(membership)
    db.flush()
    return membership


def get_membership(db: Session, user_id: int, group_id: int) -> GroupMembership | None:
    """Return the membership for a user in a group, or None."""
    return db.execute(
        select(GroupMembership).where(
            GroupMembership.user_id == user_id,
            GroupMembership.group_id == group_id,
        )
    ).scalar_one_or_none()


def list_members(db: Session, group_id: int) -> list[dict]:
    """Return all members of a group with user info (email, full_name)."""
    stmt = (
        select(
            GroupMembership.user_id,
            GroupMembership.role,
            GroupMembership.joined_at,
            User.email,
            User.full_name,
        )
        .join(User, GroupMembership.user_id == User.id)
        .where(GroupMembership.group_id == group_id)
        .order_by(GroupMembership.joined_at)
    )
    rows = db.execute(stmt).all()
    return [
        {
            "user_id": row.user_id,
            "role": row.role,
            "joined_at": row.joined_at,
            "email": row.email,
            "full_name": row.full_name,
        }
        for row in rows
    ]


def update_membership_role(
    db: Session, *, user_id: int, group_id: int, role: str
) -> GroupMembership | None:
    """Update the role of a membership. Returns the updated membership or None."""
    membership = get_membership(db, user_id, group_id)
    if membership is None:
        return None
    membership.role = role
    db.flush()
    return membership


def delete_membership(db: Session, user_id: int, group_id: int) -> bool:
    """Delete a membership. Returns True if a row was deleted."""
    membership = get_membership(db, user_id, group_id)
    if membership is None:
        return False
    db.delete(membership)
    db.flush()
    return True


def update_group_name(db: Session, group_id: int, name: str) -> Group | None:
    """Update group name. Returns the updated group or None."""
    group = get_group_by_id(db, group_id)
    if group is None:
        return None
    group.name = name
    db.flush()
    return group


# ---------------------------------------------------------------------------
# Invite code queries
# ---------------------------------------------------------------------------


def create_invite_code(
    db: Session,
    *,
    group_id: int,
    code: str,
    role_to_assign: str,
    created_by_user_id: int,
    max_uses: int | None,
    expires_at: datetime | None,
) -> GroupInviteCode:
    """Insert a new invite code row. Caller must commit."""
    invite = GroupInviteCode(
        group_id=group_id,
        code=code,
        role_to_assign=role_to_assign,
        created_by_user_id=created_by_user_id,
        max_uses=max_uses,
        expires_at=expires_at,
    )
    db.add(invite)
    db.flush()
    return invite


def list_invite_codes(db: Session, group_id: int) -> list[GroupInviteCode]:
    """Return all invite codes for a group, ordered by created_at desc."""
    stmt = (
        select(GroupInviteCode)
        .where(GroupInviteCode.group_id == group_id)
        .order_by(GroupInviteCode.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


def get_invite_code_by_id(
    db: Session, id: int, group_id: int
) -> GroupInviteCode | None:
    """Return an invite code by id, filtered by group_id (isolation between groups)."""
    return db.execute(
        select(GroupInviteCode).where(
            GroupInviteCode.id == id,
            GroupInviteCode.group_id == group_id,
        )
    ).scalar_one_or_none()


def get_active_invite_code_by_code(db: Session, code: str) -> GroupInviteCode | None:
    """Return an active invite code by its code string (global lookup, not filtered by group)."""
    return db.execute(
        select(GroupInviteCode).where(
            GroupInviteCode.code == code,
            GroupInviteCode.is_active.is_(True),
        )
    ).scalar_one_or_none()


def revoke_invite_code(
    db: Session, id: int, group_id: int
) -> GroupInviteCode | None:
    """Set is_active=False on an invite code. Returns the code or None if not found."""
    invite = get_invite_code_by_id(db, id, group_id)
    if invite is None:
        return None
    invite.is_active = False
    db.flush()
    return invite


def increment_invite_code_uses(db: Session, id: int) -> None:
    """Increment uses_count by 1 on an invite code."""
    from sqlalchemy import update

    db.execute(
        update(GroupInviteCode)
        .where(GroupInviteCode.id == id)
        .values(uses_count=GroupInviteCode.uses_count + 1)
    )
    db.flush()
