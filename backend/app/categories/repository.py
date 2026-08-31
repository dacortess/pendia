"""Database queries for categories."""
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.categories.models import Category


def list_categories_for_group(db: Session, group_id: int) -> list[Category]:
    """Return system categories (group_id IS NULL) + custom categories for the group."""
    stmt = (
        select(Category)
        .where(
            or_(
                Category.group_id.is_(None),
                Category.group_id == group_id,
            )
        )
        .order_by(Category.group_id.nullsfirst(), Category.name)
    )
    return list(db.execute(stmt).scalars().all())


def create_category(
    db: Session, *, group_id: int, name: str, icon: str | None
) -> Category:
    """Insert a new custom category. Caller must commit."""
    category = Category(group_id=group_id, name=name, icon=icon)
    db.add(category)
    db.flush()
    return category


def get_category_by_name_in_group(
    db: Session, group_id: int, name: str
) -> Category | None:
    """Return a custom category with the given name in the group, or None."""
    return db.execute(
        select(Category).where(
            Category.group_id == group_id,
            Category.name == name,
        )
    ).scalar_one_or_none()
