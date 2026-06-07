# Task M1-T6 — Metric Storage + API

> **Milestone:** M1 (Foundation)
> **Priority:** High
> **Status:** 🟢 Complete
> **Estimated Effort:** 3 days

> **Impact from M1-T4:** Latest metrics are already stored in Redis at `agent:{id}:latest_metrics` and published to `metrics:{id}` / `vllm_metrics:{id}` Redis channels. This task should subscribe to those channels and persist to PostgreSQL. The WebSocket receive loop in `agent_ws.py` calls `_handle_metrics()` which does Redis-only storage — you can add DB writes there or create a separate consumer. Metrics schemas (`MetricsMessage`, `VLLMMetricsMessage`) are in `app/schemas/ws_messages.py`. The `AgentMetric` model already exists in `app/models/agent_metric.py` with tier column (default `raw`).
> **Impact from M1-T5:** The agent now sends metrics via WebSocket using the message shapes defined in `modelprism_agent/schemas.py` (which mirror `app/schemas/ws_messages.py`). The agent pushes two message types: `metrics` (flat JSON with `gpu` array + system fields) and `vllm_metrics` (per-instance vLLM telemetry). The agent's `MetricCollector` in `modelprism_agent/metrics/collector.py` emits snapshots at 2-second intervals. The agent also pushes logs via `POST /api/agents/{id}/logs` through the `LogStreamer`. The registration payload (`POST /api/agents/register`) includes `gpus`, `cpu`, `disk`, and `os` fields matching the backend's `complete_registration()` schema in `agent_manager.py`. The agent package is at `/Users/pk/Projects/ModelPrism/modelprism-agent/`.

## Description

Implement metric storage in PostgreSQL with multi-tier retention (raw/aggregated) and the REST API for querying historical metrics. The backend receives metrics from the agent WebSocket pipeline, stores them in the appropriate retention tier, runs background downsampling, and exposes a `GET /api/metrics/{agent_id}` endpoint for the dashboard to fetch historical data.

## Task Goals

- Create metric insertion pipeline (raw → downsampled tiers)
- Implement background downsampling worker (raw→t10s→t1m→t10m→t1h→t6h)
- Implement data retention cleanup worker (purge expired data per tier)
- Create `GET /api/metrics/{agent_id}` endpoint with time range query params
- Support query parameters: `range` (1h/6h/1d/1w/1m), `tier` (auto-select based on range)
- Return metrics in format consumable by uPlot charts
- Create `app/services/metric_service.py` for business logic

## Implementation Plan

> ⚠️ Analyze this plan thoroughly before implementing.

### Pre-Implementation Analysis

- Review the existing downsampling logic in `vllm-dashboard.py` (lines 682-720) — working implementation to model after
- Review `requirements/06-api-surface.md` for the metrics API endpoint
- Review `requirements/03-functional-requirements.md` F2.3 (Time Range Selector)
- Review NFR1.2 (Dashboard Loading) for historical data performance requirements
- Invoke `fastapi-expert` skill for async background tasks in FastAPI

### Steps

1. Create `app/services/metric_service.py`:
   - `ingest_metrics(agent_id, metrics_data)` — insert raw metric row, keyed by (agent_id, ts)
   - `query_metrics(agent_id, range_key)` — returns time-bucketed metric rows
   - `get_latest_metrics(agent_id)` — return latest metric snapshot (from Redis first, DB fallback)
   - `get_agent_metric_summary(agent_id)` — aggregate stats for overview cards
2. Implement the downsampling system (modeled after `vllm-dashboard.py`):
   - Tier definitions: raw (2s), t10s (10s), t1m (60s), t10m (600s), t1h (3600s), t6h (21600s)
   - Run downsampling as a FastAPI `lifespan` background task
   - Average numeric columns within each time bucket
   - Schedule: run downsampling every 60 seconds
3. Implement retention cleanup:
   - Delete rows older than tier retention in the same background task
   - Raw: 24h, t10s: 7d, t1m: 30d, t10m: 90d, t1h: 1y, t6h: forever
4. Create `app/api/metrics.py`:
   - `GET /api/metrics/{agent_id}` — query params: `range` (default "1h")
   - Range keys: `live` (last 5 min), `1h`, `6h`, `1d`, `1w`, `1m`
   - Auto-select tier table based on range (live→raw, 1h→t10s, 6h→t1m, 1d→t1m, 1w→t10m, 1m→t1h)
   - Return format: `{"agent_id": "...", "range": "...", "count": N, "rows": [...]}`
5. Add Redis caching for latest metrics:
   - On WebSocket metric arrival, update Redis `agent:{id}:latest` (string, JSON)
   - `GET /api/metrics/{agent_id}`?latest=true reads from Redis instead of DB
   - Reduces DB load for the dashboard's live view
6. Include metrics router in `app/main.py`
7. Add tests for metric ingestion, query, and downsampling accuracy

### Skills & MCP Servers

| Resource              | Purpose                      | When to Invoke                   |
| --------------------- | ---------------------------- | -------------------------------- |
| `fastapi-expert`      | Async background tasks, SQL  | Steps 2-5                       |
| `filesystem` (MCP)    | File creation                | Creating service and API files   |

## Acceptance Criteria

- [ ] `ingest_metrics()` inserts raw metrics into the database
- [ ] Downsampling worker runs in background and creates aggregated rows
- [ ] Retention cleanup removes expired data per tier
- [ ] `GET /api/metrics/{agent_id}?range=1h` returns metrics from the last hour
- [ ] `GET /api/metrics/{agent_id}?range=live` returns last 5 minutes from Redis
- [ ] Empty agent_id returns 404
- [ ] Invalid range returns 400 with valid options
- [ ] Latest metrics available in Redis for fast access
- [ ] Downsampling does not lose accuracy on averages

## Completion Criteria

- [ ] All acceptance criteria above pass
- [ ] Python type check passes (`mypy`)
- [ ] Code passes linting (`ruff`)
- [ ] All tests pass (`pytest`)

## Testing Checklist

- [ ] Unit test: metric ingestion and retrieval
- [ ] Unit test: downsampling correctness
- [ ] Unit test: retention cleanup
- [ ] Integration test: ingest → downsample → query end-to-end

## Dependencies

- **Requires:** M1-T1 (Backend Scaffolding), M1-T2 (Database Schema), M1-T4 (Agent WebSocket Handler)
- **Blocks:** M1-T7 (Dashboard WS Broadcast), M1-T9 (Dashboard Pages)

## Documentation References

- `requirements/06-api-surface.md` — metrics API spec
- `requirements/03-functional-requirements.md` — F2.3 time range
- `requirements/04-non-functional-requirements.md` — NFR1.2, NFR2.3

## Notes

- Model the downsampling logic on the proven implementation in `vllm-dashboard.py` (lines 682-720)
- Use `sqlalchemy.ext.asyncio` for async DB operations throughout
- The `live` range is served from Redis — no DB query needed for the dashboard's default view
- Downsampling is additive: higher tiers never need to recompute lower tiers
- Retention cleanup is also additive: deleting from `raw` doesn't affect `t10s`
- Consider using PostgreSQL's `date_trunc` for the downsampling GROUP BY buckets
- For MVP, don't add JSON:API wrapping on metrics endpoint (raw JSON array is more performant for charts)
