"""Tests for the agent WebSocket handler.

Pure schema/unit tests (no DB needed):
- ParseAgentMessage — validates parse_agent_message works for all types
- CommandResultValidation — validates CommandResultMessage status field
- ClockSkew — tests clock skew detection
- BuildWsError — tests error response builder
- AgentConnectionRegistry — tests in-memory connection registry with mocks

Integration tests (require PostgreSQL + Redis):
- TestAgentWebSocketEndpoint — skipped by default
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

import pytest
from pydantic import ValidationError

# ── Test Data ──────────────────────────────────────────────────────

_HEARTBEAT_PAYLOAD = {
    "type": "heartbeat",
    "ts": 1717094400.0,
    "agents_running": ["vllm:5", "vllm:6"],
}

_METRICS_PAYLOAD: dict[str, object] = {
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
    "gpu_cache_pct": 62.5,
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

_VLLM_METRICS_PAYLOAD: dict[str, object] = {
    "type": "vllm_metrics",
    "instance_id": "inst_qwen_001",
    "ts": 1717094402.0,
    "model_name": "Qwen2.5-72B-Instruct",
    "running": 3,
    "waiting": 2,
    "total_requests": 15234,
    "prompt_tokens_total": 450000000,
    "gen_tokens_total": 120000000,
    "ttft_p50_ms": 280.0,
    "ttft_p99_ms": 850.0,
    "gpu_cache_pct": 62.5,
    "tps": 1850.0,
    "prefix_cache_hit_pct": 34.0,
    "error_pct": 0.02,
    "trunc_pct": 1.2,
    "server_start_ts": 1716800000.0,
}

_COMMAND_PROGRESS_PAYLOAD: dict[str, object] = {
    "type": "command_progress",
    "command_id": "cmd_001",
    "status": "downloading",
    "progress_pct": 45,
    "message": "Downloading model weights... (2.4 GB / 5.3 GB)",
}

_COMMAND_RESULT_PAYLOAD: dict[str, object] = cast(
    "dict[str, object]",
    {
        "type": "command_result",
        "command_id": "cmd_001",
        "status": "success",
        "result": {
            "instance_id": "inst_001",
            "port": 8001,
            "pid": 12345,
            "endpoint": "http://localhost:8001/v1",
        },
    },
)


# ── Schema Validation Tests ────────────────────────────────────────


class TestParseAgentMessage:
    """Tests for ``parse_agent_message`` helper."""

    def test_parses_heartbeat(self) -> None:
        from app.schemas.ws_messages import parse_agent_message

        msg = parse_agent_message(_HEARTBEAT_PAYLOAD)
        assert msg is not None
        assert msg.type == "heartbeat"
        assert msg.ts == 1717094400.0
        assert msg.agents_running == ["vllm:5", "vllm:6"]

    def test_parses_metrics(self) -> None:
        from app.schemas.ws_messages import parse_agent_message

        msg = parse_agent_message(_METRICS_PAYLOAD)
        assert msg is not None
        assert msg.type == "metrics"
        assert len(msg.gpu) == 1
        assert msg.gpu[0].util_pct == 87

    def test_parses_vllm_metrics(self) -> None:
        from app.schemas.ws_messages import parse_agent_message

        msg = parse_agent_message(_VLLM_METRICS_PAYLOAD)
        assert msg is not None
        assert msg.type == "vllm_metrics"
        assert msg.instance_id == "inst_qwen_001"

    def test_parses_command_progress(self) -> None:
        from app.schemas.ws_messages import parse_agent_message

        msg = parse_agent_message(_COMMAND_PROGRESS_PAYLOAD)
        assert msg is not None
        assert msg.type == "command_progress"
        assert msg.command_id == "cmd_001"

    def test_parses_command_result(self) -> None:
        from app.schemas.ws_messages import parse_agent_message

        msg = parse_agent_message(_COMMAND_RESULT_PAYLOAD)
        assert msg is not None
        assert msg.type == "command_result"
        assert msg.status == "success"

    def test_returns_none_for_unknown_type(self) -> None:
        from app.schemas.ws_messages import parse_agent_message

        msg = parse_agent_message({"type": "unknown"})
        assert msg is None

    def test_returns_none_for_missing_type(self) -> None:
        from app.schemas.ws_messages import parse_agent_message

        msg = parse_agent_message({"foo": "bar"})
        assert msg is None

    def test_returns_none_for_invalid_metrics(self) -> None:
        from app.schemas.ws_messages import parse_agent_message

        msg = parse_agent_message({"type": "metrics", "ts": 0})
        assert msg is None  # Missing required 'gpu' field


class TestCommandResultValidation:
    """Tests for CommandResultMessage status validation."""

    def test_accepts_valid_statuses(self) -> None:
        from app.schemas.ws_messages import CommandResultMessage

        for status in ("success", "failed", "rejected"):
            msg = CommandResultMessage(command_id="c1", status=status)
            assert msg.status == status

    def test_rejects_invalid_status(self) -> None:
        from app.schemas.ws_messages import CommandResultMessage

        with pytest.raises(ValidationError):
            CommandResultMessage(command_id="c1", status="unknown")


class TestClockSkew:
    """Tests for clock skew detection."""

    def test_small_skew_passes_through(self) -> None:
        from app.ws.agent_ws import _check_clock_skew

        now = datetime.now(UTC).timestamp()
        result = _check_clock_skew(now, UUID("00000000-0000-0000-0000-000000000001"))
        assert result == now

    def test_large_skew_uses_server_time(self) -> None:
        from app.ws.agent_ws import _check_clock_skew

        future = datetime.now(UTC).timestamp() + 600  # 10 minutes ahead
        result = _check_clock_skew(future, UUID("00000000-0000-0000-0000-000000000001"))
        now = datetime.now(UTC).timestamp()
        assert abs(result - now) < 5


class TestBuildWsError:
    """Tests for _build_ws_error helper."""

    def test_returns_json(self) -> None:
        from app.ws.agent_ws import _build_ws_error

        result = _build_ws_error("Agent not found")
        parsed = json.loads(result)
        assert parsed == {"error": "unauthorized", "detail": "Agent not found"}


# ── Connection Registry Tests ──────────────────────────────────────


class _MockWS:
    """Minimal WebSocket mock for testing the connection registry."""

    def __init__(self) -> None:
        self._closed = False
        self._close_code: int | None = None
        self._sent_text: str | None = None
        self._sent_json: dict[str, Any] | None = None

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self._closed = True
        self._close_code = code

    async def send_text(self, data: str) -> None:
        self._sent_text = data

    async def send_json(self, data: dict[str, Any]) -> None:
        self._sent_json = data


class TestAgentConnectionRegistry:
    """Tests for the in-memory AgentConnectionRegistry."""

    @pytest.mark.asyncio
    async def test_register_and_unregister(self) -> None:
        from app.services.agent_manager import AgentConnectionRegistry

        registry = AgentConnectionRegistry()
        agent_id = UUID("11111111-1111-1111-1111-111111111111")
        ws = _MockWS()
        await registry.register(agent_id, ws)
        assert await registry.get_online_count() == 1
        assert agent_id in await registry.get_active_ids()

        pending = await registry.unregister(agent_id)
        assert await registry.get_online_count() == 0
        assert isinstance(pending, dict)

    @pytest.mark.asyncio
    async def test_register_replaces_stale_connection(self) -> None:
        from app.services.agent_manager import AgentConnectionRegistry

        registry = AgentConnectionRegistry()
        agent_id = UUID("22222222-2222-2222-2222-222222222222")
        ws1 = _MockWS()
        ws2 = _MockWS()
        await registry.register(agent_id, ws1)
        await registry.register(agent_id, ws2)
        assert ws1._closed is True
        assert ws1._close_code == 1008

    @pytest.mark.asyncio
    async def test_get_online_count(self) -> None:
        from app.services.agent_manager import AgentConnectionRegistry

        registry = AgentConnectionRegistry()
        assert await registry.get_online_count() == 0
        ws1 = _MockWS()
        ws2 = _MockWS()
        await registry.register(UUID("33333333-3333-3333-3333-333333333333"), ws1)
        await registry.register(UUID("44444444-4444-4444-4444-444444444444"), ws2)
        assert await registry.get_online_count() == 2

    @pytest.mark.asyncio
    async def test_resolve_command(self) -> None:
        from app.schemas.ws_messages import CommandMessage
        from app.services.agent_manager import AgentConnectionRegistry

        registry = AgentConnectionRegistry()
        agent_id = UUID("55555555-5555-5555-5555-555555555555")
        ws = _MockWS()
        await registry.register(agent_id, ws)
        cmd = CommandMessage(command_id="cmd_test", command="deploy_model")
        sent = await registry.send_command(agent_id, cmd)
        assert sent is True
        resolved = await registry.resolve_command(agent_id, "cmd_test")
        assert resolved is not None
        assert resolved.command_id == "cmd_test"
        resolved2 = await registry.resolve_command(agent_id, "cmd_test")
        assert resolved2 is None

    @pytest.mark.asyncio
    async def test_send_command_to_disconnected_agent(self) -> None:
        from app.schemas.ws_messages import CommandMessage
        from app.services.agent_manager import AgentConnectionRegistry

        registry = AgentConnectionRegistry()
        agent_id = UUID("66666666-6666-6666-6666-666666666666")
        cmd = CommandMessage(command_id="cmd_test", command="deploy_model")
        sent = await registry.send_command(agent_id, cmd)
        assert sent is False

    @pytest.mark.asyncio
    async def test_broadcast_shutdown(self) -> None:
        from app.services.agent_manager import AgentConnectionRegistry

        registry = AgentConnectionRegistry()
        ws1 = _MockWS()
        ws2 = _MockWS()
        await registry.register(UUID("77777777-7777-7777-7777-777777777777"), ws1)
        await registry.register(UUID("88888888-8888-8888-8888-888888888888"), ws2)
        count = await registry.broadcast_shutdown(reconnect_delay_seconds=30)
        assert count == 2
        assert ws1._sent_text is not None
        assert "shutdown" in ws1._sent_text
        assert ws2._sent_text is not None
        assert "shutdown" in ws2._sent_text
