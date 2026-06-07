# ADR-005: Data Retention

## Status
Accepted

## Context
The system generates large volumes of time-series data: GPU metrics every 2s, vLLM metrics every 2s, log entries, usage records. Without a retention policy, storage grows unbounded. Different users have different retention needs (compliance vs cost savings).

Initial requirements mentioned raw metrics "in memory for 5 minutes" but no configurable retention or cleanup mechanism.

## Decision
- **Configurable per workspace** in Settings UI (F6.5)
- Retention tiers with separate controls:
  - Raw metrics (2s): 1h–48h default (24h)
  - Aggregated (1m): 7d–90d default (30d)
  - Historical (5m): 30d–365d default (1y)
  - Logs: 7d–90d default (30d)
  - Usage/billing records: fixed 7 years (compliance)
- Background cleanup job runs daily
- No TimescaleDB — standard PostgreSQL with partitioned tables by time range

## Consequences
- Users control their storage costs vs data availability tradeoff
- No surprise storage growth in self-hosted deployments
- Cleanup job must be efficient (batch DELETE with partitioning)
- Downsampling pipeline (raw → 1m → 5m aggregates) built into metric ingestion
