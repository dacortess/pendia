"""Audit logging service — write-only, no HTTP endpoints."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.audit.models import AuditLog


def log_action(
    db: Session,
    *,
    actor_user_id: int | None,
    group_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int,
    metadata: dict | None = None,
) -> None:
    """Insert an audit log row. Caller must commit (this only flushes)."""
    entry = AuditLog(
        actor_user_id=actor_user_id,
        group_id=group_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        extra_metadata=metadata,
    )
    db.add(entry)
    db.flush()
