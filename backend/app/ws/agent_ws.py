"""Agent WebSocket handler — persistent bidirectional connection.

Agents connect via ``/ws/agents/{agent_id}`` after completing the
two-phase registration flow.  The handler manages connection lifecycle
(connect, heartbeat, reconnect, disconnect) and routes typed messages:

- ``heartbeat`` → update ``last_seen_at`` in DB, check for queued commands
- ``metrics`` → validate, store latest in Redis, publish to ``metrics:{id}``
- ``vllm_metrics`` → same pattern, separate channel
- ``command_progress`` / ``command_result`` → store for dashboard retrieval
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionFactory
from app.models.agent import Agent
from app.models.enums import AgentStatus
from app.redis import redis_client
from app.schemas.ws_messages import (
    CommandMessage,
    parse_agent_message,
)
from app.services.agent_manager import agent_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents_ws"])

# Redis key prefixes
_REDIS_CONNECTED_KEY = "agent:{id}:ws_connected"
_REDIS_LATEST_METRICS_KEY = "agent:{id}:latest_metrics"
_REDIS_METRICS_CHANNEL = "metrics:{id}"
_REDIS_VLLM_CHANNEL = "vllm_metrics:{id}"
_REDIS_COMMANDS_KEY = "agent:{id}:commands"
_REDIS_RUNNING_INSTANCES_KEY = "agent:{id}:running_instances"

# Heartbeat tracking constants
_HEARTBEAT_TTL_SECONDS = 60  # Redis TTL for connected flag
_CLOCK_SKEW_WARNING_SECONDS = 300  # 5 minutes


async def _get_agent_by_id(
    db: AsyncSession,
    agent_id: UUID,
) -> Agent | None:
    """Fetch an agent record by UUID.

    This runs in a short-lived session created for each connection
    handshake (cannot use ``Depends(get_db)`` inside a WebSocket).
    """
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    return result.scalar_one_or_none()


async def _handle_heartbeat(
    agent_id: UUID,
    db: AsyncSession,
    ws: WebSocket,
    ts: float,
    agents_running: list[str],
) -> None:
    """Process a heartbeat message: update last_seen_at, send queued commands.

    The agent's ``last_seen_at`` is updated in the database.  If commands
    are queued in Redis for this agent, they are sent back through the
    WebSocket connection.

    Uses a simple ``SELECT`` without ``FOR UPDATE`` because heartbeat
    writes are best-effort — losing an occasional heartbeat update is
    acceptable, and holding a row lock across the WS connection would
    block concurrent admin operations.
    """
    now = datetime.now(UTC)
    try:
        result = await db.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()
        if agent is not None:
            agent.last_seen_at = now
            if agent.status != AgentStatus.ONLINE:
                agent.status = AgentStatus.ONLINE
            await db.flush()
            await db.commit()
    except Exception:
        logger.exception("Failed to update last_seen_at for agent %s", agent_id)

    # Check for queued commands in Redis
    if redis_client is not None:
        try:
            commands_raw = await redis_client.lrange(
                _REDIS_COMMANDS_KEY.format(id=agent_id),
                0,
                -1,
            )
            if commands_raw:
                for raw in commands_raw:
                    cmd_data = json.loads(raw) if isinstance(raw, bytes) else json.loads(raw)
                    cmd = CommandMessage(**cmd_data)
                    await ws.send_json(cmd.model_dump())
                    logger.info(
                        "Delivered command %s to agent %s",
                        cmd.command_id,
                        agent_id,
                    )
                # Clear delivered commands
                await redis_client.delete(_REDIS_COMMANDS_KEY.format(id=agent_id))
        except Exception:
            logger.exception("Failed to check/forward queued commands for agent %s", agent_id)

    # Renew the connected flag TTL
    await _set_connected_flag(agent_id)

    # Store running instances in Redis for dashboard queries
    if agents_running and redis_client is not None:
        try:
            await redis_client.setex(
                _REDIS_RUNNING_INSTANCES_KEY.format(id=agent_id),
                _HEARTBEAT_TTL_SECONDS * 2,
                json.dumps(agents_running),
            )
        except Exception:
            logger.debug("Failed to store running instances for agent %s", agent_id)


async def _set_connected_flag(agent_id: UUID) -> None:
    """Set the Redis connected flag with a TTL."""
    if redis_client is not None:
        try:
            await redis_client.setex(
                _REDIS_CONNECTED_KEY.format(id=agent_id),
                _HEARTBEAT_TTL_SECONDS,
                "1",
            )
        except Exception:
            logger.debug("Failed to set connected flag in Redis for agent %s", agent_id)


async def _handle_metrics(agent_id: UUID, data: dict[str, Any]) -> None:
    """Store the latest metrics in Redis and publish to the metrics channel."""
    if redis_client is None:
        return

    try:
        # Store latest metrics
        await redis_client.set(
            _REDIS_LATEST_METRICS_KEY.format(id=agent_id),
            json.dumps(data, default=str),
        )

        # Publish to the metrics channel for dashboard broadcast (F16)
        channel = _REDIS_METRICS_CHANNEL.format(id=agent_id)
        await redis_client.publish(channel, json.dumps(data, default=str))
    except Exception:
        logger.exception("Failed to store/publish metrics for agent %s", agent_id)


async def _handle_vllm_metrics(agent_id: UUID, data: dict[str, Any]) -> None:
    """Publish vLLM metrics to their own Redis channel."""
    if redis_client is None:
        return

    try:
        channel = _REDIS_VLLM_CHANNEL.format(id=agent_id)
        await redis_client.publish(channel, json.dumps(data, default=str))
    except Exception:
        logger.exception("Failed to publish vLLM metrics for agent %s", agent_id)


async def _handle_command_progress(agent_id: UUID, data: dict[str, Any]) -> None:
    """Store command progress in Redis for dashboard retrieval."""
    if redis_client is None:
        return

    try:
        command_id = data.get("command_id", "unknown")
        key = f"agent:{agent_id}:command_progress:{command_id}"
        await redis_client.setex(key, 3600, json.dumps(data, default=str))
    except Exception:
        logger.exception("Failed to store command progress for agent %s", agent_id)


async def _handle_command_result(
    agent_id: UUID,
    data: dict[str, Any],
) -> None:
    """Handle a terminal command result.

    Resolves the pending command in the registry and stores the result
    in Redis for dashboard retrieval.
    """
    command_id = data.get("command_id", "")

    # Resolve the pending command tracking
    await agent_registry.resolve_command(agent_id, command_id)

    if redis_client is None:
        return

    try:
        key = f"agent:{agent_id}:command_result:{command_id}"
        await redis_client.setex(key, 3600, json.dumps(data, default=str))
    except Exception:
        logger.exception("Failed to store command result for agent %s", agent_id)


def _check_clock_skew(agent_ts: float, agent_id: UUID) -> float:
    """Check for significant clock skew and return the effective timestamp."""
    now_ts = datetime.now(UTC).timestamp()
    diff = abs(now_ts - agent_ts)
    if diff > _CLOCK_SKEW_WARNING_SECONDS and agent_ts > 0:
        logger.warning(
            "Clock skew detected for agent %s: agent_ts=%s server_ts=%s diff=%.0fs",
            agent_id,
            agent_ts,
            now_ts,
            diff,
        )
        return now_ts
    return agent_ts


def _build_ws_error(message: str) -> str:
    """Build a JSON error response for WebSocket rejection."""
    return json.dumps({"error": "unauthorized", "detail": message})


# ── WebSocket Endpoint ─────────────────────────────────────────────


@router.websocket("/ws/agents/{agent_id}")
async def agent_websocket(ws: WebSocket, agent_id: UUID) -> None:
    """Agent WebSocket endpoint — persistent bidirectional channel.

    Steps:
    1. Accept the connection
    2. Validate that the agent exists in the database
    3. Register the connection (closes any stale connection)
    4. Enter receive loop — process typed messages
    5. On disconnect — clean up and mark agent offline
    """
    await ws.accept()
    logger.info("Agent %s WebSocket connection attempt", agent_id)

    # ── Create a short-lived DB session for this connection ──────
    session = AsyncSessionFactory()
    try:
        # Validate agent exists
        agent = await _get_agent_by_id(session, agent_id)
        if agent is None:
            logger.warning("WebSocket rejected: agent %s not found", agent_id)
            await ws.send_text(_build_ws_error("Agent not found"))
            await ws.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        logger.info(
            "Agent %s (%s) connecting via WebSocket",
            agent_id,
            agent.name,
        )

        # Register connection (will close stale connections)
        await agent_registry.register(agent_id, ws)

        # Set connected flag in Redis
        await _set_connected_flag(agent_id)

        # Update agent status to online
        try:
            agent.status = AgentStatus.ONLINE
            agent.last_seen_at = datetime.now(UTC)
            await session.flush()
            await session.commit()
        except Exception:
            logger.exception("Failed to update agent %s status to online", agent_id)
            await session.rollback()

        logger.info("Agent %s WebSocket connected", agent_id)

        # ── Receive loop ────────────────────────────────────────
        _reconnect_seen = False
        while True:
            raw = await ws.receive_text()

            # Handle connection management messages from FastAPI
            if raw == '{"type": "websocket.connect"}':
                continue

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON from agent %s: %s", agent_id, raw[:200])
                continue

            if not isinstance(data, dict):
                continue

            msg = parse_agent_message(data)
            if msg is None:
                continue

            # Route by type
            if msg.type == "heartbeat":
                await _handle_heartbeat(agent_id, session, ws, msg.ts, msg.agents_running)

            elif msg.type == "metrics":
                corrected_ts = _check_clock_skew(msg.ts, agent_id)
                if corrected_ts != msg.ts:
                    data["ts"] = corrected_ts
                await _handle_metrics(agent_id, data)

            elif msg.type == "vllm_metrics":
                corrected_ts = _check_clock_skew(msg.ts, agent_id)
                if corrected_ts != msg.ts:
                    data["ts"] = corrected_ts
                await _handle_vllm_metrics(agent_id, data)

            elif msg.type == "command_progress":
                await _handle_command_progress(agent_id, data)

            elif msg.type == "command_result":
                await _handle_command_result(agent_id, data)

    except WebSocketDisconnect:
        logger.info("Agent %s WebSocket disconnected", agent_id)
    except Exception:
        logger.exception("Unexpected error in agent %s WebSocket handler", agent_id)
    finally:
        # ── Cleanup ─────────────────────────────────────────────
        await _cleanup_agent_connection(agent_id, session)


async def _cleanup_agent_connection(agent_id: UUID, session: AsyncSession) -> None:
    """Clean up after an agent disconnects.

    1. Unregister from the connection registry (returning pending commands)
    2. Mark pending commands as failed
    3. Update agent status to offline in the database
    4. Clean up Redis keys
    """
    # 1 & 2: Unregister and fail pending commands
    pending = await agent_registry.unregister(agent_id)
    for cmd_id, cmd in pending.items():
        logger.info("Marking command %s for agent %s as failed (disconnected)", cmd_id, agent_id)
        if redis_client is not None:
            try:
                failed = {
                    "type": "command_result",
                    "command_id": cmd_id,
                    "status": "failed",
                    "error": "Agent disconnected before command completed",
                }
                key = f"agent:{agent_id}:command_result:{cmd_id}"
                await redis_client.setex(key, 3600, json.dumps(failed))
            except Exception:
                logger.debug("Failed to store command failure for %s", cmd_id)

    # 3: Update agent status to offline (no FOR UPDATE — best-effort cleanup)
    try:
        result = await session.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()
        if agent is not None and agent.status == AgentStatus.ONLINE:
            agent.status = AgentStatus.OFFLINE
            agent.last_seen_at = datetime.now(UTC)
            await session.flush()
            await session.commit()
            logger.info("Agent %s status set to offline", agent_id)
    except Exception:
        logger.exception("Failed to update agent %s status to offline", agent_id)
        await session.rollback()
    finally:
        await session.close()

    # 4: Clean up Redis keys
    if redis_client is not None:
        try:
            await redis_client.delete(_REDIS_CONNECTED_KEY.format(id=agent_id))
        except Exception:
            logger.debug("Failed to clean up Redis key for agent %s", agent_id)
