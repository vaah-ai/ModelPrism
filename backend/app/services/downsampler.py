"""Background metric downsampling and retention cleanup service.

Runs as an asyncio background task spawned during the FastAPI lifespan.
Periodically aggregates raw metric rows into lower-resolution tiered rows
(``t1m``, ``t10m``, ``t1h``, ``t6h``) and deletes rows that exceed the
configured retention window per tier.

Design:
- Downsampling is tier-cascading: raw → t1m → t10m → t1h → t6h.
  Each tier processes rows from the immediately finer-grained tier.
- A singleton lock (asyncio.Lock) prevents overlapping runs.
- Retention cleanup is additive — deleting from ``raw`` doesn't
  affect higher tiers.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionFactory
from app.models.agent_metric import AgentMetric

logger = logging.getLogger(__name__)

# ── Tier configuration ─────────────────────────────────────────────

_TIER_CHAIN: list[tuple[str, str, int]] = [
    # (source_tier, target_tier, bucket_window_seconds)
    ("raw", "t10s", 10),
    ("t10s", "t1m", 60),
    ("t1m", "t10m", 600),
    ("t10m", "t1h", 3600),
    ("t1h", "t6h", 21600),
]

_TIER_RETENTION: dict[str, timedelta] = {
    "raw": timedelta(hours=24),
    "t10s": timedelta(days=7),
    "t1m": timedelta(days=30),
    "t10m": timedelta(days=90),
    "t1h": timedelta(days=365),
    "t6h": timedelta.max,  # keep forever
}

# ── Singleton lock ─────────────────────────────────────────────────

_run_lock = asyncio.Lock()


async def run_downsampler() -> None:
    """Entry point for the background downsampling worker.

    Spawned via ``asyncio.create_task(run_downsampler())`` during the
    application lifespan. Runs every 60 seconds, aggregating and cleaning
    one tier level per cycle.
    """
    logger.info("Downsampler worker started")
    try:
        while True:
            await asyncio.sleep(60)
            await _run_downsample_pass()
    except asyncio.CancelledError:
        logger.info("Downsampler worker cancelled — shutting down")
        raise


async def _run_downsample_pass() -> None:
    """Execute one downsampling pass (aggregate + retention cleanup).

    Guarded by an asyncio.Lock so overlapping runs are prevented.
    """
    if _run_lock.locked():
        logger.warning("Previous downsampling pass still running — skipping this tick")
        return

    async with _run_lock:
        try:
            # 1. Aggregate: cascade through tiers
            for source_tier, target_tier, bucket_sec in _TIER_CHAIN:
                await _aggregate_tier(source_tier, target_tier, bucket_sec)

            # 2. Retention cleanup
            await _run_retention_cleanup()

            logger.debug("Downsampling pass completed")
        except Exception:
            logger.exception("Downsampling pass failed")


async def _aggregate_tier(
    source_tier: str,
    target_tier: str,
    bucket_seconds: int,
) -> None:
    """Aggregate rows from `source_tier` into `target_tier`.

    For each agent, groups rows by ``date_trunc`` time buckets and
    computes average/min/max for numeric columns. Writes a single
    aggregated row per agent per bucket with ``tier=target_tier``.
    """
    session = AsyncSessionFactory()
    try:
        now = datetime.now(UTC)

        # Find the latest already-aggregated timestamp for this tier
        # so we only process new data (reduces duplicate work).
        latest = await _get_latest_bucket(session, target_tier)
        range_start = latest if latest else now - timedelta(hours=1)

        # For 'raw' → t1m, only aggregate data older than the bucket
        # window to ensure the bucket is complete.
        cutoff = now - timedelta(seconds=bucket_seconds)

        if source_tier == "raw":
            # Direct SQL aggregation on raw columns
            stmt = text("""
                SELECT
                    agent_id,
                    date_trunc('second', ts) -
                      (EXTRACT('epoch' FROM ts)::bigint %% :bucket_sec) * INTERVAL '1 second'
                      AS bucket_ts,
                    AVG(gpu_util_pct) AS avg_gpu_util_pct,
                    MIN(gpu_util_pct) AS min_gpu_util_pct,
                    MAX(gpu_util_pct) AS max_gpu_util_pct,
                    AVG(gpu_mem_used_mb) AS avg_gpu_mem_used_mb,
                    MIN(gpu_mem_used_mb) AS min_gpu_mem_used_mb,
                    MAX(gpu_mem_used_mb) AS max_gpu_mem_used_mb,
                    AVG(gpu_temp_c) AS avg_gpu_temp_c,
                    AVG(gpu_power_w) AS avg_gpu_power_w,
                    AVG(gpu_cache_pct) AS avg_gpu_cache_pct,
                    AVG(ram_used_gb) AS avg_ram_used_gb,
                    AVG(cpu_pct) AS avg_cpu_pct,
                    AVG(disk_pct) AS avg_disk_pct,
                    AVG(ttft_p50_ms) AS avg_ttft_p50_ms,
                    AVG(ttft_p99_ms) AS avg_ttft_p99_ms,
                    AVG(tps) AS avg_tps,
                    AVG(running) AS avg_running,
                    AVG(waiting) AS avg_waiting,
                    AVG(prefix_cache_hit) AS avg_prefix_cache_hit,
                    AVG(error_rate) AS avg_error_rate,
                    AVG(trunc_rate) AS avg_trunc_rate
                FROM agent_metrics
                WHERE tier = :source_tier
                  AND ts >= :range_start
                  AND ts < :cutoff
                GROUP BY agent_id, bucket_ts
            """)
        else:
            # For higher tiers, already-aggregated tiers store per-field
            # averages.  This is a lossy approximation — for the simpler
            # MVP we average the averages, which gives us a coarse view.
            stmt = text("""
                SELECT
                    agent_id,
                    date_trunc('second', ts) -
                      (EXTRACT('epoch' FROM ts)::bigint %% :bucket_sec) * INTERVAL '1 second'
                      AS bucket_ts,
                    AVG(gpu_util_pct) AS avg_gpu_util_pct,
                    MIN(gpu_util_pct) AS min_gpu_util_pct,
                    MAX(gpu_util_pct) AS max_gpu_util_pct,
                    AVG(gpu_mem_used_mb) AS avg_gpu_mem_used_mb,
                    MIN(gpu_mem_used_mb) AS min_gpu_mem_used_mb,
                    MAX(gpu_mem_used_mb) AS max_gpu_mem_used_mb,
                    AVG(gpu_temp_c) AS avg_gpu_temp_c,
                    AVG(gpu_power_w) AS avg_gpu_power_w,
                    AVG(gpu_cache_pct) AS avg_gpu_cache_pct,
                    AVG(ram_used_gb) AS avg_ram_used_gb,
                    AVG(cpu_pct) AS avg_cpu_pct,
                    AVG(disk_pct) AS avg_disk_pct
                FROM agent_metrics
                WHERE tier = :source_tier
                  AND ts >= :range_start
                  AND ts < :cutoff
                GROUP BY agent_id, bucket_ts
            """)

        params = {
            "source_tier": source_tier,
            "range_start": range_start,
            "cutoff": cutoff,
            "bucket_sec": bucket_seconds,
        }
        result = await session.execute(stmt, params)
        rows = result.fetchall()

        if not rows:
            logger.debug(
                "No rows to aggregate for %s → %s (from %s to %s)",
                source_tier,
                target_tier,
                range_start.isoformat(),
                cutoff.isoformat(),
            )
            return

        # Write aggregated rows
        written = 0
        for row in rows:
            bucket_ts = row.bucket_ts
            if bucket_ts.tzinfo is None:
                bucket_ts = bucket_ts.replace(tzinfo=UTC)

            agg = AgentMetric(
                agent_id=row.agent_id,
                ts=bucket_ts,
                tier=target_tier,
                gpu_util_pct=row.avg_gpu_util_pct,
                gpu_mem_used_mb=row.avg_gpu_mem_used_mb,
                gpu_temp_c=row.avg_gpu_temp_c,
                gpu_power_w=row.avg_gpu_power_w,
                gpu_cache_pct=row.avg_gpu_cache_pct,
                ram_used_gb=row.avg_ram_used_gb,
                cpu_pct=row.avg_cpu_pct,
                disk_pct=row.avg_disk_pct,
                ttft_p50_ms=getattr(row, "avg_ttft_p50_ms", None),
                ttft_p99_ms=getattr(row, "avg_ttft_p99_ms", None),
                tps=getattr(row, "avg_tps", None),
                running=getattr(row, "avg_running", None),
                waiting=getattr(row, "avg_waiting", None),
                prefix_cache_hit=getattr(row, "avg_prefix_cache_hit", None),
                error_rate=getattr(row, "avg_error_rate", None),
                trunc_rate=getattr(row, "avg_trunc_rate", None),
            )
            session.add(agg)
            written += 1

        await session.commit()
        logger.debug(
            "Aggregated %d rows: %s → %s (bucket=%ds)",
            written,
            source_tier,
            target_tier,
            bucket_seconds,
        )
    except Exception:
        await session.rollback()
        logger.exception(
            "Failed to aggregate %s → %s",
            source_tier,
            target_tier,
        )
    finally:
        await session.close()


async def _get_latest_bucket(
    session: AsyncSession,
    tier: str,
) -> datetime | None:
    """Find the most recent timestamp for a given tier.

    Used to avoid re-aggregating already-processed time windows.
    """
    stmt = (
        select(AgentMetric.ts)
        .where(AgentMetric.tier == tier)
        .order_by(AgentMetric.ts.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    val = result.scalar_one_or_none()
    if val is not None:
        return val
    return None


async def _run_retention_cleanup() -> None:
    """Delete rows that exceed the retention window for each tier.

    Runs in batches of 10,000 rows with short sleeps between batches
    to avoid long-running locks.
    """
    now = datetime.now(UTC)
    total_deleted = 0

    for tier, retention in _TIER_RETENTION.items():
        if retention == timedelta.max:
            continue  # keep forever

        cutoff = now - retention
        batch_size = 10_000
        deleted = await _delete_expired_rows(tier, cutoff, batch_size)
        total_deleted += deleted
        if deleted > 0:
            logger.debug("Retention cleanup for %s: deleted %d rows", tier, deleted)

    if total_deleted > 0:
        logger.info("Retention cleanup completed: %d rows deleted", total_deleted)


async def _delete_expired_rows(
    tier: str,
    cutoff: datetime,
    batch_size: int,
) -> int:
    """Delete expired rows for a single tier in batches.

    Returns the total number of rows deleted.
    """
    session = AsyncSessionFactory()
    try:
        total = 0
        while True:
            # Select a batch of IDs to delete
            stmt = (
                select(AgentMetric.id)
                .where(AgentMetric.tier == tier, AgentMetric.ts < cutoff)
                .limit(batch_size)
            )
            result = await session.execute(stmt)
            ids = [r[0] for r in result.fetchall()]
            if not ids:
                break

            # Delete the batch
            delete_stmt = delete(AgentMetric).where(AgentMetric.id.in_(ids))
            await session.execute(delete_stmt)
            await session.commit()
            total += len(ids)

            # Brief sleep between batches to avoid long-running locks
            await asyncio.sleep(0.1)

        return total
    except Exception:
        await session.rollback()
        logger.exception("Failed to delete expired rows for tier %s", tier)
        return 0
    finally:
        await session.close()
