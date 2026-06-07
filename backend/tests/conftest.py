"""Pytest fixtures for backend tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import PostgresDsn, RedisDsn

from app.config import Settings
from app.database import get_db


@pytest.fixture()
def test_settings() -> Settings:
    """Return settings with test-friendly overrides."""
    return Settings(
        database_url=PostgresDsn("postgresql+asyncpg://test:test@localhost:5432/modelprism_test"),
        database_echo=False,
        redis_url=RedisDsn("redis://localhost:6379/1"),
        jwt_secret="test-secret-key-for-testing-only",
        cors_origins="http://localhost:3000",
        cloud_mode=False,
        debug=True,
        environment="test",
    )


@pytest_asyncio.fixture()
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client pointed at the FastAPI app.

    Note: This uses the app without DB/Redis connections. For full
    integration tests, use docker-compose and override the dependencies.
    """
    from app.main import app

    transport = ASGITransport(app=app)

    async def override_get_db() -> AsyncGenerator[Any, None]:
        """Override the DB dependency to yield nothing in test mode."""
        yield None

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
