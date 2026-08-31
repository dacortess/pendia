"""Business logic for categories."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.categories import repository as repo


class CategoryError(Exception):
    """Expected category business logic failure."""

    def __init__(self, detail: str, code: str, status_code: int):
        self.detail = detail
        self.code = code
        self.status_code = status_code


def list_categories(db: Session, group_id: int) -> list:
    """Return system + group categories."""
    return repo.list_categories_for_group(db, group_id)


def create_category(
    db: Session, *, group_id: int, name: str, icon: str | None
):
    """Create a custom category for a group. Raises CategoryError on duplicate."""
    existing = repo.get_category_by_name_in_group(db, group_id, name)
    if existing is not None:
        raise CategoryError(
            "Ya existe una categoría con ese nombre en este grupo",
            "CATEGORY_NAME_ALREADY_EXISTS",
            409,
        )

    category = repo.create_category(db, group_id=group_id, name=name, icon=icon)
    db.commit()
    db.refresh(category)
    return category
