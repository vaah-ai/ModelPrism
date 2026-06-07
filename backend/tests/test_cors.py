"""Tests for CORS middleware headers."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestCORS:
    """CORS middleware header tests."""

    @pytest.mark.asyncio()
    async def test_cors_allow_origin(self, async_client: AsyncClient) -> None:
        """Response should include CORS allow-origin header."""
        response = await async_client.get(
            "/api/health",
            headers={"Origin": "http://localhost:3000"},
        )
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"

    @pytest.mark.asyncio()
    async def test_cors_allow_credentials(self, async_client: AsyncClient) -> None:
        """Response should include CORS allow-credentials header."""
        response = await async_client.get(
            "/api/health",
            headers={"Origin": "http://localhost:3000"},
        )
        assert response.headers.get("access-control-allow-credentials") == "true"

    @pytest.mark.asyncio()
    async def test_cors_allow_methods(self, async_client: AsyncClient) -> None:
        """Preflight request should return allowed methods."""
        response = await async_client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Starlette CORSMiddleware returns the explicit allowed methods list
        assert "GET" in response.headers.get("access-control-allow-methods", "")

    @pytest.mark.asyncio()
    async def test_cors_rejects_unknown_origin(self, async_client: AsyncClient) -> None:
        """Origin not in allow list should not receive allow-origin header."""
        response = await async_client.get(
            "/api/health",
            headers={"Origin": "http://evil.com"},
        )
        # When origin is not allowed, the header should not match the origin
        cors_header = response.headers.get("access-control-allow-origin")
        assert cors_header != "http://evil.com"

    @pytest.mark.asyncio()
    async def test_cors_correlation_id_header(self, async_client: AsyncClient) -> None:
        """Response should include X-Correlation-ID header."""
        response = await async_client.get("/api/health")
        assert "x-correlation-id" in response.headers
        assert len(response.headers["x-correlation-id"]) > 0

    @pytest.mark.asyncio()
    async def test_cors_correlation_id_passthrough(self, async_client: AsyncClient) -> None:
        """Client-provided X-Correlation-ID should be echoed back."""
        response = await async_client.get(
            "/api/health",
            headers={"X-Correlation-ID": "my-test-id-123"},
        )
        assert response.headers.get("x-correlation-id") == "my-test-id-123"
