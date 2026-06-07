"""Application configuration via pydantic-settings.

Settings are loaded from environment variables and/or a .env file.
Env var names are uppercase versions of field names.
"""

from __future__ import annotations

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file.

    All required fields must be set before the application starts.
    Use the module-level ``settings`` singleton for imports.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Database ---
    database_url: PostgresDsn = Field(
        ...,
        description="PostgreSQL connection URL (asyncpg driver)",
    )
    database_pool_size: int = Field(
        default=20,
        description="SQLAlchemy connection pool size",
    )
    database_max_overflow: int = Field(
        default=10,
        description="Maximum overflow connections beyond pool_size",
    )
    database_echo: bool = Field(
        default=False,
        description="Echo SQL queries (development only)",
    )

    # --- Redis ---
    redis_url: RedisDsn = Field(
        ...,
        description="Redis connection URL",
    )

    # --- Authentication ---
    jwt_secret: str = Field(
        ...,
        description="JWT signing secret key (required, min 16 chars)",
        min_length=16,
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm",
    )
    jwt_access_token_expire_hours: int = Field(
        default=24,
        description="JWT access token expiration in hours",
    )

    # --- Application ---
    cors_origins: str = Field(
        default="http://localhost:3000",
        description="Comma-separated CORS allowed origins",
    )
    cloud_mode: bool = Field(
        default=False,
        description="Enable ModelPrism Cloud features (billing, multi-tenant)",
    )
    version: str = Field(
        default="0.1.0",
        description="Application version",
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode",
    )
    environment: str = Field(
        default="development",
        description="Runtime environment: development, staging, production",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse CORS_ORIGINS comma-separated string into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


# Singleton instance — import this everywhere
settings = Settings()  # type: ignore[call-arg]
