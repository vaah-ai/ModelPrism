"""Integration tests for agent registration API endpoints.

Tests use FastAPI TestClient with dependency overrides for the
database session.  Full integration tests (real PostgreSQL + Redis)
are deferred to the ``test_integration.py`` module.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from app.models.agent import Agent
from app.models.agent_token import AgentToken
from app.models.enums import AgentStatus, TokenStatus
from app.utils.crypto import hash_token

# A valid-length token (43 chars + "mp_" = 46 total, passes min_length=32)
VALID_TOKEN = "mp_" + "a" * 43


@pytest.fixture(autouse=True)
def _clean_dependency_overrides() -> None:
    """Ensure dependency overrides are cleared between tests."""
    app.dependency_overrides.clear()


@pytest.fixture()
def mock_db() -> AsyncMock:
    """Create a mock database session for testing."""
    return AsyncMock()


@pytest.fixture()
def client(mock_db: AsyncMock) -> AsyncClient:
    """Create an async HTTP client with the DB dependency overridden."""

    async def override_get_db() -> AsyncMock:  # type: ignore[misc]
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# POST /api/agents/tokens
# ---------------------------------------------------------------------------


class TestCreateToken:
    """Tests for the token generation endpoint."""

    @pytest.mark.asyncio
    async def test_creates_token(self, client: AsyncClient, mock_db: AsyncMock) -> None:
        mock_db.flush = AsyncMock()

        response = await client.post("/api/agents/tokens")

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["token"].startswith("mp_")
        assert len(data["prefix"]) == 8
        assert "expires_at" in data
        assert mock_db.add.called

    @pytest.mark.asyncio
    async def test_adds_agent_token(self, client: AsyncClient, mock_db: AsyncMock) -> None:
        mock_db.flush = AsyncMock()

        response = await client.post("/api/agents/tokens")

        assert response.status_code == status.HTTP_201_CREATED
        added = mock_db.add.call_args[0][0]
        assert isinstance(added, AgentToken)
        assert added.status == TokenStatus.PENDING
        assert added.expires_at > datetime.now(UTC)


# ---------------------------------------------------------------------------
# POST /api/agents/register (claim phase)
# ---------------------------------------------------------------------------


def _make_token_mock(status: TokenStatus = TokenStatus.PENDING) -> AsyncMock:
    """Create a mocked AgentToken with sensible defaults."""
    token = AsyncMock(spec=AgentToken)
    token.token_hash = hash_token(VALID_TOKEN)
    token.prefix = "mp_aaaaa"
    token.status = status
    token.expires_at = datetime.now(UTC) + timedelta(hours=24)
    token.agent_id = None
    return token


class TestClaimAgent:
    """Tests for the agent claim (phase 1) endpoint."""

    @pytest.mark.asyncio
    async def test_claim_with_valid_token(self, client: AsyncClient, mock_db: AsyncMock) -> None:
        """Token found, name unique → 201."""
        mock_token = _make_token_mock()

        # First call: token lookup returns mock_token
        # Subsequent calls: name uniqueness checks return None (name available)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.side_effect = [mock_token] + [None] * 21
        mock_db.execute.return_value = mock_result
        mock_db.flush = AsyncMock()

        response = await client.post(
            "/api/agents/register",
            json={"token": VALID_TOKEN, "hostname": "gpu-node-1"},
        )

        assert response.status_code == status.HTTP_201_CREATED

    @pytest.mark.asyncio
    async def test_claim_invalid_token(self, client: AsyncClient, mock_db: AsyncMock) -> None:
        """Token not found in DB → 401."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        response = await client.post(
            "/api/agents/register",
            json={"token": VALID_TOKEN, "hostname": "gpu-node-1"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_claim_expired_token(self, client: AsyncClient, mock_db: AsyncMock) -> None:
        """Token found but already expired → 401."""
        mock_token = _make_token_mock()
        mock_token.expires_at = datetime.now(UTC) - timedelta(hours=1)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_token
        mock_db.execute.return_value = mock_result

        response = await client.post(
            "/api/agents/register",
            json={"token": VALID_TOKEN, "hostname": "gpu-node-1"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        # Error format: {"error": {"code": ..., "message": ...}}
        error_msg = data.get("error", data).get(
            "detail", data.get("error", {}).get("message", str(data))
        )
        assert "expired" in str(error_msg).lower()

    @pytest.mark.asyncio
    async def test_claim_already_used_token(self, client: AsyncClient, mock_db: AsyncMock) -> None:
        """Token found but already claimed → 409."""
        mock_token = _make_token_mock(status=TokenStatus.CLAIMED)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_token
        mock_db.execute.return_value = mock_result

        response = await client.post(
            "/api/agents/register",
            json={"token": VALID_TOKEN, "hostname": "gpu-node-1"},
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        data = response.json()
        error_msg = data.get("error", data).get(
            "detail", data.get("error", {}).get("message", str(data))
        )
        assert "already" in str(error_msg).lower()

    @pytest.mark.asyncio
    async def test_claim_with_short_token(self, client: AsyncClient, mock_db: AsyncMock) -> None:
        """Token shorter than 32 chars → 422 validation error."""
        response = await client.post(
            "/api/agents/register",
            json={"token": "too-short", "hostname": "gpu-node-1"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ---------------------------------------------------------------------------
# GET /api/agents (list)
# ---------------------------------------------------------------------------


class TestListAgents:
    """Tests for the agent list endpoint."""

    @pytest.mark.asyncio
    async def test_list_empty(self, client: AsyncClient, mock_db: AsyncMock) -> None:
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        response = await client.get("/api/agents")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"] == []
        assert data["meta"]["total"] == 0

    @pytest.mark.asyncio
    async def test_list_with_agents(self, client: AsyncClient, mock_db: AsyncMock) -> None:
        agent = Agent(
            name="cyan-koala-42",
            hostname="gpu-node-1",
            status=AgentStatus.ONLINE,
        )
        agent.id = UUID("00000000-0000-0000-0000-000000000001")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [agent]
        mock_db.execute.return_value = mock_result

        response = await client.get("/api/agents")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["data"]) == 1
        resource = data["data"][0]
        assert resource["type"] == "agent"
        assert resource["id"]
        assert resource["attributes"]["name"] == "cyan-koala-42"
        assert resource["attributes"]["hostname"] == "gpu-node-1"
        assert resource["attributes"]["status"] == "online"


# ---------------------------------------------------------------------------
# GET /api/agents/{id} (detail)
# ---------------------------------------------------------------------------


class TestGetAgent:
    """Tests for the single agent detail endpoint."""

    @pytest.mark.asyncio
    async def test_get_existing_agent(self, client: AsyncClient, mock_db: AsyncMock) -> None:
        agent = Agent(
            name="cyan-koala-42",
            hostname="gpu-node-1",
            status=AgentStatus.ONLINE,
        )
        agent.id = UUID("00000000-0000-0000-0000-000000000001")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = agent
        mock_db.execute.return_value = mock_result

        response = await client.get("/api/agents/00000000-0000-0000-0000-000000000001")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        resource = data["data"]
        assert resource["type"] == "agent"
        assert resource["attributes"]["name"] == "cyan-koala-42"
        assert resource["attributes"]["hostname"] == "gpu-node-1"

    @pytest.mark.asyncio
    async def test_get_nonexistent_agent(self, client: AsyncClient, mock_db: AsyncMock) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        response = await client.get("/api/agents/00000000-0000-0000-0000-000000000099")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_with_invalid_uuid(self, client: AsyncClient, mock_db: AsyncMock) -> None:
        response = await client.get("/api/agents/not-a-uuid")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ---------------------------------------------------------------------------
# PUT /api/agents/{id}/register (complete phase)
# ---------------------------------------------------------------------------


class TestCompleteRegistration:
    """Tests for the registration completion (phase 2) endpoint."""

    AGENT_ID = "00000000-0000-0000-0000-000000000001"

    @pytest.mark.asyncio
    async def test_complete_with_hardware(self, client: AsyncClient, mock_db: AsyncMock) -> None:
        now = datetime.now(UTC)
        agent = Agent(
            name="cyan-koala-42",
            hostname="gpu-node-1",
            status=AgentStatus.OFFLINE,
            updated_at=now,
        )
        agent.id = UUID(self.AGENT_ID)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = agent
        mock_db.execute.return_value = mock_result
        mock_db.flush = AsyncMock()

        response = await client.put(
            f"/api/agents/{self.AGENT_ID}/register",
            json={
                "gpus": [
                    {
                        "name": "NVIDIA A100-SXM4-80GB",
                        "memory_total_mb": 81200,
                        "driver_version": "550.54.15",
                        "cuda_version": "12.4",
                    }
                ],
                "cpu": {
                    "model": "AMD EPYC 7V12 64-Core",
                    "cores": 64,
                    "total_memory_gb": 512,
                },
                "disk": {
                    "total_gb": 2048,
                    "available_gb": 1500,
                },
                "os": "Ubuntu 22.04",
                "kernel": "5.15.0-generic",
                "agent_version": "0.1.0",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["agent_id"]
        assert data["name"] == "cyan-koala-42"
        assert data["ws_url"]
        assert "config" in data
        assert data["config"]["poll_interval_seconds"] == 2
        assert data["config"]["heartbeat_interval_seconds"] == 15

    @pytest.mark.asyncio
    async def test_complete_claim_timeout(self, client: AsyncClient, mock_db: AsyncMock) -> None:
        old_time = datetime.now(UTC) - timedelta(minutes=10)
        agent = Agent(
            name="cyan-koala-42",
            hostname="gpu-node-1",
            status=AgentStatus.OFFLINE,
            updated_at=old_time,
        )
        agent.id = UUID(self.AGENT_ID)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = agent
        mock_db.execute.return_value = mock_result

        response = await client.put(
            f"/api/agents/{self.AGENT_ID}/register",
            json={"os": "Ubuntu 22.04"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        error_msg = data.get("error", data).get(
            "detail", data.get("error", {}).get("message", str(data))
        )
        assert "timeout" in str(error_msg).lower()

    @pytest.mark.asyncio
    async def test_complete_nonexistent_agent(
        self, client: AsyncClient, mock_db: AsyncMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        response = await client.put(
            f"/api/agents/{self.AGENT_ID}/register",
            json={"os": "Ubuntu 22.04"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
