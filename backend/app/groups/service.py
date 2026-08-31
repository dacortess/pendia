"""Business logic for groups — CRUD + membership management."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.audit.service import log_action
from app.core.security import hash_password
from app.auth.repository import (
    get_user_by_email,
    update_password_hash,
    revoke_all_refresh_tokens_for_user,
)
from app.groups import repository as repo
from app.groups.models import GroupMembership


class GroupError(Exception):
    """Expected group business logic failure. Carries detail + code for the API response."""

    def __init__(self, detail: str, code: str, status_code: int):
        self.detail = detail
        self.code = code
        self.status_code = status_code


def create_group(db: Session, *, name: str, user_id: int) -> dict:
    """Create a group and make the user the owner. Single transaction.

    Returns dict with group fields + my_role.
    """
    group = repo.create_group(db, name=name, created_by=user_id)
    repo.create_membership(db, user_id=user_id, group_id=group.id, role="owner")
    log_action(
        db,
        actor_user_id=user_id,
        group_id=group.id,
        action="group.created",
        entity_type="Group",
        entity_id=group.id,
        metadata={"name": name},
    )
    db.commit()
    db.refresh(group)
    return {
        "id": group.id,
        "name": group.name,
        "created_by": group.created_by,
        "created_at": group.created_at,
        "updated_at": group.updated_at,
        "my_role": "owner",
    }


def add_member(db: Session, *, group_id: int, email: str, role: str, actor_user_id: int) -> dict:
    """Add a user to a group by email.

    Raises GroupError if user not found or already a member.
    Returns the new membership as a dict.
    """
    user = get_user_by_email(db, email)
    if user is None:
        raise GroupError(
            "El usuario debe registrarse primero",
            "USER_NOT_FOUND_MUST_REGISTER",
            404,
        )

    existing = repo.get_membership(db, user.id, group_id)
    if existing is not None:
        raise GroupError(
            "El usuario ya es miembro de este grupo",
            "ALREADY_MEMBER",
            409,
        )

    membership = repo.create_membership(db, user_id=user.id, group_id=group_id, role=role)
    log_action(
        db,
        actor_user_id=actor_user_id,
        group_id=group_id,
        action="membership.added",
        entity_type="GroupMembership",
        entity_id=user.id,
        metadata={"role": role},
    )
    db.commit()
    db.refresh(membership)
    return {
        "user_id": membership.user_id,
        "role": membership.role,
        "joined_at": membership.joined_at,
    }


def change_member_role(
    db: Session,
    *,
    group_id: int,
    target_user_id: int,
    new_role: str,
    actor_user_id: int,
    caller_membership: GroupMembership,
) -> dict:
    """Change a member's role.

    Raises GroupError if:
      - caller is not admin+ (checked by caller_membership)
      - target is not a member
      - caller tries to transfer to themselves
      - caller is not owner and tries to assign owner
    Returns the updated membership as a dict.

    Ownership transfer (new_role == "owner"):
      - Only the current owner can initiate it.
      - Current owner is demoted to "admin".
      - Target is promoted to "owner".
      - Audit entry: membership.ownership_transferred.
    """
    target_membership = repo.get_membership(db, target_user_id, group_id)
    if target_membership is None:
        raise GroupError(
            "El usuario no es miembro de este grupo",
            "NOT_GROUP_MEMBER",
            404,
        )

    if new_role == "owner":
        # --- Ownership transfer ---
        if caller_membership.role != "owner":
            raise GroupError(
                "Solo el propietario puede transferir la propiedad",
                "FORBIDDEN_NOT_OWNER",
                403,
            )
        if caller_membership.user_id == target_user_id:
            raise GroupError(
                "No puedes transferir la propiedad a ti mismo",
                "CANNOT_TRANSFER_TO_SELF",
                400,
            )
        # Demote current owner to admin, promote target to owner
        repo.update_membership_role(
            db, user_id=caller_membership.user_id, group_id=group_id, role="admin"
        )
        repo.update_membership_role(
            db, user_id=target_user_id, group_id=group_id, role="owner"
        )
        log_action(
            db,
            actor_user_id=actor_user_id,
            group_id=group_id,
            action="membership.ownership_transferred",
            entity_type="GroupMembership",
            entity_id=target_user_id,
            metadata=None,
        )
        db.commit()
        updated = repo.get_membership(db, target_user_id, group_id)
        return {
            "user_id": updated.user_id,
            "role": updated.role,
            "joined_at": updated.joined_at,
        }

    # --- Non-owner role change ---
    if caller_membership.role == "owner":
        pass  # owner can change any non-owner role
    elif caller_membership.role != "admin":
        raise GroupError(
            "Se requiere rol de administrador",
            "NOT_ADMIN",
            403,
        )

    if target_membership.role == "owner":
        raise GroupError(
            "No se puede modificar el rol del propietario",
            "CANNOT_MODIFY_OWNER",
            403,
        )

    updated = repo.update_membership_role(
        db, user_id=target_user_id, group_id=group_id, role=new_role
    )
    log_action(
        db,
        actor_user_id=actor_user_id,
        group_id=group_id,
        action="membership.role_changed",
        entity_type="GroupMembership",
        entity_id=target_user_id,
        metadata={"new_role": new_role},
    )
    db.commit()
    db.refresh(updated)
    return {
        "user_id": updated.user_id,
        "role": updated.role,
        "joined_at": updated.joined_at,
    }


def remove_member(db: Session, *, group_id: int, target_user_id: int, actor_user_id: int) -> None:
    """Remove a member from a group.

    Raises GroupError if target is the owner or not a member.
    """
    membership = repo.get_membership(db, target_user_id, group_id)
    if membership is None:
        raise GroupError(
            "El usuario no es miembro de este grupo",
            "NOT_GROUP_MEMBER",
            404,
        )

    if membership.role == "owner":
        raise GroupError(
            "No se puede eliminar al propietario del grupo",
            "CANNOT_MODIFY_OWNER",
            403,
        )

    repo.delete_membership(db, target_user_id, group_id)
    log_action(
        db,
        actor_user_id=actor_user_id,
        group_id=group_id,
        action="membership.removed",
        entity_type="GroupMembership",
        entity_id=target_user_id,
        metadata=None,
    )
    db.commit()


def list_members(db: Session, group_id: int) -> list[dict]:
    """Return all members of a group with user info (email, full_name, role)."""
    return repo.list_members(db, group_id)


def reset_member_password(
    db: Session, *, group_id: int, target_user_id: int, actor_user_id: int
) -> dict:
    """Reset a member's password: generate temp password, hash it, revoke all sessions.

    Raises GroupError if target is not a member of the group.
    Returns {user_id, temporary_password}. The temp password is NEVER stored in audit metadata.
    """
    membership = repo.get_membership(db, target_user_id, group_id)
    if membership is None:
        raise GroupError(
            "El usuario no es miembro de este grupo",
            "NOT_GROUP_MEMBER",
            404,
        )

    temporary_password = secrets.token_urlsafe(16)
    password_hash = hash_password(temporary_password)

    update_password_hash(db, target_user_id, password_hash)
    revoke_all_refresh_tokens_for_user(db, target_user_id)

    log_action(
        db,
        actor_user_id=actor_user_id,
        group_id=group_id,
        action="user.password_reset",
        entity_type="User",
        entity_id=target_user_id,
        metadata=None,
    )
    db.commit()

    return {"user_id": target_user_id, "temporary_password": temporary_password}


# ---------------------------------------------------------------------------
# Invite codes
# ---------------------------------------------------------------------------

_INVITE_CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"
_CODE_LENGTH = 8
_MAX_RETRIES = 5


def _generate_unique_code(db: Session) -> str:
    """Generate a unique 8-char invite code from the ambiguity-free alphabet.

    Uses secrets.choice (not random) for cryptographic safety.
    Retries up to _MAX_RETRIES times on collision (extremely unlikely given
    32^8 ≈ 1.1 × 10^12 possible codes).
    """
    for _ in range(_MAX_RETRIES):
        code = "".join(secrets.choice(_INVITE_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
        existing = repo.get_active_invite_code_by_code(db, code)
        if existing is None:
            return code
    raise GroupError(
        "No se pudo generar un código único (esto no debería pasar)",
        "CODE_GENERATION_FAILED",
        500,
    )


def _is_code_valid(invite_code) -> bool:
    """Check if an invite code is still valid (not expired, not exhausted)."""
    now = datetime.now(timezone.utc)
    if invite_code.expires_at is not None and invite_code.expires_at <= now:
        return False
    return not (
        invite_code.max_uses is not None
        and invite_code.uses_count >= invite_code.max_uses
    )


def create_invite_code(
    db: Session,
    *,
    group_id: int,
    role_to_assign: str,
    max_uses: int | None,
    expires_at: datetime | None,
    created_by_user_id: int,
):
    """Create a new invite code for a group. Returns the GroupInviteCode."""
    code = _generate_unique_code(db)
    invite = repo.create_invite_code(
        db,
        group_id=group_id,
        code=code,
        role_to_assign=role_to_assign,
        created_by_user_id=created_by_user_id,
        max_uses=max_uses,
        expires_at=expires_at,
    )
    db.commit()
    db.refresh(invite)
    return invite


def list_invite_codes(db: Session, group_id: int) -> list:
    """Return all invite codes for a group."""
    return repo.list_invite_codes(db, group_id)


def revoke_invite_code(db: Session, *, id: int, group_id: int):
    """Revoke (deactivate) an invite code. Raises GroupError 404 if not found."""
    invite = repo.revoke_invite_code(db, id, group_id)
    if invite is None:
        raise GroupError(
            "Código de invitación no encontrado",
            "INVITE_CODE_NOT_FOUND",
            404,
        )
    db.commit()
    db.refresh(invite)
    return invite


def get_group_name_for_code(db: Session, code: str) -> str:
    """Validate a code and return the group name for the preview endpoint.

    Raises GroupError 404 INVALID_INVITE_CODE if code is invalid/expired/exhausted.
    """
    from app.groups.repository import get_group_by_id

    invite = repo.get_active_invite_code_by_code(db, code)
    if invite is None or not invite.is_active:
        raise GroupError(
            "Código de invitación inválido",
            "INVALID_INVITE_CODE",
            404,
        )
    if not _is_code_valid(invite):
        raise GroupError(
            "Código de invitación inválido",
            "INVALID_INVITE_CODE",
            404,
        )
    group = get_group_by_id(db, invite.group_id)
    return group.name


def join_group_by_code(db: Session, *, user_id: int, code: str) -> dict:
    """Join a user to a group via invite code.

    Returns {group_id, group_name, role}. Caller must commit.
    Raises GroupError on any validation failure.
    """
    from app.groups.repository import get_group_by_id

    invite = repo.get_active_invite_code_by_code(db, code)
    if invite is None or not invite.is_active:
        raise GroupError(
            "Código de invitación inválido",
            "INVALID_INVITE_CODE",
            404,
        )
    if not _is_code_valid(invite):
        raise GroupError(
            "Código de invitación inválido",
            "INVALID_INVITE_CODE",
            404,
        )

    existing = repo.get_membership(db, user_id, invite.group_id)
    if existing is not None:
        raise GroupError(
            "El usuario ya es miembro de este grupo",
            "ALREADY_MEMBER",
            409,
        )

    membership = repo.create_membership(
        db,
        user_id=user_id,
        group_id=invite.group_id,
        role=invite.role_to_assign,
    )
    membership.joined_via_invite_code_id = invite.id
    repo.increment_invite_code_uses(db, invite.id)
    log_action(
        db,
        actor_user_id=user_id,
        group_id=invite.group_id,
        action="membership.joined_via_code",
        entity_type="GroupMembership",
        entity_id=user_id,
        metadata={"invite_code_id": invite.id},
    )

    group = get_group_by_id(db, invite.group_id)
    return {
        "group_id": invite.group_id,
        "group_name": group.name,
        "role": invite.role_to_assign,
    }
