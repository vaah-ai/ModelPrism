"""Metric ingestion and query service.

Provides the core operations for receiving metrics from the agent WebSocket
pipeline and querying historical data for the dashboard.

Ingestion flow: WebSocket handler calls ``enqueue()`` which buffers rows
in memory. A periodic flush writes buffered rows to PostgreSQL. Queries
read directly from the ``agent_metrics`` table, auto-selecting the
appropriate retention tier based on the requested time range.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionFactory
from app.models.agent_metric import AgentMetric
from app.models.enums import MetricTier

logger = logging.getLogger(__name__)

# ── Range → tier mapping ────────────────────────────────────────────

_RANGE_TIER_MAP: dict[str, str] = {
    "live": "redis",
    "5m": "raw",
    "15m": "raw",
    "1h": "raw",
    "6h": "t1m",
    "12h": "t1m",
    "1d": "t1m",
    "3d": "t10m",
    "1w": "t10m",
    "1M": "t1h",
    "3M": "t1h",
    "6M": "t1h",
    "1y": "t6h",
}

_VALID_RANGES = frozenset(_RANGE_TIER_MAP.keys())

# ── Retention windows per tier (in hours) ───────────────────────────

_TIER_RETENTION_HOURS: dict[str, int] = {
    "raw": 24,
    "t10s": 168,  # 7 days
    "t1m": 720,  # 30 days
    "t10m": 2160,  # 90 days
    "t1h": 8760,  # 1 year
    "t6h": 0,  # forever
}

# ── Ingest buffer dataclass ─────────────────────────────────────────


@dataclass
class MetricWrite:
    """A single buffered metric row waiting to be flushed to PostgreSQL."""

    agent_id: UUID
    ts: datetime
    tier: str
    gpu_util_pct: float | None = None
    gpu_mem_used_mb: float | None = None
    gpu_temp_c: float | None = None
    gpu_power_w: float | None = None
    gpu_cache_pct: float | None = None
    running: int | None = None
    waiting: int | None = None
    total_requests: int | None = None
    prompt_tokens_total: int | None = None
    gen_tokens_total: int | None = None
    ttft_p50_ms: float | None = None
    ttft_p99_ms: float | None = None
    tps: float | None = None
    prefix_cache_hit: float | None = None
    error_rate: float | None = None
    trunc_rate: float | None = None
    ram_used_gb: float | None = None
    ram_total_gb: float | None = None
    cpu_pct: float | None = None
    load_1: float | None = None
    load_5: float | None = None
    load_15: float | None = None
    disk_used_gb: float | None = None
    disk_total_gb: float | None = None
    disk_pct: float | None = None


# ── Service ─────────────────────────────────────────────────────────


class MetricIngestionService:
    """Buffered metric ingestion and query service.

    The service maintains a per-agent buffer of ``MetricWrite`` rows.
    It is flushed either when the buffer reaches 100 rows or on a
    periodic ticker (every 5 seconds), whichever comes first.
    """

    def __init__(self) -> None:
        self._buffer: dict[UUID, list[MetricWrite]] = defaultdict(list)
        self._redis_client: Any = None

    def set_redis(self, redis_client: Any) -> None:
        """Inject the Redis client after initialisation (lifespan hook)."""
        self._redis_client = redis_client

    # ── Enqueue ─────────────────────────────────────────────────

    def enqueue(
        self,
        agent_id: UUID,
        ts: datetime,
        *,
        tier: str = MetricTier.RAW,
        gpu_util_pct: float | None = None,
        gpu_mem_used_mb: float | None = None,
        gpu_temp_c: float | None = None,
        gpu_power_w: float | None = None,
        gpu_cache_pct: float | None = None,
        running: int | None = None,
        waiting: int | None = None,
        total_requests: int | None = None,
        prompt_tokens_total: int | None = None,
        gen_tokens_total: int | None = None,
        ttft_p50_ms: float | None = None,
        ttft_p99_ms: float | None = None,
        tps: float | None = None,
        prefix_cache_hit: float | None = None,
        error_rate: float | None = None,
        trunc_rate: float | None = None,
        ram_used_gb: float | None = None,
        ram_total_gb: float | None = None,
        cpu_pct: float | None = None,
        load_1: float | None = None,
        load_5: float | None = None,
        load_15: float | None = None,
        disk_used_gb: float | None = None,
        disk_total_gb: float | None = None,
        disk_pct: float | None = None,
    ) -> None:
        """Buffer a metric row for batch insertion.

        Call this from the WebSocket handler for each incoming
        ``metrics`` or ``vllm_metrics`` message.
        """
        row = MetricWrite(
            agent_id=agent_id,
            ts=ts,
            tier=tier,
            gpu_util_pct=gpu_util_pct,
            gpu_mem_used_mb=gpu_mem_used_mb,
            gpu_temp_c=gpu_temp_c,
            gpu_power_w=gpu_power_w,
            gpu_cache_pct=gpu_cache_pct,
            running=running,
            waiting=waiting,
            total_requests=total_requests,
            prompt_tokens_total=prompt_tokens_total,
            gen_tokens_total=gen_tokens_total,
            ttft_p50_ms=ttft_p50_ms,
            ttft_p99_ms=ttft_p99_ms,
            tps=tps,
            prefix_cache_hit=prefix_cache_hit,
            error_rate=error_rate,
            trunc_rate=trunc_rate,
            ram_used_gb=ram_used_gb,
            ram_total_gb=ram_total_gb,
            cpu_pct=cpu_pct,
            load_1=load_1,
            load_5=load_5,
            load_15=load_15,
            disk_used_gb=disk_used_gb,
            disk_total_gb=disk_total_gb,
            disk_pct=disk_pct,
        )
        agent_rows = self._buffer[agent_id]
        agent_rows.append(row)

        # Flush if buffer reaches 100 rows for this agent
        if len(agent_rows) >= 100:
            logger.debug("Buffer for agent %s reached 100 rows — scheduling flush", agent_id)

    def enqueue_vllm(
        self,
        agent_id: UUID,
        ts: datetime,
        *,
        tier: str = MetricTier.RAW,
        running: int | None = None,
        waiting: int | None = None,
        total_requests: int | None = None,
        prompt_tokens_total: int | None = None,
        gen_tokens_total: int | None = None,
        ttft_p50_ms: float | None = None,
        ttft_p99_ms: float | None = None,
        tps: float | None = None,
        gpu_cache_pct: float | None = None,
        prefix_cache_hit: float | None = None,
        error_rate: float | None = None,
        trunc_rate: float | None = None,
    ) -> None:
        """Enqueue a vLLM metrics snapshot (merged into the same metric row)."""
        self.enqueue(
            agent_id=agent_id,
            ts=ts,
            tier=tier,
            running=running,
            waiting=waiting,
            total_requests=total_requests,
            prompt_tokens_total=prompt_tokens_total,
            gen_tokens_total=gen_tokens_total,
            ttft_p50_ms=ttft_p50_ms,
            ttft_p99_ms=ttft_p99_ms,
            tps=tps,
            gpu_cache_pct=gpu_cache_pct,
            prefix_cache_hit=prefix_cache_hit,
            error_rate=error_rate,
            trunc_rate=trunc_rate,
        )

    # ── Flush ───────────────────────────────────────────────────

    async def flush(self) -> int:
        """Flush all buffered rows to PostgreSQL.

        Uses a single multi-row INSERT per flush. Returns the number
        of rows flushed (0 if buffer was empty).
        """
        if not self._buffer:
            return 0

        all_rows: list[MetricWrite] = []
        for rows in self._buffer.values():
            all_rows.extend(rows)

        total = len(all_rows)
        logger.debug("Flushing %d metric rows to PostgreSQL", total)

        try:
            session = AsyncSessionFactory()
        except Exception:
            logger.exception("Failed to create DB session for flush — discarding buffer")
            self._buffer.clear()
            return 0

        try:
            session.add_all(
                [
                    AgentMetric(
                        agent_id=row.agent_id,
                        ts=row.ts,
                        tier=row.tier,
                        gpu_util_pct=row.gpu_util_pct,
                        gpu_mem_used_mb=row.gpu_mem_used_mb,
                        gpu_temp_c=row.gpu_temp_c,
                        gpu_power_w=row.gpu_power_w,
                        gpu_cache_pct=row.gpu_cache_pct,
                        running=row.running,
                        waiting=row.waiting,
                        total_requests=row.total_requests,
                        prompt_tokens_total=row.prompt_tokens_total,
                        gen_tokens_total=row.gen_tokens_total,
                        ttft_p50_ms=row.ttft_p50_ms,
                        ttft_p99_ms=row.ttft_p99_ms,
                        tps=row.tps,
                        prefix_cache_hit=row.prefix_cache_hit,
                        error_rate=row.error_rate,
                        trunc_rate=row.trunc_rate,
                        ram_used_gb=row.ram_used_gb,
                        ram_total_gb=row.ram_total_gb,
                        cpu_pct=row.cpu_pct,
                        load_1=row.load_1,
                        load_5=row.load_5,
                        load_15=row.load_15,
                        disk_used_gb=row.disk_used_gb,
                        disk_total_gb=row.disk_total_gb,
                        disk_pct=row.disk_pct,
                    )
                    for row in all_rows
                ]
            )
            await session.commit()
            self._buffer.clear()
            logger.debug("Successfully flushed %d metric rows", total)
            return total
        except Exception:
            await session.rollback()
            logger.exception("Failed to flush %d metric rows — discarding buffer", total)
            self._buffer.clear()
            return 0
        finally:
            await session.close()

    # ── Query ───────────────────────────────────────────────────

    async def query_metrics(
        self,
        agent_id: UUID,
        range_key: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[dict[str, Any]]:
        """Query historical metrics for a given agent and time range.

        Returns a list of dicts with keys ``ts`` and all metric fields.
        The ``live`` range is served from Redis (no DB query). All
        other ranges query the ``agent_metrics`` table.
        """
        if range_key not in _VALID_RANGES:
            return []

        # Live range → Redis
        if range_key == "live":
            return await self._get_live_from_redis(agent_id)

        # Drop-in session for standalone calls
        close_session = session is None
        if session is None:
            session = AsyncSessionFactory()

        try:
            range_start = _range_start(range_key)
            stmt = (
                select(AgentMetric)
                .where(
                    AgentMetric.agent_id == agent_id,
                    AgentMetric.ts >= range_start,
                )
                .order_by(AgentMetric.ts.asc())
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [_metric_row_to_dict(r) for r in rows]
        finally:
            if close_session:
                await session.close()

    async def get_latest_metrics(
        self,
        agent_id: UUID,
    ) -> dict[str, Any] | None:
        """Return the latest metric snapshot from Redis.

        This is the primary data source for the dashboard's live view.
        Returns ``None`` if no metrics have been received yet.
        """
        rows = await self._get_live_from_redis(agent_id)
        return rows[0] if rows else None

    async def get_agent_metric_summary(
        self,
        agent_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> dict[str, Any]:
        """Compute summary statistics for dashboard overview cards.

        Returns current GPU util, VRAM usage, running/waiting requests,
        and error rate for the most recent raw metric row.
        """
        close_session = session is None
        if session is None:
            try:
                session = AsyncSessionFactory()
            except Exception:
                logger.debug("No DB session available for metric summary — returning None fields")
                return {
                    "gpu_util_pct": None,
                    "gpu_mem_used_mb": None,
                    "running": None,
                    "waiting": None,
                    "error_rate": None,
                    "ts": None,
                }

        try:
            stmt = (
                select(AgentMetric)
                .where(
                    AgentMetric.agent_id == agent_id,
                    AgentMetric.tier == MetricTier.RAW,
                )
                .order_by(AgentMetric.ts.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()

            if row is None:
                return {
                    "gpu_util_pct": None,
                    "gpu_mem_used_mb": None,
                    "running": None,
                    "waiting": None,
                    "error_rate": None,
                    "ts": None,
                }

            return {
                "gpu_util_pct": row.gpu_util_pct,
                "gpu_mem_used_mb": row.gpu_mem_used_mb,
                "running": row.running,
                "waiting": row.waiting,
                "error_rate": row.error_rate,
                "ts": row.ts.isoformat() if row.ts else None,
            }
        except Exception:
            logger.debug("Database error in metric summary — returning None fields")
            return {
                "gpu_util_pct": None,
                "gpu_mem_used_mb": None,
                "running": None,
                "waiting": None,
                "error_rate": None,
                "ts": None,
            }
        finally:
            if close_session:
                await session.close()

    # ── Internal helpers ────────────────────────────────────────

    async def _get_live_from_redis(
        self,
        agent_id: UUID,
    ) -> list[dict[str, Any]]:
        """Fetch the latest metric snapshot from Redis."""
        if self._redis_client is None:
            return []

        try:
            key = f"agent:{agent_id}:latest_metrics"
            raw = await self._redis_client.get(key)
            if raw is None:
                return []
            data = json.loads(raw) if isinstance(raw, bytes) else json.loads(raw)
            return [data] if isinstance(data, dict) else data
        except Exception:
            logger.debug("Failed to fetch live metrics from Redis for agent %s", agent_id)
            return []

    @property
    def buffer_size(self) -> int:
        """Return total buffered rows across all agents."""
        return sum(len(rows) for rows in self._buffer.values())


# ── Background flush loop ─────────────────────────────────────────


async def run_flush_loop(service: MetricIngestionService) -> None:
    """Periodic background task that flushes the metric ingestion buffer.

    Spawned via ``asyncio.create_task(run_flush_loop(metric_service))``
    during the application lifespan. Flushes every 5 seconds.
    """
    logger.info("Metric flush loop started")
    try:
        while True:
            await asyncio.sleep(5)
            flushed = await service.flush()
            if flushed > 0:
                logger.debug("Periodic flush: %d rows written", flushed)
    except asyncio.CancelledError:
        logger.info("Metric flush loop cancelled — flushing remaining rows")
        await service.flush()
        raise


# ── Standalone helpers ──────────────────────────────────────────────


def _range_start(range_key: str) -> datetime:
    """Compute the start datetime for a given range key."""
    now = datetime.now(UTC)
    durations: dict[str, timedelta] = {
        "5m": timedelta(minutes=5),
        "15m": timedelta(minutes=15),
        "1h": timedelta(hours=1),
        "6h": timedelta(hours=6),
        "12h": timedelta(hours=12),
        "1d": timedelta(days=1),
        "3d": timedelta(days=3),
        "1w": timedelta(weeks=1),
        "1M": timedelta(days=30),
        "3M": timedelta(days=90),
        "6M": timedelta(days=180),
        "1y": timedelta(days=365),
    }
    delta = durations.get(range_key, timedelta(hours=1))
    return now - delta


def _metric_row_to_dict(row: AgentMetric) -> dict[str, Any]:
    """Convert an AgentMetric ORM row to a flat dictionary for JSON serialisation."""
    return {
        "ts": row.ts.isoformat() if row.ts else None,
        "tier": row.tier,
        "gpu_util_pct": row.gpu_util_pct,
        "gpu_mem_used_mb": row.gpu_mem_used_mb,
        "gpu_temp_c": row.gpu_temp_c,
        "gpu_power_w": row.gpu_power_w,
        "gpu_cache_pct": row.gpu_cache_pct,
        "running": row.running,
        "waiting": row.waiting,
        "total_requests": row.total_requests,
        "prompt_tokens_total": row.prompt_tokens_total,
        "gen_tokens_total": row.gen_tokens_total,
        "ttft_p50_ms": row.ttft_p50_ms,
        "ttft_p99_ms": row.ttft_p99_ms,
        "tps": row.tps,
        "prefix_cache_hit": row.prefix_cache_hit,
        "error_rate": row.error_rate,
        "trunc_rate": row.trunc_rate,
        "ram_used_gb": row.ram_used_gb,
        "ram_total_gb": row.ram_total_gb,
        "cpu_pct": row.cpu_pct,
        "load_1": row.load_1,
        "load_5": row.load_5,
        "load_15": row.load_15,
        "disk_used_gb": row.disk_used_gb,
        "disk_total_gb": row.disk_total_gb,
        "disk_pct": row.disk_pct,
    }


# ── Singleton instance (initialised in lifespan) ────────────────────

metric_service = MetricIngestionService()
"""Module-level singleton injected during application startup."""
