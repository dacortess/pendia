"""Application configuration loaded from environment variables."""
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    # Database
    DATABASE_URL: str = Field(
        default="postgresql+psycopg://app:app_dev_only@localhost:5432/gestor_pagos",
        description="PostgreSQL connection URL",
    )
    
    # JWT
    JWT_SECRET: str = Field(
        default="change-me-to-a-random-256-bit-value",
        description="Secret key for JWT signing",
    )
    JWT_ACCESS_TOKEN_TTL_MINUTES: int = Field(
        default=15,
        description="Access token expiration in minutes",
    )
    REFRESH_TOKEN_TTL_DAYS: int = Field(
        default=30,
        description="Refresh token expiration in days",
    )
    
    # Security
    FRONTEND_ORIGIN: str = Field(
        default="https://gestor-pagos.pages.dev",
        description="Exact frontend origin for CORS",
    )
    
    # Argon2id
    ARGON2_TIME_COST: int = Field(
        default=3,
        description="Argon2 time cost",
    )
    ARGON2_MEMORY_COST_KB: int = Field(
        default=65536,
        description="Argon2 memory cost in KB",
    )
    ARGON2_PARALLELISM: int = Field(
        default=2,
        description="Argon2 parallelism",
    )
    
    # Environment
    ENVIRONMENT: str = Field(
        default="development",
        description="Environment: development, staging, production",
    )
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL."""
        if not v:
            raise ValueError("DATABASE_URL must be set")
        return v
    
    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Validate JWT secret length."""
        if len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return v


settings = Settings()