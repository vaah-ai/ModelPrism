"""Tests for the dashboard WebSocket broadcast handler.

Pure unit tests (no DB/Redis needed):
- TransformMetrics — validates metric transformation for various payload shapes
- TransformVllmMetrics — validates vLLM metric transformation
- RouteChannelMessage — validates channel-based routing logic
- TransformMetricsEdgeCases — empty GPUs, missing fields, null values
- DashboardMetricsMessageSchema — validates the typed schema itself
"""

from __future__ import annotations

from typing import Any

from app.schemas.dashboard_ws import DashboardMetricsMessage
from app.ws.dashboard_ws import (
    _route_channel_message,
    _transform_metrics,
    _transform_vllm_metrics,
)


def _make_gpu_metrics(ts: float = 1717094402.0) -> dict[str, Any]:
    return {
        "type": "metrics",
        "ts": ts,
        "gpu": [
            {
                "index": 0,
                "util_pct": 87,
                "mem_used_mb": 42100,
                "mem_total_mb": 81200,
                "temp_c": 72,
                "power_w": 285,
            }
        ],
        "ram_used_gb": 128,
        "ram_total_gb": 512,
        "cpu_pct": 12.5,
        "load_1": 8.2,
        "load_5": 7.1,
        "load_15": 6.5,
        "disk_used_gb": 548,
        "disk_total_gb": 2048,
        "disk_pct": 26.8,
    }


def _make_vllm_metrics(ts: float = 1717094402.0) -> dict[str, Any]:
    return {
        "type": "vllm_metrics",
        "instance_id": "inst_qwen_001",
        "ts": ts,
        "model_name": "Qwen2.5-72B-Instruct",
        "running": 3,
        "waiting": 2,
        "total_requests": 15234,
        "prompt_tokens_total": 450000000,
        "gen_tokens_total": 120000000,
        "ttft_p50_ms": 280,
        "ttft_p99_ms": 850,
        "gpu_cache_pct": 62.5,
        "tps": 1850,
        "prefix_cache_hit_pct": 34,
        "error_pct": 0.02,
        "trunc_pct": 1.2,
    }


# ── DashboardMetricsMessage Schema ─────────────────────────────────


class TestDashboardMetricsMessageSchema:
    """DashboardMetricsMessage typed schema validation."""

    def test_creates_with_required_fields(self) -> None:
        """Minimal fields create a valid message."""
        msg = DashboardMetricsMessage(agent_id="ag_xyz789", ts_raw=1717094402.0)
        assert msg.type == "metrics"
        assert msg.agent_id == "ag_xyz789"
        assert msg.ts == "2024-05-30T18:40:02+00:00"

    def test_to_dict_excludes_none(self) -> None:
        """to_dict() omits None and default fields."""
        msg = DashboardMetricsMessage(agent_id="ag_xyz789", ts_raw=1717094402.0)
        d = msg.to_dict()
        # Required fields always present
        assert set(d.keys()) == {"type", "agent_id", "ts"}
        assert "gpu_util_avg_pct" not in d  # None, so excluded

    def test_to_dict_includes_set_fields(self) -> None:
        """to_dict() includes non-None fields."""
        msg = DashboardMetricsMessage(
            agent_id="ag_xyz789",
            ts_raw=1717094402.0,
            gpu_util_avg_pct=87.0,
            running=3,
            cpu_pct=12.5,
        )
        d = msg.to_dict()
        assert d["gpu_util_avg_pct"] == 87.0
        assert d["running"] == 3
        assert d["cpu_pct"] == 12.5
        assert "gpu_memory_used_mb" not in d  # None

    def test_rejects_missing_ts(self) -> None:
        """Missing ts raises ValueError."""
        try:
            DashboardMetricsMessage(agent_id="ag_xyz789", ts_raw=None)
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_string_timestamp_passthrough(self) -> None:
        """String timestamps are passed through as-is."""
        msg = DashboardMetricsMessage(
            agent_id="ag_xyz789",
            ts_raw="2024-05-30T18:40:02+00:00",
        )
        assert msg.ts == "2024-05-30T18:40:02+00:00"


# ── System Metrics Transformation ──────────────────────────────────


class TestTransformMetrics:
    """_transform_metrics correctly converts raw agent payloads to dashboard format."""

    def _assert_msg(
        self,
        result: DashboardMetricsMessage | None,
    ) -> DashboardMetricsMessage:
        assert result is not None
        return result

    def test_basic_transformation(self) -> None:
        """A standard metric snapshot with one GPU is correctly flattened."""
        result = self._assert_msg(_transform_metrics(_make_gpu_metrics(), "ag_xyz789"))
        assert result.type == "metrics"
        assert result.agent_id == "ag_xyz789"
        assert result.ts == "2024-05-30T18:40:02+00:00"
        assert result.gpu_util_avg_pct == 87.0
        assert result.gpu_memory_used_mb == 42100.0
        assert result.ram_used_gb == 128
        assert result.cpu_pct == 12.5
        assert result.load_1 == 8.2
        assert result.disk_pct == 26.8
        # System metrics have no running/waiting info
        assert result.running_models is None
        assert result.running is None
        assert result.waiting is None

    def test_multiple_gpus_averaged(self) -> None:
        """GPU metrics across multiple GPUs are averaged correctly."""
        raw: dict[str, Any] = {
            "type": "metrics",
            "ts": 1717094402.0,
            "gpu": [
                {"index": 0, "util_pct": 80, "mem_used_mb": 40000, "mem_total_mb": 81200},
                {"index": 1, "util_pct": 90, "mem_used_mb": 60000, "mem_total_mb": 81200},
                {"index": 2, "util_pct": 70, "mem_used_mb": 30000, "mem_total_mb": 81200},
                {"index": 3, "util_pct": 60, "mem_used_mb": 20000, "mem_total_mb": 81200},
            ],
        }

        result = self._assert_msg(_transform_metrics(raw, "ag_xyz789"))
        assert result.gpu_util_avg_pct == 75.0
        assert result.gpu_memory_used_mb == 37500.0

    def test_empty_gpu_list(self) -> None:
        """An empty GPU list produces None averages."""
        raw = {"type": "metrics", "ts": 1717094402.0, "gpu": []}

        result = _transform_metrics(raw, "ag_xyz789")
        assert result is not None
        assert result.gpu_util_avg_pct is None
        assert result.gpu_memory_used_mb is None

    def test_missing_ts_field(self) -> None:
        """Payload without a ts field is rejected."""
        raw = {"type": "metrics", "gpu": [{"util_pct": 87}]}

        result = _transform_metrics(raw, "ag_xyz789")
        assert result is None

    def test_missing_gpu_field(self) -> None:
        """Payload without a gpu field produces None averages."""
        raw = {"type": "metrics", "ts": 1717094402.0, "cpu_pct": 12.5}

        result = _transform_metrics(raw, "ag_xyz789")
        assert result is not None
        assert result.gpu_util_avg_pct is None
        assert result.gpu_memory_used_mb is None
        assert result.cpu_pct == 12.5

    def test_mixed_gpu_field_availability(self) -> None:
        """Some GPUs missing a field should still average available ones."""
        raw: dict[str, Any] = {
            "type": "metrics",
            "ts": 1717094402.0,
            "gpu": [
                {"index": 0, "util_pct": 80, "mem_used_mb": 40000},
                {"index": 1, "util_pct": 90},
                {"index": 2},
            ],
        }

        result = self._assert_msg(_transform_metrics(raw, "ag_xyz789"))
        assert result.gpu_util_avg_pct == 85.0
        assert result.gpu_memory_used_mb == 40000.0

    def test_string_timestamp(self) -> None:
        """String timestamps are passed through, not converted."""
        raw = {"type": "metrics", "ts": "2024-05-30T14:40:02+00:00", "gpu": []}

        result = _transform_metrics(raw, "ag_xyz789")
        assert result is not None
        assert result.ts == "2024-05-30T14:40:02+00:00"

    def test_gpu_cache_pct_passthrough(self) -> None:
        """gpu_cache_pct from system metrics is forwarded."""
        raw = {"type": "metrics", "ts": 1717094402.0, "gpu": [], "gpu_cache_pct": 62.5}

        result = self._assert_msg(_transform_metrics(raw, "ag_xyz789"))
        assert result.gpu_cache_pct == 62.5

    def test_to_dict_output(self) -> None:
        """The serialized dict matches frontend expectations."""
        raw = _make_gpu_metrics()
        result = self._assert_msg(_transform_metrics(raw, "ag_xyz789"))
        d = result.to_dict()
        assert d["type"] == "metrics"
        assert d["agent_id"] == "ag_xyz789"
        assert d["gpu_util_avg_pct"] == 87.0
        assert d["gpu_memory_used_mb"] == 42100.0
        assert d["cpu_pct"] == 12.5
        # None fields are excluded
        assert "running" not in d
        assert "running_models" not in d


# ── vLLM Metrics Transformation ────────────────────────────────────


class TestTransformVllmMetrics:
    """_transform_vllm_metrics correctly converts vLLM payloads."""

    def _assert_msg(
        self,
        result: DashboardMetricsMessage | None,
    ) -> DashboardMetricsMessage:
        assert result is not None
        return result

    def test_basic_vllm_transformation(self) -> None:
        """vLLM metrics produce dashboard format with running/waiting."""
        result = self._assert_msg(_transform_vllm_metrics(_make_vllm_metrics(), "ag_xyz789"))
        assert result.type == "metrics"
        assert result.agent_id == "ag_xyz789"
        assert result.ts == "2024-05-30T18:40:02+00:00"
        assert result.running == 3
        assert result.waiting == 2
        assert result.running_models == 1
        # System fields are None for vLLM-only payloads
        assert result.gpu_memory_used_mb is None

    def test_vllm_no_model_name(self) -> None:
        """vLLM metrics without model_name produce running_models = 0."""
        raw = _make_vllm_metrics()
        del raw["model_name"]

        result = self._assert_msg(_transform_vllm_metrics(raw, "ag_xyz789"))
        assert result.running_models == 0
        assert result.running == 3

    def test_vllm_missing_ts(self) -> None:
        """vLLM payload without ts is rejected."""
        raw = _make_vllm_metrics()
        del raw["ts"]

        result = _transform_vllm_metrics(raw, "ag_xyz789")
        assert result is None

    def test_vllm_gpu_cache_pct(self) -> None:
        """gpu_cache_pct from vLLM is forwarded."""
        raw = _make_vllm_metrics()
        raw["gpu_cache_pct"] = 75.0

        result = self._assert_msg(_transform_vllm_metrics(raw, "ag_xyz789"))
        assert result.gpu_cache_pct == 75.0
        assert result.gpu_util_avg_pct == 75.0

    def test_to_dict_output(self) -> None:
        """The serialized dict from vLLM matches frontend expectations."""
        result = self._assert_msg(_transform_vllm_metrics(_make_vllm_metrics(), "ag_xyz789"))
        d = result.to_dict()
        assert d["running"] == 3
        assert d["waiting"] == 2
        assert d["running_models"] == 1
        assert d["gpu_cache_pct"] == 62.5
        # System None fields are excluded
        assert "ram_used_gb" not in d
        assert "load_1" not in d


# ── Channel Routing ────────────────────────────────────────────────


class TestRouteChannelMessage:
    """_route_channel_message dispatches to the correct transform."""

    def test_routes_metrics_channel(self) -> None:
        """Messages on metrics:{id} channel use _transform_metrics."""
        data = '{"type":"metrics","ts":1717094402.0,"gpu":[{"util_pct":87,"mem_used_mb":42100}]}'

        result = _route_channel_message("metrics:ag_xyz789", data, "ag_xyz789")
        assert result is not None
        assert result.gpu_util_avg_pct == 87.0
        assert result.gpu_memory_used_mb == 42100.0
        # System route has no running info
        assert result.running is None

    def test_routes_vllm_channel(self) -> None:
        """Messages on vllm_metrics:{id} channel use _transform_vllm_metrics."""
        data = (
            '{"type":"vllm_metrics","ts":1717094402.0,'
            '"model_name":"Qwen2.5","running":3,"waiting":2}'
        )

        result = _route_channel_message("vllm_metrics:ag_xyz789", data, "ag_xyz789")
        assert result is not None
        assert result.running == 3
        assert result.waiting == 2
        assert result.running_models == 1

    def test_routes_unknown_channel_as_metrics(self) -> None:
        """Unknown channel prefix falls through to _transform_metrics."""
        data = '{"type":"metrics","ts":1717094402.0,"gpu":[]}'

        result = _route_channel_message("unknown:ag_xyz789", data, "ag_xyz789")
        assert result is not None

    def test_returns_none_for_invalid_json(self) -> None:
        """Invalid JSON returns None."""
        result = _route_channel_message("metrics:ag_xyz789", "not-json", "ag_xyz789")
        assert result is None

    def test_returns_none_for_missing_ts(self) -> None:
        """Valid JSON without ts returns None."""
        data = '{"type":"metrics","gpu":[]}'

        result = _route_channel_message("metrics:ag_xyz789", data, "ag_xyz789")
        assert result is None
