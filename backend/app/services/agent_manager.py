"""Agent management service — business logic for agent registration and connection management.

Provides the core operations for the two-phase agent registration flow
and the ``AgentConnectionRegistry`` for tracking active WebSocket
connections.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.agent import Agent
from app.models.agent_token import AgentToken
from app.models.enums import AgentStatus, TokenStatus
from app.utils.crypto import generate_agent_id, generate_token, get_token_prefix, hash_token
from app.utils.naming import generate_unique_name

if TYPE_CHECKING:
    from uuid import UUID

    from app.schemas.ws_messages import CommandMessage

logger = logging.getLogger(__name__)


async def create_registration_token(db: AsyncSession) -> dict[str, object]:
    """Generate a new agent registration token.

    Args:
        db: An active SQLAlchemy async session.

    Returns:
        A dict with the raw token, prefix, and expiry timestamp.
    """
    raw_token = generate_token()
    token_hash = hash_token(raw_token)
    prefix = get_token_prefix(raw_token)
    expires_at = datetime.now(UTC) + timedelta(hours=settings.agent_token_expire_hours)

    db_token = AgentToken(
        token_hash=token_hash,
        prefix=prefix,
        status=TokenStatus.PENDING,
        expires_at=expires_at,
    )
    db.add(db_token)
    await db.flush()

    logger.info(
        "Created registration token: prefix=%s expires_at=%s",
        prefix,
        expires_at.isoformat(),
    )

    return {
        "token": raw_token,
        "prefix": prefix,
        "expires_at": expires_at,
    }


async def claim_agent(
    db: AsyncSession,
    token_str: str,
    hostname: str,
) -> dict[str, object]:
    """Phase 1 of two-phase registration: claim an agent with a token.

    Validates the token, generates a unique friendly name, creates an
    ``Agent`` record in ``OFFLINE`` status, and marks the token as
    ``CLAIMED``.

    Args:
        db: An active SQLAlchemy async session.
        token_str: The raw registration token string.
        hostname: The server hostname reported by the agent.

    Returns:
        A dict with the agent id, friendly name, and a placeholder
        WebSocket URL.

    Raises:
        HTTPException 401: If the token is invalid or expired.
        HTTPException 409: If the token has already been claimed.
    """
    token_hash = hash_token(token_str)

    result = await db.execute(select(AgentToken).where(AgentToken.token_hash == token_hash))
    db_token: AgentToken | None = result.scalar_one_or_none()

    if db_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid registration token",
        )

    if db_token.status != TokenStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Registration token has already been used",
        )

    now = datetime.now(UTC)
    if now > db_token.expires_at:
        db_token.status = TokenStatus.EXPIRED
        await db.flush()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Registration token has expired",
        )

    # Generate a unique friendly name
    friendly_name = await generate_unique_name(db)

    # Create the agent record
    agent = Agent(
        name=friendly_name,
        hostname=hostname,
        status=AgentStatus.OFFLINE,
    )
    db.add(agent)
    await db.flush()  # Flush to get agent.id

    # Link the token to the agent
    db_token.agent_id = agent.id
    db_token.status = TokenStatus.CLAIMED

    # Record the claim timestamp on the agent's updated_at
    agent.updated_at = now

    await db.flush()

    logger.info(
        "Agent claimed: id=%s name=%s hostname=%s",
        agent.id,
        agent.name,
        agent.hostname,
    )

    # Construct WebSocket URL with the human-friendly agent ID
    agent_id_str = generate_agent_id(agent.id)
    ws_url = f"ws://localhost:8000/ws/agents/{agent_id_str}"

    return {
        "agent_id": agent_id_str,
        "name": agent.name,
        "ws_url": ws_url,
    }


async def complete_registration(
    db: AsyncSession,
    agent_id: UUID,
    hardware: dict[str, object],
) -> Agent:
    """Phase 2 of two-phase registration: complete agent registration.

    Updates the agent with full hardware specifications and sets the
    status to ``ONLINE``.  Must be called within the claim timeout
    window (default 5 minutes).

    Args:
        db: An active SQLAlchemy async session.
        agent_id: The UUID of the claimed agent.
        hardware: A dict containing hardware info with keys:
            ``gpus``, ``cpu``, ``disk``, ``os``, ``kernel``,
            ``agent_version``.

    Returns:
        The updated ``Agent`` ORM instance.

    Raises:
        HTTPException 404: If the agent is not found.
        HTTPException 400: If the claim timeout has elapsed.
    """
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent: Agent | None = result.scalar_one_or_none()

    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    # Check agent is in OFFLINE/pending state
    if agent.status != AgentStatus.OFFLINE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Agent is already registered",
        )

    # Check claim timeout
    now = datetime.now(UTC)
    claim_deadline = agent.updated_at + timedelta(minutes=settings.agent_claim_timeout_minutes)
    if now > claim_deadline:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration claim timeout — please start over with a new token",
        )

    # Update hardware information
    # gpu_info/cpu_info/disk_info are JSONB columns accepting any JSON
    agent.gpu_info = _ensure_json_value(hardware.get("gpus"))  # type: ignore[assignment]
    agent.cpu_info = _ensure_json_value(hardware.get("cpu"))  # type: ignore[assignment]
    agent.disk_info = _ensure_json_value(hardware.get("disk"))  # type: ignore[assignment]
    agent.os_info = _ensure_str(hardware.get("os"))
    agent.agent_version = _ensure_str(hardware.get("agent_version"))
    if hardware.get("vllm_version"):
        agent.vllm_version = _ensure_str(hardware.get("vllm_version"))
    agent.status = AgentStatus.ONLINE
    agent.last_seen_at = now
    agent.updated_at = now

    await db.flush()

    logger.info(
        "Agent registration completed: id=%s name=%s hostname=%s",
        agent.id,
        agent.name,
        agent.hostname,
    )

    return agent


async def complete_registration_v2(
    db: AsyncSession,
    agent_id: UUID,
    hardware: dict[str, object],
) -> dict[str, object]:
    """Phase 2 helper that returns a dict instead of an ORM object.

    This is the public-facing version used by the API handler.
    It calls :func:`complete_registration` and enriches the return
    value with the WebSocket URL and polling config.

    Args:
        db: An active SQLAlchemy async session.
        agent_id: The UUID of the claimed agent.
        hardware: Full hardware info dict.

    Returns:
        A dict with agent_id, name, ws_url, and config.
    """
    agent = await complete_registration(db, agent_id, hardware)
    agent_id_str = generate_agent_id(agent.id)
    return {
        "agent_id": agent_id_str,
        "name": agent.name,
        "ws_url": _build_ws_url(agent_id_str),
        "config": {
            "poll_interval_seconds": 2,
            "heartbeat_interval_seconds": 15,
        },
    }


async def get_agent(db: AsyncSession, agent_id: UUID) -> Agent | None:
    """Look up a single agent by its UUID.

    Args:
        db: An active SQLAlchemy async session.
        agent_id: The agent UUID.

    Returns:
        The ``Agent`` instance, or ``None`` if not found.
    """
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    return result.scalar_one_or_none()


async def list_agents(db: AsyncSession) -> list[Agent]:
    """Return all registered agents, ordered by creation time descending.

    Args:
        db: An active SQLAlchemy async session.

    Returns:
        A list of ``Agent`` instances.
    """
    result = await db.execute(select(Agent).order_by(Agent.created_at.desc()))
    return list(result.scalars().all())


def _build_ws_url(agent_id_str: str) -> str:
    """Build the WebSocket URL for an agent.

    For MVP this returns a localhost URL.  In production this should be
    built from the request's host header or a configured external URL.
    """
    return f"ws://localhost:8000/ws/agents/{agent_id_str}"


def _ensure_json_value(
    value: object,
) -> dict[str, object] | list[object] | str | int | float | bool | None:
    """Coerce a value to a JSONB-compatible type.

    JSONB columns accept dicts, lists, scalar values, and None.
    This helper ensures structured data (like GPU lists) pass through
    without being mangled into a string.
    """
    if value is None:
        return None
    if isinstance(value, (dict, list, str, int, float, bool)):
        return value
    return str(value)


def _ensure_str(value: object) -> str | None:
    """Coerce a value to a string, returning None if it's not usable."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    if value is None:
        return None
    return str(value)


# ── Connection Registry ────────────────────────────────────────────


@dataclass
class PendingCommand:
    """A command sent to an agent that has not yet been completed."""

    command_id: str
    command: str
    sent_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class AgentConnectionRegistry:
    """Thread-safe registry of active agent WebSocket connections.

    Provides:
    - ``register`` — add or replace a connection (closes stale ones)
    - ``unregister`` — remove a connection and return its pending commands
    - ``send_command`` — deliver a command to a connected agent
    - ``broadcast_shutdown`` — notify all connected agents of server shutdown
    - ``get_active_ids`` — list all currently connected agent IDs
    - ``get_online_count`` — number of currently connected agents
    """

    def __init__(self) -> None:
        self._connections: dict[UUID, Any] = {}
        self._pending_commands: dict[UUID, dict[str, PendingCommand]] = {}
        self._lock = asyncio.Lock()

    async def register(self, agent_id: UUID, ws: Any) -> None:
        """Register (or replace) a WebSocket connection for an agent.

        If a connection already exists for this ``agent_id``, the old
        connection is force-closed with code 1008 ("Replaced by new
        connection") before accepting the new one.
        """
        async with self._lock:
            old_ws = self._connections.get(agent_id)
            if old_ws is not None:
                logger.warning("Replacing stale connection for agent %s", agent_id)
                try:
                    await old_ws.close(code=1008, reason="Replaced by new connection")
                except Exception:
                    logger.debug("Error closing stale connection for agent %s", agent_id)
            self._connections[agent_id] = ws
            self._pending_commands.setdefault(agent_id, {})

    async def unregister(self, agent_id: UUID) -> dict[str, PendingCommand]:
        """Remove a connection and return its pending commands.

        The pending commands are returned so the caller can mark them
        as failed (e.g. due to agent disconnect).
        """
        async with self._lock:
            self._connections.pop(agent_id, None)
            return self._pending_commands.pop(agent_id, {})

    async def send_command(
        self,
        agent_id: UUID,
        command: CommandMessage,
    ) -> bool:
        """Deliver a command to a connected agent over its WebSocket.

        Returns ``True`` if the agent was connected and the command was
        sent, ``False`` if the agent is not connected.

        The command is tracked as pending until a ``command_result`` is
        received.
        """
        async with self._lock:
            ws = self._connections.get(agent_id)
            if ws is None:
                return False
            self._pending_commands[agent_id][command.command_id] = PendingCommand(
                command_id=command.command_id,
                command=command.command,
            )
            await ws.send_json(command.model_dump())
            return True

    async def resolve_command(
        self,
        agent_id: UUID,
        command_id: str,
    ) -> PendingCommand | None:
        """Mark a command as resolved (completed) and return it.

        Returns the ``PendingCommand`` if it was tracked, or ``None``
        if the command_id was unknown (e.g. duplicate response).
        """
        async with self._lock:
            pending = self._pending_commands.get(agent_id)
            if pending is None:
                return None
            return pending.pop(command_id, None)

    async def broadcast_shutdown(self, reconnect_delay_seconds: int = 10) -> int:
        """Send a shutdown message to every connected agent.

        Returns the number of agents that were notified.
        """

        from app.schemas.ws_messages import ShutdownMessage

        shutdown = ShutdownMessage(reconnect_delay_seconds=reconnect_delay_seconds)
        payload = shutdown.model_dump_json()
        count = 0
        async with self._lock:
            for agent_id, ws in list(self._connections.items()):
                try:
                    await ws.send_text(payload)
                    count += 1
                except Exception:
                    logger.warning("Failed to send shutdown to agent %s", agent_id)
        return count

    async def get_active_ids(self) -> list[UUID]:
        """Return the list of currently connected agent UUIDs."""
        async with self._lock:
            return list(self._connections.keys())

    async def get_online_count(self) -> int:
        """Return the number of currently connected agents."""
        async with self._lock:
            return len(self._connections)


# Singleton — import this everywhere
agent_registry = AgentConnectionRegistry()
