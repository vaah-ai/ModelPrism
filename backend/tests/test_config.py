"""Tests for application configuration (config.py)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import PostgresDsn, RedisDsn, ValidationError

from app.config import Settings


class TestSettings:
    """Settings validation tests."""

    def test_valid_urls(self) -> None:
        """Valid environment should produce valid settings."""
        settings = Settings(
            database_url=PostgresDsn("postgresql+asyncpg://user:pass@localhost:5432/db"),
            redis_url=RedisDsn("redis://localhost:6379/0"),
            jwt_secret="a" * 16,
        )
        assert settings.database_pool_size == 20
        assert settings.database_max_overflow == 10
        assert settings.database_echo is False
        assert settings.jwt_algorithm == "HS256"
        assert settings.jwt_access_token_expire_hours == 24

    def test_custom_values(self) -> None:
        settings = Settings(
            database_url=PostgresDsn("postgresql+asyncpg://user:pass@localhost:5432/db"),
            redis_url=RedisDsn("redis://localhost:6379/0"),
            jwt_secret="a" * 16,
            cors_origins="http://localhost:3000,http://dashboard.example.com",
            cloud_mode=True,
            environment="production",
            database_pool_size=10,
            database_max_overflow=5,
        )
        assert settings.cloud_mode is True
        assert settings.environment == "production"
        assert settings.database_pool_size == 10
        assert settings.database_max_overflow == 5

    def test_defaults(self) -> None:
        settings = Settings(
            database_url=PostgresDsn("postgresql+asyncpg://user:pass@localhost:5432/db"),
            redis_url=RedisDsn("redis://localhost:6379/0"),
            jwt_secret="a" * 16,
        )
        assert settings.cloud_mode is False
        assert settings.version == "0.1.0"
        assert settings.environment == "development"

    def test_secret_too_short_raises(self) -> None:
        with pytest.raises(ValidationError, match="String should have at least 16 characters"):
            Settings(
                database_url=PostgresDsn("postgresql+asyncpg://user:pass@localhost:5432/db"),
                redis_url=RedisDsn("redis://localhost:6379/0"),
                jwt_secret="short",
            )

    def test_cors_origin_list(self) -> None:
        settings = Settings(
            database_url=PostgresDsn("postgresql+asyncpg://user:pass@localhost:5432/db"),
            redis_url=RedisDsn("redis://localhost:6379/0"),
            jwt_secret="a" * 16,
            cors_origins="http://a.com, http://b.com",
        )
        assert settings.cors_origin_list == ["http://a.com", "http://b.com"]

    def test_single_cors_origin(self) -> None:
        settings = Settings(
            database_url=PostgresDsn("postgresql+asyncpg://user:pass@localhost:5432/db"),
            redis_url=RedisDsn("redis://localhost:6379/0"),
            jwt_secret="a" * 16,
        )
        assert settings.cors_origin_list == ["http://localhost:3000"]

    def test_compose_all_settings_from_env(self, monkeypatch: Any) -> None:
        """Verify the settings loads from environment variables."""
        env_vars = {
            "DATABASE_URL": "postgresql+asyncpg://u:p@localhost:5432/db",
            "REDIS_URL": "redis://localhost:6379/0",
            "JWT_SECRET": "a" * 16,
        }
        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)

        settings = Settings()  # type: ignore[call-arg]
        assert settings.database_url is not None
        assert settings.redis_url is not None
        assert settings.jwt_secret == "a" * 16
        assert settings.cloud_mode is False
