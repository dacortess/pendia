"""Pydantic schemas for user responses."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    """Public user profile — never exposes password_hash."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    phone_number: str | None
    whatsapp_opt_in: bool
    created_at: datetime
