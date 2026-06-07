"""Pydantic models for agent WebSocket message types.

All messages use a lightweight flat-JSON format (not JSON:API) to
minimise overhead on the 2-second metric push cycle.  Each message
has a ``type`` discriminator field that determines its shape.

Message types:
- ``heartbeat`` — Agent → Backend, 15s keep-alive
- ``metrics`` — Agent → Backend, GPU + system snapshot (every 2s)
- ``vllm_metrics`` — Agent → Backend, per-instance vLLM telemetry
- ``command`` — Backend → Agent, deployment or action command
- ``command_progress`` — Agent → Backend, progress update
- ``command_result`` — Agent → Backend, terminal result
- ``shutdown`` — Backend → Agent, graceful server restart notice
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# ── GPU / System metric sub-models ──────────────────────────────────


class GpuMetric(BaseModel):
    """Per-GPU metrics from nvidia-smi."""

    index: int = Field(..., ge=0, description="GPU index (0-based)")
    util_pct: float | None = Field(default=None, ge=0, le=100, description="GPU utilization %")
    mem_used_mb: float | None = Field(default=None, ge=0, description="Used VRAM in MB")
    mem_total_mb: float | None = Field(default=None, ge=0, description="Total VRAM in MB")
    temp_c: float | None = Field(default=None, ge=0, le=120, description="GPU temperature °C")
    power_w: float | None = Field(default=None, ge=0, description="GPU power draw in watts")


# ── Heartbeat ──────────────────────────────────────────────────────


class HeartbeatMessage(BaseModel):
    """Agent heartbeat sent every 15 seconds.

    The backend responds to keep the connection alive and updates
    ``last_seen_at`` on each received heartbeat.
    """

    type: Literal["heartbeat"] = "heartbeat"
    ts: float = Field(
        ...,
        description="Agent-local Unix epoch seconds",
    )
    agents_running: list[str] = Field(
        default_factory=list,
        description="Identifiers of running vLLM instances, e.g. ['vllm:5', 'vllm:6']",
    )


# ── Metrics ────────────────────────────────────────────────────────


class MetricsMessage(BaseModel):
    """Full GPU + system metrics snapshot pushed every 2 seconds."""

    type: Literal["metrics"] = "metrics"
    ts: float = Field(..., description="Agent-local Unix epoch seconds")
    gpu: list[GpuMetric] = Field(
        ...,
        min_length=1,
        description="Per-GPU metrics, at least one GPU expected",
    )
    gpu_cache_pct: float | None = Field(
        default=None, ge=0, le=100, description="GPU KV cache utilization %"
    )
    ram_used_gb: float | None = Field(default=None, ge=0, description="Used system RAM in GB")
    ram_total_gb: float | None = Field(default=None, ge=0, description="Total system RAM in GB")
    cpu_pct: float | None = Field(
        default=None, ge=0, le=100, description="Overall CPU utilization %"
    )
    load_1: float | None = Field(default=None, ge=0, description="1-minute load average")
    load_5: float | None = Field(default=None, ge=0, description="5-minute load average")
    load_15: float | None = Field(default=None, ge=0, description="15-minute load average")
    disk_used_gb: float | None = Field(default=None, ge=0, description="Used disk space in GB")
    disk_total_gb: float | None = Field(default=None, ge=0, description="Total disk capacity in GB")
    disk_pct: float | None = Field(default=None, ge=0, le=100, description="Disk utilization %")


# ── vLLM Metrics ───────────────────────────────────────────────────


class VLLMMetricsMessage(BaseModel):
    """Per-instance vLLM telemetry pushed every 2 seconds."""

    type: Literal["vllm_metrics"] = "vllm_metrics"
    instance_id: str = Field(..., max_length=100, description="vLLM instance identifier")
    ts: float = Field(..., description="Agent-local Unix epoch seconds")
    model_name: str | None = Field(default=None, max_length=200, description="Served model name")
    running: int | None = Field(default=None, ge=0, description="Currently running requests")
    waiting: int | None = Field(default=None, ge=0, description="Queued / waiting requests")
    total_requests: int | None = Field(default=None, ge=0, description="Cumulative request count")
    prompt_tokens_total: int | None = Field(
        default=None, ge=0, description="Cumulative prompt tokens"
    )
    gen_tokens_total: int | None = Field(
        default=None, ge=0, description="Cumulative generated tokens"
    )
    ttft_p50_ms: float | None = Field(default=None, ge=0, description="TTFT p50 in milliseconds")
    ttft_p99_ms: float | None = Field(default=None, ge=0, description="TTFT p99 in milliseconds")
    gpu_cache_pct: float | None = Field(
        default=None, ge=0, le=100, description="GPU KV cache utilization %"
    )
    tps: float | None = Field(default=None, ge=0, description="Throughput in tokens/second")
    prefix_cache_hit_pct: float | None = Field(
        default=None, ge=0, le=100, description="Prefix cache hit rate %"
    )
    error_pct: float | None = Field(default=None, ge=0, le=100, description="Error rate %")
    trunc_pct: float | None = Field(default=None, ge=0, le=100, description="Truncation rate %")
    server_start_ts: float | None = Field(default=None, description="vLLM server start timestamp")


# ── Command (Backend → Agent) ──────────────────────────────────────


class CommandMessage(BaseModel):
    """Command sent from backend to agent over WebSocket."""

    type: Literal["command"] = "command"
    command_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique command identifier (UUID string)",
    )
    command: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Command name, e.g. 'deploy_model', 'stop_model'",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Command-specific parameters",
    )


# ── Command Progress & Result (Agent → Backend) ───────────────────


class CommandProgressMessage(BaseModel):
    """Progress update sent by the agent during command execution."""

    type: Literal["command_progress"] = "command_progress"
    command_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Command identifier returned in the original command",
    )
    status: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Status label, e.g. 'downloading', 'starting'",
    )
    progress_pct: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Progress percentage (0–100)",
    )
    message: str | None = Field(
        default=None,
        max_length=500,
        description="Human-readable progress description",
    )


_COMMAND_RESULT_STATUSES = {"success", "failed", "rejected"}


class CommandResultMessage(BaseModel):
    """Terminal result sent by the agent after command execution."""

    type: Literal["command_result"] = "command_result"
    command_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Command identifier returned in the original command",
    )
    status: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Terminal status: 'success', 'failed', or 'rejected'",
    )
    result: dict[str, Any] | None = Field(
        default=None,
        description="Result payload (e.g. instance_id, port, pid)",
    )
    error: str | None = Field(
        default=None,
        max_length=1000,
        description="Error message if status is 'failed' or 'rejected'",
    )

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: str) -> str:
        if v not in _COMMAND_RESULT_STATUSES:
            msg = f"Invalid command result status: '{v}'. Must be one of {_COMMAND_RESULT_STATUSES}"
            raise ValueError(msg)
        return v


# ── Shutdown (Backend → Agent) ─────────────────────────────────────


class ShutdownMessage(BaseModel):
    """Graceful server shutdown notification sent to all connected agents."""

    type: Literal["shutdown"] = "shutdown"
    reason: str = Field(
        default="server_restart",
        max_length=100,
        description="Shutdown reason, e.g. 'server_restart'",
    )
    reconnect_delay_seconds: int = Field(
        default=10,
        ge=0,
        le=300,
        description="Seconds the agent should wait before reconnecting",
    )


# ── Discriminated Union ────────────────────────────────────────────


AgentMessage = (
    HeartbeatMessage
    | MetricsMessage
    | VLLMMetricsMessage
    | CommandProgressMessage
    | CommandResultMessage
)
"""Union of all agent-to-backend message types."""

BackendMessage = CommandMessage | ShutdownMessage
"""Union of all backend-to-agent message types."""


MESSAGE_TYPE_MAP: dict[str, type[AgentMessage]] = {
    "heartbeat": HeartbeatMessage,
    "metrics": MetricsMessage,
    "vllm_metrics": VLLMMetricsMessage,
    "command_progress": CommandProgressMessage,
    "command_result": CommandResultMessage,
}
"""Maps ``type`` discriminator strings to their Pydantic model classes."""


def parse_agent_message(raw: dict[str, object]) -> AgentMessage | None:
    """Parse a raw JSON dict into the correct agent message type.

    Returns ``None`` (and logs a warning) for unknown types or
    validation failures — the handler drops malformed messages
    rather than disconnecting the agent.
    """
    import logging

    logger = logging.getLogger(__name__)

    msg_type = raw.get("type")
    if not isinstance(msg_type, str):
        logger.warning("Received message without a valid 'type' field")
        return None

    model_cls = MESSAGE_TYPE_MAP.get(msg_type)
    if model_cls is None:
        logger.warning("Unknown message type: '%s'", msg_type)
        return None

    try:
        return model_cls.model_validate(raw)
    except Exception:
        logger.exception("Failed to validate %s message", msg_type)
        return None
