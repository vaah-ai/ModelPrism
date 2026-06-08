"""Dashboard WebSocket handler — real-time metric broadcast to browsers.

Agents push metrics to Redis ``metrics:{agent_id}`` and ``vllm_metrics:{agent_id}``
channels via the agent WebSocket handler (``agent_ws.py``).  This module provides
two dashboard-facing WebSocket endpoints that subscribe to those channels and
forward transformed metrics to connected browser clients.

Endpoints
---------
- ``/ws/dashboard/{agent_id}`` — real-time metrics for a specific GPU server
- ``/ws/dashboard`` — aggregate metrics for all registered agents
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.redis import redis_client
from app.utils.metric_helpers import avg_gpu_field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard_ws"])

# ── Metric Transformation ──────────────────────────────────────────


def _transform_metrics(
    raw: dict[str, Any],
    agent_id: str,
) -> dict[str, Any] | None:
    """Transform a raw agent metric snapshot into the dashboard format.

    The agent WebSocket handler publishes the raw, nested format
    (``gpu: [{util_pct, mem_used_mb, ...}]``).  This function computes
    GPU-level averages and flattens the payload for the dashboard
    composable (``useWebSocketMetrics.ts``).

    Parameters
    ----------
    raw:
        The raw metric payload as published to Redis.
    agent_id:
        The agent identifier to inject into the forwarded message.

    Returns
    -------
    The transformed payload, or ``None`` if the payload cannot be parsed.
    """
    ts_raw = raw.get("ts")
    if ts_raw is None:
        return None

    # Convert Unix timestamp to ISO 8601
    if isinstance(ts_raw, (int, float)):
        ts_iso = datetime.fromtimestamp(ts_raw, tz=UTC).isoformat()
    else:
        ts_iso = str(ts_raw)

    gpus = raw.get("gpu", [])
    avg_util_pct = avg_gpu_field(gpus, "util_pct")
    avg_mem_used = avg_gpu_field(gpus, "mem_used_mb")

    return {
        "type": "metrics",
        "agent_id": agent_id,
        "ts": ts_iso,
        "gpu_util_avg_pct": avg_util_pct,
        "gpu_memory_used_mb": avg_mem_used,
        "ram_used_gb": raw.get("ram_used_gb"),
        "ram_total_gb": raw.get("ram_total_gb"),
        "cpu_pct": raw.get("cpu_pct"),
        "load_1": raw.get("load_1"),
        "load_5": raw.get("load_5"),
        "load_15": raw.get("load_15"),
        "disk_used_gb": raw.get("disk_used_gb"),
        "disk_total_gb": raw.get("disk_total_gb"),
        "disk_pct": raw.get("disk_pct"),
        "gpu_cache_pct": raw.get("gpu_cache_pct"),
    }


# ── Per-Agent Endpoint ─────────────────────────────────────────────


@router.websocket("/ws/dashboard/{agent_id}")
async def dashboard_ws_agent(websocket: WebSocket, agent_id: UUID) -> None:
    """Real-time metrics for a specific GPU server.

    Subscribes to the ``metrics:{agent_id}`` Redis channel and forwards
    transformed metric snapshots to the dashboard client.
    """
    await websocket.accept()
    logger.info("Dashboard WS connected for agent %s", agent_id)

    channel = f"metrics:{agent_id}"
    pubsub = None

    try:
        if redis_client is not None:
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(channel)
        else:
            logger.warning(
                "Redis unavailable — dashboard WS for agent %s will not receive data",
                agent_id,
            )

        async def redis_reader() -> None:
            """Read from Redis pub/sub and forward transformed metrics."""
            if pubsub is None:
                # Sleep forever so the other task (client_reader) stays alive
                await asyncio.get_running_loop().create_future()
                return

            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                raw_data = message.get("data")
                if isinstance(raw_data, bytes):
                    raw_data = raw_data.decode("utf-8")
                if not isinstance(raw_data, str):
                    continue

                try:
                    payload = json.loads(raw_data)
                except json.JSONDecodeError:
                    continue

                transformed = _transform_metrics(payload, str(agent_id))
                if transformed is not None:
                    try:
                        await websocket.send_json(transformed)
                    except Exception:
                        break  # Connection likely closed

        async def client_reader() -> None:
            """Read messages from the dashboard client (pings, replay requests)."""
            try:
                async for raw in websocket.iter_json():
                    msg_type = raw.get("type")
                    if msg_type == "ping":
                        await websocket.send_json({"type": "pong"})
                    elif msg_type == "replay_request":
                        # MVP: no replay buffer — return empty batch
                        await websocket.send_json(
                            {
                                "type": "replay_batch",
                                "entries": [],
                                "count": 0,
                            }
                        )
            except WebSocketDisconnect:
                pass

        await asyncio.wait(
            [
                asyncio.create_task(redis_reader()),
                asyncio.create_task(client_reader()),
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )

    except WebSocketDisconnect:
        logger.info("Dashboard WS disconnected for agent %s", agent_id)
    except Exception:
        logger.exception("Unexpected error in dashboard WS for agent %s", agent_id)
    finally:
        if pubsub is not None:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.aclose()  # type: ignore[no-untyped-call]
            except Exception:
                logger.debug("Error cleaning up pubsub for agent %s", agent_id)


# ── Aggregate (All Agents) Endpoint ────────────────────────────────


@router.websocket("/ws/dashboard")
async def dashboard_ws_all(websocket: WebSocket) -> None:
    """Aggregate metrics for all registered agents.

    Uses Redis ``PSUBSCRIBE`` to listen on the ``metrics:*`` pattern and
    forwards transformed snapshots for *every* agent to the connected
    dashboard client.
    """
    await websocket.accept()
    logger.info("Dashboard WS connected (all agents)")

    pubsub = None

    try:
        if redis_client is not None:
            pubsub = redis_client.pubsub()
            await pubsub.psubscribe("metrics:*")
        else:
            logger.warning("Redis unavailable — dashboard WS (all) will not receive data")

        async def redis_reader() -> None:
            """Read from Redis pub/sub and forward transformed metrics."""
            if pubsub is None:
                await asyncio.get_running_loop().create_future()
                return

            async for message in pubsub.listen():
                if message["type"] != "pmessage":
                    continue

                channel: str = message["channel"]
                agent_id = channel.split(":", 1)[1] if ":" in channel else "unknown"

                raw_data = message.get("data")
                if isinstance(raw_data, bytes):
                    raw_data = raw_data.decode("utf-8")
                if not isinstance(raw_data, str):
                    continue

                try:
                    payload = json.loads(raw_data)
                except json.JSONDecodeError:
                    continue

                transformed = _transform_metrics(payload, agent_id)
                if transformed is not None:
                    try:
                        await websocket.send_json(transformed)
                    except Exception:
                        break

        async def client_reader() -> None:
            """Read messages from the dashboard client."""
            try:
                async for raw in websocket.iter_json():
                    msg_type = raw.get("type")
                    if msg_type == "ping":
                        await websocket.send_json({"type": "pong"})
                    elif msg_type == "replay_request":
                        await websocket.send_json(
                            {
                                "type": "replay_batch",
                                "entries": [],
                                "count": 0,
                            }
                        )
            except WebSocketDisconnect:
                pass

        await asyncio.wait(
            [
                asyncio.create_task(redis_reader()),
                asyncio.create_task(client_reader()),
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )

    except WebSocketDisconnect:
        logger.info("Dashboard WS disconnected (all agents)")
    except Exception:
        logger.exception("Unexpected error in dashboard WS (all agents)")
    finally:
        if pubsub is not None:
            try:
                await pubsub.punsubscribe()
                await pubsub.aclose()  # type: ignore[no-untyped-call]
            except Exception:
                logger.debug("Error cleaning up pubsub for all agents")
