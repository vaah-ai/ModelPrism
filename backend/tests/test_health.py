"""Tests for the health check endpoint."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestHealthEndpoint:
    """Health check endpoint tests."""

    @pytest.mark.asyncio()
    async def test_health_returns_200(self, async_client: AsyncClient) -> None:
        """Health endpoint should always return 200 (even in degraded mode)."""
        response = await async_client.get("/api/health")
        assert response.status_code == 200

    @pytest.mark.asyncio()
    async def test_health_has_required_fields(self, async_client: AsyncClient) -> None:
        """Health response should contain all required fields."""
        response = await async_client.get("/api/health")
        data = response.json()
        assert "status" in data
        assert "database" in data
        assert "redis" in data
        assert "version" in data

    @pytest.mark.asyncio()
    async def test_health_database_status(self, async_client: AsyncClient) -> None:
        """Database status should be 'connected' or 'disconnected'."""
        response = await async_client.get("/api/health")
        data = response.json()
        assert data["database"] in ("connected", "disconnected")

    @pytest.mark.asyncio()
    async def test_health_redis_status(self, async_client: AsyncClient) -> None:
        """Redis status should be 'connected' or 'disconnected'."""
        response = await async_client.get("/api/health")
        data = response.json()
        assert data["redis"] in ("connected", "disconnected")

    @pytest.mark.asyncio()
    async def test_health_overall_status(self, async_client: AsyncClient) -> None:
        """Overall status should be 'ok' or 'degraded'."""
        response = await async_client.get("/api/health")
        data = response.json()
        assert data["status"] in ("ok", "degraded")

    @pytest.mark.asyncio()
    async def test_health_version_matches(self, async_client: AsyncClient) -> None:
        """Version should be a string."""
        response = await async_client.get("/api/health")
        data = response.json()
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0

    @pytest.mark.asyncio()
    async def test_metrics_endpoint(self, async_client: AsyncClient) -> None:
        """Prometheus metrics endpoint should return 200."""
        response = await async_client.get("/metrics/")
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")

    @pytest.mark.asyncio()
    async def test_root_not_found(self, async_client: AsyncClient) -> None:
        """Root endpoint should return 404 (no route registered)."""
        response = await async_client.get("/")
        assert response.status_code == 404
