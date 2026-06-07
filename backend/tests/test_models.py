"""Tests for SQLAlchemy ORM model definitions.

These tests verify model creation, column types, relationships,
and index definitions. They do not require a database connection.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, Enum, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase

from app.models import Base
from app.models.agent import Agent
from app.models.agent_log import AgentLog
from app.models.agent_metric import AgentMetric
from app.models.agent_token import AgentToken
from app.models.enums import AgentStatus, LogLevel, MetricTier, TokenStatus


class TestBase:
    """Verify the declarative Base class."""

    def test_base_is_declarative(self) -> None:
        """Base should be a DeclarativeBase instance."""
        assert issubclass(Base, DeclarativeBase)

    def test_all_tables_registered(self) -> None:
        """All 4 foundation tables should be in Base.metadata."""
        table_names = set(Base.metadata.tables.keys())
        expected = {"agents", "agent_tokens", "agent_metrics", "agent_logs"}
        missing = expected - table_names
        extra = table_names - expected
        assert not missing, f"Missing tables: {missing}"
        assert not extra, f"Unexpected tables: {extra}"


class TestAgentModel:
    """Verify the Agent ORM model."""

    def test_table_name(self) -> None:
        assert Agent.__tablename__ == "agents"

    def test_primary_key(self) -> None:
        col = Agent.__table__.c["id"]
        assert col.primary_key
        assert isinstance(col.type, UUID)
        assert col.type.as_uuid is True

    def test_required_columns(self) -> None:
        table = Agent.__table__
        assert isinstance(table.c["name"].type, String)
        assert table.c["name"].type.length == 100
        assert table.c["name"].nullable is False

        assert isinstance(table.c["status"].type, Enum)
        assert table.c["status"].nullable is False

    def test_jsonb_columns(self) -> None:
        table = Agent.__table__
        for col_name in ("gpu_info", "cpu_info", "disk_info"):
            col = table.c[col_name]
            assert isinstance(col.type, JSONB), f"{col_name} should be JSONB"
            assert col.nullable is True

    def test_timestamp_columns(self) -> None:
        table = Agent.__table__
        for col_name in ("created_at", "updated_at"):
            col = table.c[col_name]
            assert isinstance(col.type, DateTime), f"{col_name} should be DateTime"
            assert col.nullable is False

    def test_indexes(self) -> None:
        indexes = {idx.name: idx for idx in Agent.__table__.indexes}
        assert "ix_agents_status" in indexes
        assert list(indexes["ix_agents_status"].columns.keys()) == ["status"]

        assert "ix_agents_last_seen_at" in indexes
        assert list(indexes["ix_agents_last_seen_at"].columns.keys()) == ["last_seen_at"]

        assert "ix_agents_workspace_id" in indexes
        assert list(indexes["ix_agents_workspace_id"].columns.keys()) == ["workspace_id"]

    def test_relationships(self) -> None:
        mapper = Agent.__mapper__
        rel_names = {r.key for r in mapper.relationships}
        expected = {"tokens", "metrics", "logs"}
        assert expected.issubset(rel_names), f"Missing relationships: {expected - rel_names}"

    def test_default_status(self) -> None:
        # Check Python-level default (not server_default for enum columns)
        col = Agent.__table__.c["status"]
        assert col.default is not None or col.server_default is not None

    def test_workspace_id_nullable(self) -> None:
        col = Agent.__table__.c["workspace_id"]
        assert col.nullable is True


class TestAgentTokenModel:
    """Verify the AgentToken ORM model."""

    def test_table_name(self) -> None:
        assert AgentToken.__tablename__ == "agent_tokens"

    def test_primary_key(self) -> None:
        col = AgentToken.__table__.c["id"]
        assert col.primary_key
        assert isinstance(col.type, UUID)

    def test_required_columns(self) -> None:
        table = AgentToken.__table__
        assert isinstance(table.c["token_hash"].type, String)
        assert table.c["token_hash"].nullable is False
        assert table.c["token_hash"].unique is True

        assert isinstance(table.c["prefix"].type, String)
        assert table.c["prefix"].type.length == 8

        assert isinstance(table.c["expires_at"].type, DateTime)

    def test_foreign_key(self) -> None:
        table = AgentToken.__table__
        fk = next(iter(table.c["agent_id"].foreign_keys))
        assert fk.column.table.name == "agents"
        assert fk.ondelete == "SET NULL"

    def test_agent_id_nullable(self) -> None:
        col = AgentToken.__table__.c["agent_id"]
        assert col.nullable is True

    def test_indexes(self) -> None:
        indexes = {idx.name: idx for idx in AgentToken.__table__.indexes}
        assert "ix_agent_tokens_token_hash" in indexes
        assert list(indexes["ix_agent_tokens_token_hash"].columns.keys()) == ["token_hash"]

    def test_relationship(self) -> None:
        mapper = AgentToken.__mapper__
        assert any(r.key == "agent" for r in mapper.relationships)


class TestAgentMetricModel:
    """Verify the AgentMetric ORM model."""

    def test_table_name(self) -> None:
        assert AgentMetric.__tablename__ == "agent_metrics"

    def test_primary_key(self) -> None:
        col = AgentMetric.__table__.c["id"]
        assert col.primary_key
        assert isinstance(col.type, BigInteger)

    def test_required_columns(self) -> None:
        table = AgentMetric.__table__
        assert isinstance(table.c["agent_id"].type, UUID)
        assert isinstance(table.c["ts"].type, DateTime)
        assert table.c["ts"].nullable is False
        assert isinstance(table.c["tier"].type, String)
        assert table.c["tier"].type.length == 10

    def test_metric_columns_nullable(self) -> None:
        """GPU, vLLM, and system metrics should all be nullable."""
        table = AgentMetric.__table__
        nullable_cols = [
            "gpu_util_pct",
            "gpu_mem_used_mb",
            "gpu_temp_c",
            "gpu_power_w",
            "gpu_cache_pct",
            "running",
            "waiting",
            "total_requests",
            "prompt_tokens_total",
            "gen_tokens_total",
            "ttft_p50_ms",
            "ttft_p99_ms",
            "tps",
            "prefix_cache_hit",
            "error_rate",
            "trunc_rate",
            "ram_used_gb",
            "ram_total_gb",
            "cpu_pct",
            "load_1",
            "load_5",
            "load_15",
            "disk_used_gb",
            "disk_total_gb",
            "disk_pct",
        ]
        for col_name in nullable_cols:
            assert table.c[col_name].nullable is True, f"{col_name} should be nullable"

    def test_float_metric_types(self) -> None:
        table = AgentMetric.__table__
        float_cols = [
            "gpu_util_pct",
            "gpu_mem_used_mb",
            "gpu_temp_c",
            "gpu_power_w",
            "gpu_cache_pct",
            "ttft_p50_ms",
            "ttft_p99_ms",
            "tps",
            "prefix_cache_hit",
            "error_rate",
            "trunc_rate",
            "ram_used_gb",
            "ram_total_gb",
            "cpu_pct",
            "load_1",
            "load_5",
            "load_15",
            "disk_used_gb",
            "disk_total_gb",
            "disk_pct",
        ]
        for col_name in float_cols:
            assert isinstance(table.c[col_name].type, Float), f"{col_name} should be Float"

    def test_integer_metric_types(self) -> None:
        table = AgentMetric.__table__
        int_cols = [
            "running",
            "waiting",
            "total_requests",
            "prompt_tokens_total",
            "gen_tokens_total",
        ]
        for col_name in int_cols:
            assert isinstance(table.c[col_name].type, Integer), f"{col_name} should be Integer"

    def test_foreign_key(self) -> None:
        table = AgentMetric.__table__
        fk = next(iter(table.c["agent_id"].foreign_keys))
        assert fk.column.table.name == "agents"
        assert fk.ondelete == "CASCADE"

    def test_composite_index(self) -> None:
        indexes = {idx.name: idx for idx in AgentMetric.__table__.indexes}
        assert "ix_agent_metrics_agent_ts_tier" in indexes
        idx = indexes["ix_agent_metrics_agent_ts_tier"]
        assert list(idx.columns.keys()) == ["agent_id", "ts", "tier"]

    def test_relationship(self) -> None:
        mapper = AgentMetric.__mapper__
        assert any(r.key == "agent" for r in mapper.relationships)


class TestAgentLogModel:
    """Verify the AgentLog ORM model."""

    def test_table_name(self) -> None:
        assert AgentLog.__tablename__ == "agent_logs"

    def test_primary_key(self) -> None:
        col = AgentLog.__table__.c["id"]
        assert col.primary_key
        assert isinstance(col.type, BigInteger)

    def test_required_columns(self) -> None:
        table = AgentLog.__table__
        assert isinstance(table.c["agent_id"].type, UUID)
        assert isinstance(table.c["ts"].type, DateTime)
        assert isinstance(table.c["level"].type, Enum)
        assert isinstance(table.c["message"].type, Text)
        assert table.c["message"].nullable is False

    def test_optional_columns(self) -> None:
        table = AgentLog.__table__
        assert table.c["module"].nullable is True
        assert isinstance(table.c["module"].type, String)
        assert table.c["stack_trace"].nullable is True
        assert isinstance(table.c["stack_trace"].type, Text)

    def test_foreign_key(self) -> None:
        table = AgentLog.__table__
        fk = next(iter(table.c["agent_id"].foreign_keys))
        assert fk.column.table.name == "agents"
        assert fk.ondelete == "CASCADE"

    def test_composite_index(self) -> None:
        indexes = {idx.name: idx for idx in AgentLog.__table__.indexes}
        assert "ix_agent_logs_agent_ts_level" in indexes
        idx = indexes["ix_agent_logs_agent_ts_level"]
        assert list(idx.columns.keys()) == ["agent_id", "ts", "level"]

    def test_relationship(self) -> None:
        mapper = AgentLog.__mapper__
        assert any(r.key == "agent" for r in mapper.relationships)


class TestEnums:
    """Verify the Python enum definitions."""

    def test_agent_status_values(self) -> None:
        assert AgentStatus.ONLINE.value == "online"
        assert AgentStatus.OFFLINE.value == "offline"

    def test_token_status_values(self) -> None:
        assert TokenStatus.PENDING.value == "pending"
        assert TokenStatus.CLAIMED.value == "claimed"
        assert TokenStatus.EXPIRED.value == "expired"

    def test_log_level_values(self) -> None:
        assert LogLevel.DEBUG.value == "debug"
        assert LogLevel.INFO.value == "info"
        assert LogLevel.WARNING.value == "warning"
        assert LogLevel.ERROR.value == "error"

    def test_metric_tier_values(self) -> None:
        assert MetricTier.RAW.value == "raw"
        assert MetricTier.T10S.value == "t10s"
        assert MetricTier.T1M.value == "t1m"
        assert MetricTier.T10M.value == "t10m"
        assert MetricTier.T1H.value == "t1h"
        assert MetricTier.T6H.value == "t6h"


class TestModelInstantiation:
    """Verify models can be instantiated in memory."""

    def test_create_agent(self) -> None:
        agent = Agent(
            name="test-agent",
            hostname="gpu-01.example.com",
            agent_version="0.1.0",
            status=AgentStatus.OFFLINE,
        )
        assert agent.name == "test-agent"
        assert agent.hostname == "gpu-01.example.com"
        assert agent.status == AgentStatus.OFFLINE
        assert agent.id is None  # Not yet persisted

    def test_create_agent_token(self) -> None:
        token = AgentToken(
            token_hash="abc123",
            prefix="abc12345",
            status=TokenStatus.PENDING,
        )
        assert token.token_hash == "abc123"
        assert token.status == TokenStatus.PENDING
        assert token.agent_id is None

    def test_create_agent_metric(self) -> None:
        agent_id = uuid.uuid4()

        metric = AgentMetric(
            agent_id=agent_id,
            ts=datetime.now(UTC),
            tier="raw",
            gpu_util_pct=85.5,
            gpu_mem_used_mb=4096,
            running=3,
            waiting=2,
            ram_used_gb=16.0,
            ram_total_gb=64.0,
        )
        assert metric.agent_id == agent_id
        assert metric.gpu_util_pct == 85.5
        assert metric.running == 3

    def test_create_agent_log(self) -> None:
        agent_id = uuid.uuid4()

        log = AgentLog(
            agent_id=agent_id,
            ts=datetime.now(UTC),
            level=LogLevel.INFO,
            module="registration",
            message="Agent registered successfully",
        )
        assert log.level == LogLevel.INFO
        assert log.message == "Agent registered successfully"
        assert log.stack_trace is None


class TestModelRepr:
    """Verify __repr__ implementations are present and functional."""

    def test_agent_repr(self) -> None:
        agent = Agent(name="test", status=AgentStatus.ONLINE)
        r = repr(agent)
        assert "Agent" in r
        assert "test" in r
        assert "AgentStatus.ONLINE" in r or "online" in r

    def test_token_repr(self) -> None:
        token = AgentToken(prefix="abc12345", status=TokenStatus.PENDING)
        r = repr(token)
        assert "AgentToken" in r
        assert "abc12345" in r

    def test_metric_repr(self) -> None:
        metric = AgentMetric(agent_id=uuid.uuid4(), tier="raw")
        r = repr(metric)
        assert "AgentMetric" in r

    def test_log_repr(self) -> None:
        log = AgentLog(agent_id=uuid.uuid4(), level=LogLevel.INFO)
        r = repr(log)
        assert "AgentLog" in r
