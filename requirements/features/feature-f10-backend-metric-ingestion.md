# F10: Backend metric ingestion

## Metadata
- **ID:** F10
- **Phase:** Foundation
- **Effort:** Large
- **Dependencies:** F1, F3, F7, F9
- **Acceptance Criteria Count:** 8

## Description

Receive, validate, store, and downsample real-time GPU/system/vLLM metric snapshots pushed by modelprism-agent instances over WebSocket, and expose the ingested data through REST endpoints for dashboard historical queries and live WebSocket broadcast. Every agent registered with the platform (F6) maintains a persistent WebSocket connection (F7) and pushes a metrics message every 2 seconds (F9). The backend must handle these high-frequency writes without blocking or dropping data under load, persist raw snapshots to the `agent_metrics` table defined in F3, and run a background downsampling pipeline that aggregates raw 2-second data into lower-resolution time series (1-minute buckets kept 30 days, 5-minute buckets kept 1 year) so dashboard time-range selectors (F17) can serve both live and historical views with predictable query performance.

The ingestion pipeline comprises three layers. The **WebSocket receiver** in `backend/app/ws/agent_ws.py` parses incoming `"type": "metrics"` and `"type": "vllm_metrics"` messages, validates them against shared Pydantic schemas defined in `common/modelprism_common/schemas/metrics.py`, and initiates a database write. The **bulk-write layer** in a new `backend/app/services/metric_ingestion_service.py` batches incoming metric rows in memory per-agent and flushes them to PostgreSQL at configurable intervals (default every 5 seconds or every 100 rows, whichever comes first) using efficient multi-row `INSERT` statements, avoiding per-row round trips. The **downsampling engine** in `backend/app/services/downsampler_service.py` runs as an asyncio background task, waking on a schedule to aggregate raw metrics into materialised summary buckets (1-minute avg/min/max/P50/P95/P99 counts over the window), write them to dedicated aggregate tables (`metric_aggregates_1m`, `metric_aggregates_5m`), and delete raw rows that exceed the configured retention window. This prevents the `agent_metrics` table from growing unbounded while preserving semantic fidelity for dashboard queries at longer time scales.

The feature integrates with the real-time dashboard broadcast system (F16): immediately after persisting a batch, the ingestion service publishes the fresh metrics to Redis pub/sub, which the dashboard WebSocket handler consumes and forwards to connected browser clients. Historical metric queries use `GET /api/metrics/{agent_id}` (F17) which reads from the appropriate table depending on the requested time range — raw `agent_metrics` for the last hour, `metric_aggregates_1m` for up to 30 days, and `metric_aggregates_5m` for up to 1 year. This tiered read path keeps query latency under 500 ms for any time range without requiring TimescaleDB or external time-series infrastructure.

## Concrete Examples (Specification by Example)

### Example 1: Agent Pushes a Metrics Snapshot via WebSocket

- **Input:** Agent `ag_cyan_koala_42` (workspace `ws_abc`) sends the following JSON message over its WebSocket connection at `2026-06-07T12:00:02.000Z`:

```json
{
  "type": "metrics",
  "ts": "2026-06-07T12:00:02.000Z",
  "gpu": [
    {
      "index": 0,
      "util_pct": 87.2,
      "mem_used_mb": 42100,
      "mem_total_mb": 81200,
      "temp_c": 71.0,
      "power_w": 285.0
    },
    {
      "index": 1,
      "util_pct": 92.1,
      "mem_used_mb": 75600,
      "mem_total_mb": 81200,
      "temp_c": 73.0,
      "power_w": 300.0
    }
  ],
  "gpu_cache_pct": 62.1,
  "ram_used_gb": 128.0,
  "ram_total_gb": 512.0,
  "cpu_pct": 34.2,
  "load_1": 12.5,
  "load_5": 10.1,
  "load_15": 8.2,
  "disk_used_gb": 548.0,
  "disk_total_gb": 2048.0,
  "disk_pct": 26.8
}
```

- **Action:** The WebSocket handler in `backend/app/ws/agent_ws.py` receives the message, deserialises it, validates it against `MetricSnapshot` from `common/modelprism_common/schemas/metrics.py`, extracts the agent's `workspace_id` from the connection's authenticated session, and enqueues a `MetricWrite` dataclass into the per-agent batch buffer. After 5 seconds (or when the buffer reaches 100 rows) the buffer flush writes a multi-row `INSERT` into `agent_metrics`.
- **Expected Output:** A single `INSERT INTO agent_metrics (agent_id, workspace_id, ts, data) VALUES (...)` bulk statement inserts one row. The row contains:
  - `agent_id`: `550e8400-e29b-41d4-a716-446655440000` (the agent UUID)
  - `workspace_id`: `7c9d1b2a-3e4f-5a6b-7c8d-9e0f1a2b3c4d`
  - `ts`: `2026-06-07T12:00:02.000Z` (ISO 8601 with timezone)
  - `data`: The full JSON payload including the nested `gpu` array, system stats, and cache utilisation, stored as JSONB. The row is committed within 100 ms of the buffer flush trigger. Immediately after commit, the ingestion service publishes the same payload to the Redis channel `metrics:ws_abc` for dashboard broadcast.

### Example 2: Agent Pushes vLLM Instance Metrics

- **Input:** Agent `ag_cyan_koala_42` sends the following message over WebSocket at `2026-06-07T12:00:02.000Z`:

```json
{
  "type": "vllm_metrics",
  "instance_id": "inst_001",
  "ts": "2026-06-07T12:00:02.000Z",
  "model_name": "Qwen2.5-72B-Instruct",
  "running": 3,
  "waiting": 2,
  "total_requests": 15234,
  "prompt_tokens_total": 450000000,
  "gen_tokens_total": 120000000,
  "ttft_p50_ms": 280,
  "ttft_p99_ms": 850,
  "gpu_cache_pct": 62.5,
  "tps": 1850.3,
  "prefix_cache_hit_pct": 34.2,
  "error_pct": 0.02,
  "trunc_pct": 1.2,
  "server_start_ts": "2026-06-05T08:00:00.000Z"
}
```

- **Action:** The handler routes the message by `"type": "vllm_metrics"` to the same batch buffer (vLLM metrics are a variant of agent metrics rather than a separate table; they merge into the same `agent_metrics.data` JSONB payload but with an additional `data.vllm` namespace). The batch buffer stores the row alongside GPU/system rows.
- **Expected Output:** The same `INSERT INTO agent_metrics` statement includes a row with `data` containing the full vLLM payload nested under `{"vllm": {...}}`. The `data` column is a single JSONB document that includes both the GPU/system fields and the vLLM fields so that neither the raw table nor the downsampling engine needs table joins to serve complete metric snapshots.

### Example 3: Dashboard Queries 1-Hour Historical Metrics

- **Input:** A user opens the single-server dashboard for agent `ag_cyan_koala_42` and selects the "1h" time range via the `TimeRangeSelector` component.
- **Action:** The frontend calls `GET /api/metrics/550e8400-e29b-41d4-a716-446655440000?range=1h` with `Authorization: Bearer <jwt>`. The backend route handler extracts the workspace from the JWT, verifies the agent belongs to that workspace (F34), and routes the query to the raw `agent_metrics` table because the range is under the 24-hour raw retention threshold. It queries `SELECT ts, data FROM agent_metrics WHERE agent_id = :aid AND workspace_id = :wid AND ts >= NOW() - INTERVAL '1 hour' ORDER BY ts ASC`.
- **Expected Output:** A JSON:API response with up to 1,800 rows (1 per 2 seconds for 1 hour). The response is paginated with `page[limit]=500` default; the frontend fetches subsequent pages for ranges longer than ~15 minutes at 2-second resolution. Each row's `attributes.data` object is the stored JSONB payload (GPU array, system stats, vLLM fields if present). Overall query latency on the backend is under 200 ms for the first page.

### Example 4: Downsampling Run Aggregates Raw Data

- **Input:** The downsampling cron job triggers at `2026-06-07T12:00:05.000Z` (5 seconds past the minute). A worker picks up the `metric_aggregates_1m` bucket for minute `2026-06-07T11:59:00.000Z` (the just-completed minute).
- **Action:** The downsampling engine queries `SELECT data FROM agent_metrics WHERE agent_id = :aid AND ts >= '2026-06-07T11:59:00' AND ts < '2026-06-07T12:00:00'` for every agent that has metrics in that window. For each agent, it computes per-field aggregates: `avg(gpu_util_pct)`, `min(gpu_util_pct)`, `max(gpu_util_pct)`, `p50(gpu_util_pct)`, `p95(gpu_util_pct)`, `p99(gpu_util_pct)`, and similarly for `vram_used_gb`, `ttft_p99_ms`, `tps`, `running_requests`, `waiting_requests`, `gpu_cache_pct`, `cpu_pct`, `ram_used_gb`, and `disk_pct`. It writes a single row per agent per 1-minute window to `metric_aggregates_1m` with the aggregate JSONB payload. It then deletes raw rows from `agent_metrics` that are older than the workspace's raw-retention threshold (default 24 hours).
- **Expected Output:** The `metric_aggregates_1m` table now contains one row for agent `ag_cyan_koala_42` with `bucket_ts = '2026-06-07T11:59:00Z'` and `data` containing aggregate fields computed from 30 raw snapshots (60 seconds / 2-second interval). The 5-minute aggregates cascade from the 1-minute table rather than re-reading raw rows.

### Example 5: Retention Cleanup Removes Expired Raw Data

- **Input:** The retention enforcement job (part of the downsampling runner) executes at `2026-06-08T12:00:00.000Z`. A workspace `ws_abc` has its raw-metrics retention configured to 24 hours. All `agent_metrics` rows with `ts < '2026-06-07T12:00:00Z'` and `workspace_id = 'ws_abc'` are eligible for deletion.
- **Action:** The cleanup query runs as a batched `DELETE FROM agent_metrics WHERE workspace_id = :wid AND ts < :cutoff`. To avoid long-running locks, the deletion runs in chunks of 10,000 rows with a 100 ms sleep between batches via an asyncio `sleep()`.
- **Expected Output:** Approximately 43,200 rows per agent (1 agent × 24 hours × 1,800 rows/hour) are deleted from `agent_metrics`. The `metric_aggregates_1m` and `metric_aggregates_5m` tables are unaffected — their retention (30 days and 1 year respectively) is enforced by a separate, slower cleanup pass. The deletion completes within 5 seconds for a workspace with 3 agents (~130K rows to remove). The PostgreSQL `autovacuum` processes the table in the background.

## Acceptance Criteria

- **ACF10-1: WebSocket metrics messages are validated against shared Pydantic schemas before ingestion** — Every incoming `"type": "metrics"` and `"type": "vllm_metrics"` message is deserialised and validated against `MetricSnapshot` and `VllmMetricSnapshot` from `common/modelprism_common/schemas/metrics.py` before enqueuing. Malformed messages (missing required fields `ts`, `gpu`, or `type`; `gpu` array with missing `index` or `util_pct`; non-numeric `ttft_p99_ms`; invalid ISO 8601 timestamp) are rejected with a JSON error response on the WebSocket (`{"error": "VALIDATION_ERROR", "detail": "..."}`), logged at `WARNING` level with the agent ID, and the connection remains open. The ingestion pipeline never writes a row with NULL or default values for required metric fields, and never raises an unhandled exception from malformed input.

- **ACF10-2: Metrics are buffered per-agent and flushed in bulk INSERTs** — Incoming validated metric rows accumulate in an in-memory per-agent buffer (`defaultdict[UUID, list[MetricWrite]]`). The buffer is flushed to PostgreSQL under either condition: buffer reaches 100 rows for any single agent, or a periodic ticker fires every 5 seconds. On flush, all buffered rows across all agents are written in a single `executemany` or multi-row `INSERT INTO agent_metrics (agent_id, workspace_id, ts, data) VALUES (...)` statement within one database transaction. After a successful commit, the buffer is cleared. If the commit fails (e.g., `IntegrityError` from a bad foreign key), the exception is logged at `ERROR` level, the buffer for the offending agent is discarded (to prevent perpetual retry), and the other buffers are flushed in a subsequent retry. The buffer may lose at most 5 seconds of data on a crash, which is acceptable given the 2-second push cadence.

- **ACF10-3: After ingestion, metrics are immediately published to Redis pub/sub for dashboard broadcast** — As part of the flush handler, for every row written, the ingestion service publishes the metric payload to the Redis channel `metrics:<workspace_id>` using `PUBLISH` (or an equivalent pipelined `RPUSH` + `PUBLISH` combination). The dashboard WebSocket handler in `backend/app/ws/dashboard_ws.py` subscribes to this channel and forwards each message verbatim to all connected browser clients for the given workspace. The end-to-end latency from agent push to browser client is consistently under 500 ms (p99) under normal network conditions. Redis pub/sub delivery is fire-and-forget — a dashboard client that disconnects and reconnects misses the metrics published during the gap and must backfill via the historical REST endpoint.

- **ACF10-4: The downsampling engine creates 1-minute and 5-minute aggregate tables with correct schemas** — Two new database tables are created by an Alembic migration:
  1. `metric_aggregates_1m`: Columns `id` (BIGSERIAL PK), `agent_id` (UUID FK → `agents.id` ON DELETE CASCADE, NOT NULL), `workspace_id` (UUID FK → `workspaces.id` ON DELETE CASCADE, NOT NULL), `bucket_ts` (TIMESTAMPTZ, NOT NULL — truncated to minute boundary), `data` (JSONB, NOT NULL — aggregated fields: `avg`, `min`, `max`, `p50`, `p95`, `p99` for all numeric metric keys). Unique constraint on `(agent_id, bucket_ts)`. Index on `(agent_id, bucket_ts DESC)` and `(workspace_id, bucket_ts DESC)`.
  2. `metric_aggregates_5m`: Identical structure to `metric_aggregates_1m` but with `bucket_ts` truncated to 5-minute boundaries. Unique constraint on `(agent_id, bucket_ts)`.
  
  Both tables are created before the downsampling runner starts. The migration is reversible (`downgrade` drops them cleanly).

- **ACF10-5: Downsampling runs at correct cadence with correct aggregation logic** — The downsampling worker runs as an asyncio background task spawned during the FastAPI lifespan:
  - Every 60 seconds (at `:05` past the minute), it processes the completed 1-minute bucket for all agents that have raw data in that window. Processing includes:
    - For each numeric field in the raw `data` JSONB payload (all keys under `gpu[*].util_pct`, `gpu[*].mem_used_mb`, `gpu_cache_pct`, `ttft_p50_ms`, `ttft_p99_ms`, `tps`, `running`, `waiting`, `cpu_pct`, `ram_used_gb`, `disk_pct`), compute `avg`, `min`, `max`, `p50`, `p95`, and `p99` over the window's rows.
    - Write a single row to `metric_aggregates_1m` with the aggregate payload keyed as `{"gpu_util_pct": {"avg": 88.1, "min": 72.0, "max": 95.3, "p50": 89.0, "p95": 94.1, "p99": 95.0}, "vram_used_gb": {...}, ...}`.
    - On `ON CONFLICT (agent_id, bucket_ts) DO UPDATE`, the worker re-aggregates and updates the row (covers edge cases where the worker runs before the minute is fully complete — this is a last-writer-wins idempotent overwrite).
  - Every 5 minutes (at `:05` past each 5-minute mark), it cascades from the 1-minute aggregates table: `SELECT agent_id, workspace_id, bucket_ts, data FROM metric_aggregates_1m WHERE bucket_ts >= <5-min-boundary> AND bucket_ts < <5-min-boundary + 5 min>` and aggregates 5 rows into one 5-minute aggregate row using the same aggregate functions (the per-window aggregates from the 1m table are themselves averaged for `avg`, min/max are re-taken, and percentiles are re-computed from the raw p50/p95/p99 values stored in the 1m rows — this is a lossy approximation of true 5-minute percentiles, which is acceptable for dashboard display purposes). The 5-minute aggregate is written to `metric_aggregates_5m` with the same upsert pattern.
  - After the 1-minute aggregates are written, the worker deletes raw rows from `agent_metrics` that fall outside the raw retention window for each workspace (default 24 hours, read from `workspaces.settings['data_retention']['raw_metrics_hours']`). This deletion runs in batches of 10,000 rows with a 100 ms delay between batches.
  - If the worker is still running when the next tick occurs (e.g., the database is slow), it skips the overlapping tick and logs a `WARNING` — it never runs two aggregation passes concurrently.

- **ACF10-6: Historical metric REST endpoint reads from the correct table tier based on time range** — `GET /api/metrics/{agent_id}` accepts query parameters `range` (one of `live`, `5m`, `15m`, `1h`, `6h`, `1d`, `1w`, `1M`, `3M`, `6M`, `1y`) or explicit `since` and `until` ISO 8601 timestamps. The backend routes reads as follows:
  - `range ≤ 1h` or `since < 24h ago`: Query `agent_metrics` table (raw 2s resolution). Limit: 500 rows per page.
  - `range ≤ 1w`: Query `metric_aggregates_1m` (1-minute resolution).
  - `range > 1w`: Query `metric_aggregates_5m` (5-minute resolution).
  The response is a JSON:API document with `type: "metrics"` and attributes `ts` (ISO 8601), `resolution` (`"raw"`, `"1m"`, or `"5m"`), and `data` (the stored JSONB payload or aggregate structure). The meta block includes `total` rows, `offset`, `limit`, and `resolution`. Query latency for any range is under 500 ms for a single agent.

- **ACF10-7: Workspace data isolation is enforced on all metric reads** — Every metric query (both live WebSocket broadcast and historical REST) filters by `workspace_id` derived from the authenticated user's JWT claim. The `agent_metrics`, `metric_aggregates_1m`, and `metric_aggregates_5m` tables all carry a `workspace_id` column. The REST handler at `GET /api/metrics/{agent_id}` verifies the agent belongs to the JWT's workspace via a `SELECT workspace_id FROM agents WHERE id = :aid` check, returning HTTP 404 (JSON:API error, code `"RESOURCE_NOT_FOUND"`) if the agent UUID does not exist in the user's workspace. The WebSocket dashboard handler verifies workspace membership before subscribing to the Redis channel for that workspace.

- **ACF10-8: The ingestion pipeline handles high-frequency concurrent writes without data loss or write contention** — Under a simulated load of 100 concurrently connected agents (each pushing a metrics message every 2 seconds, ~50 writes/second aggregate), the batch-ingestion pipeline:
  - Sustains a 99th-percentile write latency (buffer-to-commit) under 200 ms.
  - Does not exceed 15 database connections from the connection pool during write bursts (measured via `pg_stat_activity`).
  - Never produces deadlocks or serialisation failures (`40001` / `40P01` PostgreSQL errors).
  - Does not drop or skip rows: the row count in `agent_metrics` after 10 minutes of sustained 50 writes/second equals exactly `100 agents × 30 snapshots/minute × 10 minutes = 30,000 rows` (accounting for agent startup skew).
  - CPU utilisation of the backend process stays under 50% of a single core (excluding the downsampling worker). Memory growth from the batch buffers stays under 100 MB total (each buffer entry is approximately 2 KB × 100 agents × 5 seconds / 2-second interval × 2.5 safety factor ≈ 250 KB per agent, 25 MB total).

## Technical Notes

### File Paths and Structure

```
backend/app/
├── ws/
│   └── agent_ws.py              # WebSocket handler: receives metrics from agents
│   └── dashboard_ws.py          # WebSocket handler: broadcasts to browsers
├── api/
│   └── metrics.py               # GET /api/metrics/{agent_id} historical endpoint
├── services/
│   ├── metric_ingestion_service.py  # NEW: batch buffer, flush logic, Redis publish
│   └── downsampler_service.py       # NEW: aggregation runner, retention cleanup
├── models/
│   ├── agent_metrics.py         # (F3) agent_metrics ORM model
│   └── metric_aggregate.py      # NEW: metric_aggregates_1m and metric_aggregates_5m models
├── schemas/
│   └── metric.py                # JSON:API serialization for metric responses

common/modelprism_common/schemas/
    └── metrics.py               # Pydantic models shared by agent + backend:
                                 # MetricSnapshot, VllmMetricSnapshot, MetricBatch

modelprism-agent/modelprism_agent/
    └── connection.py            # Sends serialized MetricSnapshot over WebSocket
    └── metrics/collector.py     # (F8) Produces MetricSnapshot dicts every 2s
```

### Key Design Decisions

**Why batch writes instead of per-row INSERT?** At 50+ writes/second sustained, per-row `INSERT` with individual `commit` would consume the connection pool and add ~5–10 ms of round-trip latency per write. Batching reduces the commit rate from 50/s to 10/s (5-second flush interval) and uses `executemany` with a single round trip. Acceptable trade-off: up to 5 seconds of data buffered in memory, lost on crash.

**Why JSONB aggregates instead of separate columns?** The `agent_metrics.data` JSONB schema is extensible — agents may report different GPU counts, future vLLM versions may add new metric keys. Storing aggregates as `{"field": {"avg": ..., "min": ..., "max": ..., "p50": ..., "p95": ..., "p99": ...}}` in a single JSONB column keeps the aggregate table schema stable even as the underlying metric surface grows. The query layer parses the JSONB and presents the same field structure to the frontend regardless of table origin.

**Why not TimescaleDB or a dedicated time-series database?** ModelPrism targets self-hosted users on modest hardware. Adding TimescaleDB (PostgreSQL extension) or a separate InfluxDB/Prometheus instance increases operational complexity. At the expected scale (hundreds of agents, not thousands), PostgreSQL with careful indexing, batch ingestion, and downsampling provides adequate performance. If an installation reaches >10M metric rows/day, the operator can migrate to TimescaleDB without changing the application layer by swapping the storage queries.

### Ingestion Service: `metric_ingestion_service.py`

```python
# Core buffer architecture
# Buffer = dict[UUID, list[MetricWrite]]
#
# MetricWrite is a dataclass:
#   agent_id: UUID
#   workspace_id: UUID
#   ts: datetime
#   data: dict (the full JSONB payload)
#
# flush() called by:
#   1. Periodic asyncio task (every 5 seconds)
#   2. Buffer reaches 100 rows for any agent (size check in enqueue())
#
# flush() does:
#   async with db.begin() as tx:
#       await tx.execute(
#           insert(AgentMetric),
#           [row._asdict() for rows in buffer.values() for row in rows]
#       )
#   for wid in affected_workspaces:
#       await redis.publish(f"metrics:{wid}", json.dumps(metrics_batch))
#   buffer.clear()
```

### Downsampling Service: `downsampler_service.py`

```python
# Background task spawned in lifespan:
# asyncio.create_task(run_downsampler())
#
# Schedule:
#   1m aggregates: every 60s at :05 past the minute
#   5m aggregates: every 300s at :05 past each 5-minute boundary
#   Raw retention cleanup: after each 1m aggregate pass
#
# Aggregation query pattern (1m):
#   SELECT
#     agent_id,
#     workspace_id,
#     date_trunc('minute', ts) AS bucket_ts,
#     -- For each numeric field, compute aggregates from JSONB
#     jsonb_build_object(
#       'gpu_util_pct', jsonb_build_object(
#         'avg', AVG((data->>'gpu_util_pct')::numeric),
#         'min', MIN((data->>'gpu_util_pct')::numeric),
#         ...
#       ),
#       ...
#     ) AS data
#   FROM agent_metrics
#   WHERE ts >= :bucket_start AND ts < :bucket_end
#   GROUP BY agent_id, workspace_id
#
# Note: For multi-GPU agents, each GPU index in the gpu array is
# computed independently: gpu_0_util_pct, gpu_1_util_pct, etc.
```

### WebSocket Handler Integration (`agent_ws.py`)

The existing agent WebSocket handler defined in F7 must be extended to route metrics messages to the ingestion service:

```python
# In agent_ws.py receive loop:
async def handle_message(ws, msg: dict, agent: Agent, ingestion: MetricIngestionService):
    msg_type = msg.get("type")
    if msg_type == "metrics":
        snapshot = MetricSnapshot(**msg)  # validates via Pydantic
        await ingestion.enqueue(
            agent_id=agent.id,
            workspace_id=agent.workspace_id,
            ts=snapshot.ts,
            data=msg,
        )
    elif msg_type == "vllm_metrics":
        vllm_snapshot = VllmMetricSnapshot(**msg)
        # Merge vLLM data into a metrics-structured payload
        await ingestion.enqueue(
            agent_id=agent.id,
            workspace_id=agent.workspace_id,
            ts=vllm_snapshot.ts,
            data={"vllm": msg},  # nested under vllm key in JSONB
        )
    elif msg_type == "heartbeat":
        # Handled by F7 — update agent last_seen_at
        ...
```

### API Endpoint: `GET /api/metrics/{agent_id}`

```
GET /api/metrics/{agent_id}?range=1h&page[offset]=0&page[limit]=500
Authorization: Bearer <jwt>

Response (JSON:API):

{
  "data": [
    {
      "type": "metrics",
      "id": null,
      "attributes": {
        "ts": "2026-06-07T12:00:02.000Z",
        "resolution": "raw",
        "data": { /* full JSONB payload */ }
      }
    }
  ],
  "meta": {
    "total": 1800,
    "count": 500,
    "offset": 0,
    "limit": 500,
    "resolution": "raw"
  },
  "links": {
    "self": "/api/metrics/550e8400-e29b-41d4-a716-446655440000?range=1h&page%5Boffset%5D=0&page%5Blimit%5D=500",
    "next": "/api/metrics/550e8400-e29b-41d4-a716-446655440000?range=1h&page%5Boffset%5D=500&page%5Blimit%5D=500"
  }
}
```

Note: The `id` is `null` because metric rows use a `BIGSERIAL` primary key that is not meaningful as a public resource identifier. The frontend uses `ts` as the unique identifier within a response page.

### Retention Configuration

Retention periods are configurable per workspace via `workspaces.settings['data_retention']`:

```json
{
  "data_retention": {
    "raw_metrics_hours": 24,
    "agg_1m_days": 30,
    "agg_5m_days": 365,
    "logs_days": 30
  }
}
```

Defaults are applied by the workspace creation handler (F32). The retention enforcement pass runs as part of the downsampling cycle and respects per-workspace settings. Workspaces that never configure retention use the defaults.

### Edge Cases

- **Agent disconnect mid-buffer:** If an agent disconnects while the buffer contains unflushed rows for that agent, the remaining rows are flushed on the next periodic tick (or discarded on server shutdown if the buffer survives). No special handling needed because the buffer is per-agent and the next reconnection will begin pushing fresh metrics.
- **Agent reconnection with stale timestamp:** If an agent's clock is skewed and it pushes a metric with `ts` far in the past or future (>1 hour from server clock), the ingestion service logs a `WARNING` and drops the row. The agent is expected to synchronise its clock via NTP.
- **Duplicate metrics on WebSocket reconnect:** After a brief disconnection, the agent resumes pushing at 2-second intervals. The previous buffer may have contained rows that were not yet flushed. The new connection's metrics begin fresh — there is no deduplication across connections. At most 5 seconds of overlap is lost, which is acceptable for the 2-second interval data.
- **Downsampling on an agent with zero metrics in a window:** The worker skips agents that have no raw data in the window. It does not write a placeholder row. This naturally handles paused or stopped agents.
- **Downsampling race with live insert:** If the downsampler reads a window that is still receiving live writes (the agent is pushing at `:02` while the downsampler reads at `:05` for the previous minute), the upsert pattern (`ON CONFLICT DO UPDATE`) ensures the final aggregate reflects all rows in the window. The worker's `ts >= bucket_start AND ts < bucket_end` WHERE clause is stable because it uses the exact minute boundary.
- **Concurrent downsampling on same workspace:** The `ON CONFLICT` upsert prevents duplicate rows. Two workers never run concurrently (singleton guard via a Redis `SETNX`-style lock key `downsampler:running` with a 10-second TTL).
- **Integer overflow in BIGSERIAL:** The `agent_metrics` primary key is `BIGSERIAL` (64-bit), providing 9.2 quintillion values. At 50 rows/second it would overflow in ~5.8 billion years.

### Integration Points

- **F1 (Backend scaffolding):** The ingestion service uses the SQLAlchemy async engine and session factory configured in `backend/app/database.py`. The downsampling worker runs as an `asyncio` background task spawned within the FastAPI `lifespan` context manager defined in F1. The Redis connection pool configured in F1 is used for both the ingestion Redis publish channel and the downsampler lock key.

- **F3 (Database schema):** Three tables are involved. The `agent_metrics` table (defined in F3, `backend/app/models/agent_metrics.py`) receives raw metric rows. The new `metric_aggregates_1m` and `metric_aggregates_5m` tables are defined in a new file `backend/app/models/metric_aggregate.py` and are created by an Alembic migration. The models use `WorkspaceScopedMixin` for workspace isolation and `BIGSERIAL` primary keys matching the `agent_metrics` pattern established in F3.

- **F7 (Agent WebSocket handler):** The `backend/app/ws/agent_ws.py` handler from F7 is extended with the `handle_message` routing shown above. The F7 handler's existing authentication, heartbeat handling, and command-response routing remain unchanged. Metrics messages are a new message type that flows through the same `receive()` loop.

- **F9 (Agent metric push):** The agent's `connection.py` (from F9) already sends `"type": "metrics"` messages every 2 seconds. F10 does not change the agent's push behaviour. The agent pushes the same payload format defined in F9; F10 validates it server-side.

- **F16 (Dashboard WebSocket broadcast):** The `backend/app/ws/dashboard_ws.py` handler subscribes to the Redis channel `metrics:<workspace_id>` and forwards messages to all connected browser clients for that workspace. F10 publishes to this Redis channel after every successful buffer flush.

- **F17 (Time-range selector + historical data):** The frontend `TimeRangeSelector` component and the `GET /api/metrics/{agent_id}` endpoint defined here are the read-side counterpart to the write pipeline. F17 defines the frontend composable that calls this endpoint and renders uPlot charts from the response data.

- **F23 (Model optimisation recommendations):** The optimisation rules engine reads aggregated metric data to detect patterns (low KV cache utilisation, high error rate, GPU under-utilisation). F10 provides the aggregate tables as the data source for these rules.

- **F32 (Workspace management):** The retention settings in `workspaces.settings['data_retention']` are configured via the workspace settings UI (F32). F10 reads these settings during the retention cleanup pass. If a workspace has never configured retention, the defaults (24h raw, 30d 1m-agg, 1y 5m-agg) apply.

- **F35 (Data retention configuration UI):** The retention cleanup pass in F10 enforces the policies that F35 configures. The cleanup job reads the workspace-level retention settings from the database and deletes expired rows accordingly. F35 additionally includes a "Run cleanup now" button that triggers an on-demand retention pass via a background task.

### Performance Testing

The high-frequency ingestion performance criterion (ACF10-8) must be verified with a reproducible benchmark:

```python
# test_load/bench_ingestion.py (conceptual)
# Setup: 100 simulated WebSocket agents, each pushing metrics every 2s
# Duration: 10 minutes
# Measure:
#   - Rows ingested per second
#   - p50/p95/p99 write latency (time from WS message → commit)
#   - Connection pool utilisation
#   - Backend CPU/memory
# Assert:
#   - > 95% of writes complete within 200 ms
#   - No dropped rows (count matches expected)
#   - No database deadlocks or serialisation failures
```

### Depends on: F1, F3, F7, F9
