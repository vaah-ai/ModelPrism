"""Typed Pydantic models for dashboard WebSocket messages.

These models define the contract between the backend's dashboard WebSocket
broadcast handler (``dashboard_ws.py``) and the frontend's WebSocket
composable (``useWebSocketMetrics.ts``).

Every message forwarded to a dashboard client is a ``DashboardMetricsMessage``
regardless of the source Redis channel (system ``metrics:{id}`` or
``vllm_metrics:{id}``).  Fields that are not present in the source payload
are set to ``None`` and omitted from the JSON wire format via
``model_dump(exclude_none=True)``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def _ts_to_iso(ts_raw: object) -> str | None:
    """Convert a Unix timestamp (int/float) to an ISO 8601 string.

    Returns ``None`` if the input is missing or not a valid timestamp.
    """
    if ts_raw is None:
        return None
    if isinstance(ts_raw, (int, float)):
        return datetime.fromtimestamp(ts_raw, tz=UTC).isoformat()
    return str(ts_raw)


class DashboardMetricsMessage:
    """Typed container for a dashboard WebSocket metric message.

    Every dashboard WS message carries ``type``, ``agent_id``, and ``ts``.
    All other fields are optional — they are populated by the transform
    functions based on which Redis channel the payload came from.

    System metrics (``metrics:{id}``) populate:
    ``gpu_util_avg_pct``, ``gpu_memory_used_mb``, ``ram_used_gb``,
    ``cpu_pct``, ``disk_*``, ``load_*``, ``gpu_cache_pct``.

    vLLM metrics (``vllm_metrics:{id}``) populate:
    ``running``, ``waiting``, ``running_models``, ``gpu_cache_pct``,
    ``gpu_util_avg_pct`` (mapped from vLLM's ``gpu_cache_pct``).
    """

    def __init__(
        self,
        agent_id: str,
        ts_raw: object,
        *,
        gpu_util_avg_pct: float | None = None,
        gpu_memory_used_mb: float | None = None,
        gpu_cache_pct: float | None = None,
        ram_used_gb: float | None = None,
        ram_total_gb: float | None = None,
        cpu_pct: float | None = None,
        load_1: float | None = None,
        load_5: float | None = None,
        load_15: float | None = None,
        disk_used_gb: float | None = None,
        disk_total_gb: float | None = None,
        disk_pct: float | None = None,
        running_models: int | None = None,
        running: int | None = None,
        waiting: int | None = None,
    ) -> None:
        ts_str = _ts_to_iso(ts_raw)
        if ts_str is None:
            msg = "ts_raw must be a valid Unix timestamp or ISO string"
            raise ValueError(msg)

        self.type: str = "metrics"
        self.agent_id: str = agent_id
        self.ts: str = ts_str
        self.gpu_util_avg_pct = gpu_util_avg_pct
        self.gpu_memory_used_mb = gpu_memory_used_mb
        self.gpu_cache_pct = gpu_cache_pct
        self.ram_used_gb = ram_used_gb
        self.ram_total_gb = ram_total_gb
        self.cpu_pct = cpu_pct
        self.load_1 = load_1
        self.load_5 = load_5
        self.load_15 = load_15
        self.disk_used_gb = disk_used_gb
        self.disk_total_gb = disk_total_gb
        self.disk_pct = disk_pct
        self.running_models = running_models
        self.running = running
        self.waiting = waiting

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict, excluding ``None`` values.

        This is the format sent over the WebSocket wire.
        Frontend ``useWebSocketMetrics.ts`` expects flat JSON with
        ``type``, ``agent_id``, ``ts``, and optional metric fields.
        """
        result: dict[str, Any] = {
            "type": self.type,
            "agent_id": self.agent_id,
            "ts": self.ts,
        }
        for field_name in (
            "gpu_util_avg_pct",
            "gpu_memory_used_mb",
            "gpu_cache_pct",
            "ram_used_gb",
            "ram_total_gb",
            "cpu_pct",
            "load_1",
            "load_5",
            "load_15",
            "disk_used_gb",
            "disk_total_gb",
            "disk_pct",
            "running_models",
            "running",
            "waiting",
        ):
            value = getattr(self, field_name)
            if value is not None:
                result[field_name] = value
        return result
