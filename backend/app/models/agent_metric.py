"""AgentMetric ORM model.

Time-series GPU and system metrics emitted by agents at regular intervals.

Each row represents a single observation snapshot tagged with a retention
``tier`` that determines how long the data is kept (raw 24h → t6h forever).
Data is inserted by the backend metric ingestion and queried by the
dashboard for real-time and historical charts.

Partitioning by time range is deferred until the table reaches ~100M rows.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

if TYPE_CHECKING:
    from app.models.agent import Agent


class AgentMetric(Base):
    """A single metric observation snapshot from an agent.

    The ``tier`` column enables efficient queries by retention level
    (e.g., latest data = raw, historical = t1h/t6h).
    """

    __tablename__ = "agent_metrics"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="Sequential PK for high-frequency write throughput",
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Observation timestamp (set by the agent, not insert time)",
    )
    tier: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default="raw",
        comment="Retention tier: raw, t10s, t1m, t10m, t1h, t6h",
    )

    # --- GPU metrics ---
    gpu_util_pct: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="GPU utilization percentage 0–100"
    )
    gpu_mem_used_mb: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="GPU memory used in MB"
    )
    gpu_temp_c: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="GPU temperature in Celsius"
    )
    gpu_power_w: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="GPU power draw in watts"
    )
    gpu_cache_pct: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="GPU KV cache utilization percentage"
    )

    # --- vLLM metrics ---
    running: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Currently running requests"
    )
    waiting: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Queued / waiting requests"
    )
    total_requests: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Total requests since last reset"
    )
    prompt_tokens_total: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Total prompt tokens since reset"
    )
    gen_tokens_total: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Total generated tokens since reset"
    )
    ttft_p50_ms: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Time to first token p50 in ms"
    )
    ttft_p99_ms: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Time to first token p99 in ms"
    )
    tps: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Tokens per second throughput"
    )
    prefix_cache_hit: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Prefix cache hit rate 0–1"
    )
    error_rate: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Request error rate 0–1"
    )
    trunc_rate: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Request truncation rate 0–1"
    )

    # --- System metrics ---
    ram_used_gb: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Host RAM used in GB"
    )
    ram_total_gb: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Total host RAM in GB"
    )
    cpu_pct: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Host CPU utilization percentage"
    )
    load_1: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="System load average (1 minute)"
    )
    load_5: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="System load average (5 minutes)"
    )
    load_15: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="System load average (15 minutes)"
    )
    disk_used_gb: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Disk space used in GB"
    )
    disk_total_gb: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Total disk space in GB"
    )
    disk_pct: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Disk usage percentage"
    )

    # Relationships
    agent: Mapped[Agent] = relationship(
        "Agent",
        back_populates="metrics",
    )

    __table_args__ = (
        Index(
            "ix_agent_metrics_agent_ts_tier",
            "agent_id",
            "ts",
            "tier",
            postgresql_using="btree",
        ),
    )

    def __repr__(self) -> str:
        return f"<AgentMetric id={self.id} agent_id={self.agent_id} tier='{self.tier}'>"
