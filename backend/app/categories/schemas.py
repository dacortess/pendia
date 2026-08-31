"""Pydantic schemas for category endpoints."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CategoryCreate(BaseModel):
    """Request body for POST /groups/{group_id}/categories."""
    name: str = Field(min_length=1, max_length=100)
    icon: str | None = None


class CategoryResponse(BaseModel):
    """Category detail."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_id: int | None
    name: str
    icon: str | None
    is_system: bool
    created_at: datetime
