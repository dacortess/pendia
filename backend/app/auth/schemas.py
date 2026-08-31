"""Pydantic schemas for auth endpoints."""
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Request body for POST /auth/register."""
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)
    phone_number: str | None = None
    invite_code: str | None = None


class LoginRequest(BaseModel):
    """Request body for POST /auth/login."""
    email: EmailStr
    password: str


class AccessTokenResponse(BaseModel):
    """Response body for register/login/refresh — access token only, refresh goes in cookie."""
    access_token: str
    token_type: str = "bearer"
