"""Tests for the dashboard WebSocket broadcast handler.

Pure unit tests (no DB/Redis needed):
- TransformMetrics — validates metric transformation for various payload shapes
- TransformMetricsEdgeCases — empty GPUs, missing fields, null values

Integration tests (require PostgreSQL + Redis):
- TestDashboardWsEndpoint — skipped by default
"""

from __future__ import annotations

from app.ws.dashboard_ws import _transform_metrics

# ── Metric Transformation Tests ────────────────────────────────────


class TestTransformMetrics:
    """_transform_metrics correctly converts raw agent payloads to dashboard format."""

    def test_basic_transformation(self) -> None:
        """A standard metric snapshot with one GPU is correctly flattened."""
        raw = {
            "type": "metrics",
            "ts": 1717094402.0,
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

        result = _transform_metrics(raw, "ag_xyz789")
        assert result is not None
        assert result["type"] == "metrics"
        assert result["agent_id"] == "ag_xyz789"
        # 1717094402 = 2024-05-30T18:40:02+00:00 UTC
        assert result["ts"] == "2024-05-30T18:40:02+00:00"
        assert result["gpu_util_avg_pct"] == 87.0
        assert result["gpu_memory_used_mb"] == 42100.0
        assert result["ram_used_gb"] == 128
        assert result["cpu_pct"] == 12.5
        assert result["load_1"] == 8.2
        assert result["disk_pct"] == 26.8

    def test_multiple_gpus_averaged(self) -> None:
        """GPU metrics across multiple GPUs are averaged correctly."""
        raw = {
            "type": "metrics",
            "ts": 1717094402.0,
            "gpu": [
                {"index": 0, "util_pct": 80, "mem_used_mb": 40000, "mem_total_mb": 81200},
                {"index": 1, "util_pct": 90, "mem_used_mb": 60000, "mem_total_mb": 81200},
                {"index": 2, "util_pct": 70, "mem_used_mb": 30000, "mem_total_mb": 81200},
                {"index": 3, "util_pct": 60, "mem_used_mb": 20000, "mem_total_mb": 81200},
            ],
        }

        result = _transform_metrics(raw, "ag_xyz789")
        assert result is not None
        assert result["gpu_util_avg_pct"] == 75.0  # (80 + 90 + 70 + 60) / 4
        assert result["gpu_memory_used_mb"] == 37500.0  # (40000 + 60000 + 30000 + 20000) / 4

    def test_vllm_metrics_passthrough(self) -> None:
        """vLLM metric payloads are handled (run/wait counts)."""
        raw = {
            "type": "vllm_metrics",
            "instance_id": "inst_001",
            "ts": 1717094402.0,
            "model_name": "Qwen2.5-72B-Instruct",
            "running": 3,
            "waiting": 2,
            "ttft_p50_ms": 280,
            "ttft_p99_ms": 850,
        }

        result = _transform_metrics(raw, "ag_xyz789")
        assert result is not None
        # vLLM metrics aren't dedicated yet — they flow through the
        # metrics channel. GPU fields will be None but other fields
        # are passed through as-is.
        assert result["gpu_util_avg_pct"] is None
        assert result["gpu_memory_used_mb"] is None


class TestTransformMetricsEdgeCases:
    """Edge cases for metric transformation."""

    def test_empty_gpu_list(self) -> None:
        """An empty GPU list produces None averages."""
        raw = {"type": "metrics", "ts": 1717094402.0, "gpu": []}

        result = _transform_metrics(raw, "ag_xyz789")
        assert result is not None
        assert result["gpu_util_avg_pct"] is None
        assert result["gpu_memory_used_mb"] is None

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
        assert result["gpu_util_avg_pct"] is None
        assert result["gpu_memory_used_mb"] is None
        assert result["cpu_pct"] == 12.5

    def test_mixed_gpu_field_availability(self) -> None:
        """Some GPUs missing a field should still average available ones."""
        raw = {
            "type": "metrics",
            "ts": 1717094402.0,
            "gpu": [
                {"index": 0, "util_pct": 80, "mem_used_mb": 40000},
                {"index": 1, "util_pct": 90},  # No mem_used_mb
                {"index": 2},  # Nothing
            ],
        }

        result = _transform_metrics(raw, "ag_xyz789")
        assert result is not None
        assert result["gpu_util_avg_pct"] == 85.0  # (80 + 90) / 2
        assert result["gpu_memory_used_mb"] == 40000.0  # Only one GPU has it

    def test_string_timestamp(self) -> None:
        """String timestamps are passed through, not converted."""
        raw = {"type": "metrics", "ts": "2024-05-30T14:40:02+00:00", "gpu": []}

        result = _transform_metrics(raw, "ag_xyz789")
        assert result is not None
        assert result["ts"] == "2024-05-30T14:40:02+00:00"
