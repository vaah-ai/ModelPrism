"""Agent management service — business logic for agent registration.

Provides the core operations for the two-phase agent registration flow:
1. Create a registration token (dashboard/admin action)
2. Claim an agent (phase 1 — token + hostname)
3. Complete registration (phase 2 — hardware details)
4. List and get agents
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.agent import Agent
from app.models.agent_token import AgentToken
from app.models.enums import AgentStatus, TokenStatus
from app.utils.crypto import generate_token, get_token_prefix, hash_token
from app.utils.naming import generate_unique_name

if TYPE_CHECKING:
    from uuid import UUID

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

    # Construct WebSocket URL (placeholder — uses request host in practice)
    ws_url = f"ws://localhost:8000/ws/agents/{agent.id}"

    return {
        "agent_id": str(agent.id),
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
    return {
        "agent_id": str(agent.id),
        "name": agent.name,
        "ws_url": _build_ws_url(agent.id),
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


def _build_ws_url(agent_id: UUID) -> str:
    """Build the WebSocket URL for an agent.

    For MVP this returns a localhost URL.  In production this should be
    built from the request's host header or a configured external URL.
    """
    return f"ws://localhost:8000/ws/agents/{agent_id}"


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
