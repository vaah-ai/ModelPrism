"""Dashboard WebSocket handler — real-time metric broadcast to browsers.

Agents push metrics to Redis ``metrics:{agent_id}`` and ``vllm_metrics:{agent_id}``
channels via the agent WebSocket handler (``agent_ws.py``).  This module provides
two dashboard-facing WebSocket endpoints that subscribe to those channels and
forward transformed metrics to connected browser clients.

Endpoints
---------
- ``/ws/dashboard/{agent_id}`` — real-time metrics for a specific GPU server
- ``/ws/dashboard`` — aggregate metrics for all registered agents

Data flow
---------
::

    agent_ws.py (publishes) → Redis pub/sub → dashboard_ws.py (subscribes)
                                                ├── _transform_metrics()
                                                ├── _transform_vllm_metrics()
                                                └── _route_channel_message()
                                                → DashboardMetricsMessage (typed schema)
                                                → browser client
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.redis import redis_client
from app.schemas.dashboard_ws import DashboardMetricsMessage
from app.utils.metric_helpers import avg_gpu_field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard_ws"])

# Redis channel patterns
_METRICS_CHANNEL = "metrics:{id}"
_VLLM_METRICS_CHANNEL = "vllm_metrics:{id}"

# ── Metric Transformation ──────────────────────────────────────────


def _transform_metrics(
    raw: dict[str, Any],
    agent_id: str,
) -> DashboardMetricsMessage | None:
    """Transform a raw agent metric snapshot into a ``DashboardMetricsMessage``.

    The agent WebSocket handler publishes the raw, nested format
    (``gpu: [{util_pct, mem_used_mb, ...}]``).  This function computes
    GPU-level averages and flattens the payload for the dashboard
    composable (``useWebSocketMetrics.ts``).
    """
    ts_raw = raw.get("ts")
    if ts_raw is None:
        return None

    gpus = raw.get("gpu", [])
    avg_util_pct = avg_gpu_field(gpus, "util_pct")
    avg_mem_used = avg_gpu_field(gpus, "mem_used_mb")

    return DashboardMetricsMessage(
        agent_id=agent_id,
        ts_raw=ts_raw,
        gpu_util_avg_pct=avg_util_pct,
        gpu_memory_used_mb=avg_mem_used,
        gpu_cache_pct=raw.get("gpu_cache_pct"),
        ram_used_gb=raw.get("ram_used_gb"),
        ram_total_gb=raw.get("ram_total_gb"),
        cpu_pct=raw.get("cpu_pct"),
        load_1=raw.get("load_1"),
        load_5=raw.get("load_5"),
        load_15=raw.get("load_15"),
        disk_used_gb=raw.get("disk_used_gb"),
        disk_total_gb=raw.get("disk_total_gb"),
        disk_pct=raw.get("disk_pct"),
        # System metrics do not carry running/waiting — those come
        # from vLLM metrics via _transform_vllm_metrics.
    )


def _transform_vllm_metrics(
    raw: dict[str, Any],
    agent_id: str,
) -> DashboardMetricsMessage | None:
    """Transform a raw vLLM metric entry into a ``DashboardMetricsMessage``.

    vLLM metrics carry per-instance LLM telemetry (request counts,
    throughput, TTFT).  The frontend uses ``running`` / ``waiting``
    for request queue charts and ``running_models`` to indicate
    that at least one model is deployed.
    """
    ts_raw = raw.get("ts")
    if ts_raw is None:
        return None

    model_name = raw.get("model_name")

    return DashboardMetricsMessage(
        agent_id=agent_id,
        ts_raw=ts_raw,
        gpu_util_avg_pct=raw.get("gpu_cache_pct"),
        gpu_cache_pct=raw.get("gpu_cache_pct"),
        running_models=1 if model_name else 0,
        running=raw.get("running"),
        waiting=raw.get("waiting"),
    )


def _route_channel_message(
    channel: str,
    data: str,
    agent_id: str,
) -> DashboardMetricsMessage | None:
    """Parse a Redis channel message and dispatch to the correct transform.

    Inspects the channel prefix to determine whether the payload is a
    system metrics snapshot (``metrics:{id}``) or a vLLM metrics entry
    (``vllm_metrics:{id}``).
    """
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return None

    if channel.startswith("vllm_metrics:"):
        return _transform_vllm_metrics(payload, agent_id)
    return _transform_metrics(payload, agent_id)


# ── Shared Reader Helpers ──────────────────────────────────────────


async def _forward_pubsub_messages(
    pubsub: Any,  # redis.asyncio.client.PubSub
    websocket: WebSocket,
    is_pattern: bool,
) -> None:
    """Read from a Redis pub/sub connection and forward transformed messages.

    Parameters
    ----------
    pubsub:
        An already-subscribed Redis pub/sub instance.
    websocket:
        The dashboard WebSocket to forward to.
    is_pattern:
        ``True`` if using ``PSUBSCRIBE`` (messages have type ``pmessage``),
        ``False`` if using ``SUBSCRIBE`` (type ``message``).
    """
    expected_type = "pmessage" if is_pattern else "message"

    async for message in pubsub.listen():
        if message["type"] != expected_type:
            continue

        msg_channel: str = message["channel"]
        raw_data = message.get("data")
        if isinstance(raw_data, bytes):
            raw_data = raw_data.decode("utf-8")
        if not isinstance(raw_data, str):
            continue

        # Extract agent_id from the channel name
        # Channels: "metrics:{id}" or "vllm_metrics:{id}"
        agent_id = msg_channel.split(":", 1)[1] if ":" in msg_channel else "unknown"

        transformed = _route_channel_message(msg_channel, raw_data, agent_id)
        if transformed is not None:
            try:
                await websocket.send_json(transformed.to_dict())
            except Exception:
                break  # Connection likely closed


async def _client_reader(websocket: WebSocket) -> None:
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


# ── Per-Agent Endpoint ─────────────────────────────────────────────


@router.websocket("/ws/dashboard/{agent_id}")
async def dashboard_ws_agent(websocket: WebSocket, agent_id: UUID) -> None:
    """Real-time metrics for a specific GPU server.

    Subscribes to ``metrics:{agent_id}`` and ``vllm_metrics:{agent_id}``
    Redis channels and forwards ``DashboardMetricsMessage`` payloads to
    the dashboard client.
    """
    await websocket.accept()
    logger.info("Dashboard WS connected for agent %s", agent_id)

    sid = str(agent_id)
    channels = [
        _METRICS_CHANNEL.format(id=sid),
        _VLLM_METRICS_CHANNEL.format(id=sid),
    ]
    pubsub = None

    try:
        if redis_client is not None:
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(*channels)
        else:
            logger.warning(
                "Redis unavailable — dashboard WS for agent %s will not receive data",
                agent_id,
            )

        async def redis_reader() -> None:
            """Read from Redis pub/sub and forward transformed metrics."""
            if pubsub is None:
                await asyncio.get_running_loop().create_future()
                return

            await _forward_pubsub_messages(pubsub, websocket, is_pattern=False)

        await asyncio.wait(
            [
                asyncio.create_task(redis_reader()),
                asyncio.create_task(_client_reader(websocket)),
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
                await pubsub.unsubscribe(*channels)
                await pubsub.aclose()  # type: ignore[no-untyped-call]
            except Exception:
                logger.debug("Error cleaning up pubsub for agent %s", agent_id)


# ── Aggregate (All Agents) Endpoint ────────────────────────────────


@router.websocket("/ws/dashboard")
async def dashboard_ws_all(websocket: WebSocket) -> None:
    """Aggregate metrics for all registered agents.

    Uses Redis ``PSUBSCRIBE`` to listen on ``metrics:*`` and
    ``vllm_metrics:*`` patterns and forwards ``DashboardMetricsMessage``
    payloads for *every* agent to the connected dashboard client.
    """
    await websocket.accept()
    logger.info("Dashboard WS connected (all agents)")

    pubsub = None

    try:
        if redis_client is not None:
            pubsub = redis_client.pubsub()
            await pubsub.psubscribe("metrics:*", "vllm_metrics:*")
        else:
            logger.warning("Redis unavailable — dashboard WS (all) will not receive data")

        async def redis_reader() -> None:
            """Read from Redis pub/sub and forward transformed metrics."""
            if pubsub is None:
                await asyncio.get_running_loop().create_future()
                return

            await _forward_pubsub_messages(pubsub, websocket, is_pattern=True)

        await asyncio.wait(
            [
                asyncio.create_task(redis_reader()),
                asyncio.create_task(_client_reader(websocket)),
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
