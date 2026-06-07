# Task M1-T2 — Database Schema

> **Milestone:** M1 (Foundation)
> **Priority:** Critical
> **Status:** ⚪ Not Started
> **Estimated Effort:** 3 days

## Description

Create the SQLAlchemy ORM models and Alembic migrations for all Foundation-level database entities. This includes the `agents`, `agent_tokens`, `metrics` (multi-tier: raw, aggregated), and `agent_logs` tables. Set up the Alembic configuration and initial migration.

## Task Goals

- Define SQLAlchemy 2.0 ORM models for: `Agent`, `AgentToken`, `AgentMetric`, `AgentLog`
- Create Alembic configuration with async migration support
- Generate initial migration that creates all tables
- Add `Base` declarative base in `app/models/__init__.py`
- Create `app/models/agent.py` — Agent ORM model
- Create `app/models/agent_token.py` — AgentToken ORM model
- Create `app/models/agent_metric.py` — AgentMetric with tiered storage support
- Create `app/models/agent_log.py` — AgentLog ORM model
- Add proper indexes for time-range queries (agent_id + timestamp)
- Add `workspace_id` columns for future multi-tenancy

## Implementation Plan

> ⚠️ Analyze this plan thoroughly before implementing.

### Pre-Implementation Analysis

- Review `requirements/06-api-surface.md` for agent registration fields and metric shapes
- Review `requirements/02-architecture-overview.md` for data flow and retention design
- Review `requirements/03-functional-requirements.md` for F1 (Agent Management) data requirements
- Review NFR2.3 (Data Durability) for retention tiers
- Invoke `fastapi-expert` skill for SQLAlchemy 2.0 async patterns and Alembic configuration

### Steps

1. Create `app/models/__init__.py` with `Base = declarative_base()` and re-exports
2. Create `app/models/agent.py`:
   - Columns: `id` (UUID PK), `name` (friendly name, e.g., "cyan-koala-42"), `hostname`, `agent_version`, `status` (online/offline), `last_seen_at`, `gpu_info` (JSON), `cpu_info` (JSON), `disk_info` (JSON), `os_info`, `workspace_id` (nullable FK for future), `created_at`, `updated_at`
   - Indexes on `status`, `workspace_id`, `last_seen_at`
3. Create `app/models/agent_token.py`:
   - Columns: `id` (UUID PK), `token_hash` (hashed token), `prefix` (first 8 chars), `agent_id` (nullable FK, set on claim), `status` (pending/claimed/expired), `expires_at`, `created_at`
   - Index on `token_hash` for fast lookup
4. Create `app/models/agent_metric.py`:
   - Columns: `id` (BigInt PK, auto), `agent_id` (FK), `ts` (timestamp), `tier` (raw/t10s/t1m/t10m/t1h/t6h)
   - GPU metrics columns: `gpu_util_pct`, `gpu_mem_used_mb`, `gpu_temp_c`, `gpu_power_w`, `gpu_cache_pct`
   - vLLM metrics columns: `running`, `waiting`, `total_requests`, `prompt_tokens_total`, `gen_tokens_total`, `ttft_p50_ms`, `ttft_p99_ms`, `tps`, `prefix_cache_hit`, `error_rate`, `trunc_rate`
   - System metrics columns: `ram_used_gb`, `ram_total_gb`, `cpu_pct`, `load_1`, `load_5`, `load_15`, `disk_used_gb`, `disk_total_gb`, `disk_pct`
   - Composite index on `(agent_id, ts, tier)` for efficient time-range queries
   - Partitioned by tier for data management
5. Create `app/models/agent_log.py`:
   - Columns: `id` (BigInt PK, auto), `agent_id` (FK), `ts`, `level` (debug/info/warning/error), `module`, `message`, `stack_trace` (nullable)
   - Index on `(agent_id, ts, level)` for filtered log queries
6. Create Alembic configuration:
   - `alembic.ini` with migration path
   - `alembic/env.py` configured for async SQLAlchemy
   - `alembic/versions/` directory
7. Generate initial migration: `alembic revision --autogenerate -m "initial schema"`
8. Verify migration runs cleanly against a test PostgreSQL
9. Create downgrade test — ensure migration is reversible

### Skills & MCP Servers

| Resource              | Purpose                      | When to Invoke                   |
| --------------------- | ---------------------------- | -------------------------------- |
| `fastapi-expert`      | SQLAlchemy 2.0 async models  | Steps 2-6                       |
| `filesystem` (MCP)    | File creation                | Creating model files             |

## Acceptance Criteria

- [ ] All ORM models defined with proper types and relationships
- [ ] Alembic migration generates and applies successfully
- [ ] Migration creates all 4 tables with proper indexes
- [ ] Migration is reversible (downgrade works)
- [ ] Foreign key relationships work (Agent → AgentToken, AgentMetric, AgentLog)
- [ ] JSON columns for GPU/CPU/disk info use PostgreSQL JSONB
- [ ] Composite indexes on (agent_id, ts) for metric and log tables

## Completion Criteria

- [ ] All acceptance criteria above pass
- [ ] `alembic upgrade head` runs cleanly
- [ ] `alembic downgrade -1` runs cleanly
- [ ] Python type check passes (`mypy`)
- [ ] Code passes linting (`ruff`)

## Testing Checklist

- [ ] Unit tests for model creation and relationships
- [ ] Migration test: upgrade → insert test data → downgrade → verify rollback
- [ ] Index existence verification test

## Dependencies

- **Requires:** M1-T1 (Backend Scaffolding)
- **Blocks:** M1-T3 (Agent Registration API), M1-T6 (Metric Storage + API)

## Documentation References

- `requirements/06-api-surface.md` — agent fields, metric shapes
- `requirements/03-functional-requirements.md` — F1 data requirements
- `requirements/07-directory-structure.md` — file locations
- `requirements/04-non-functional-requirements.md` — NFR2.3 data retention

## Notes

- Use `sqlalchemy.orm.Mapped` and `mapped_column` (SQLAlchemy 2.0 style)
- All timestamp columns should use `DateTime(timezone=True)` with UTC
- `UUID` columns should use PostgreSQL native UUID type
- Keep workspace_id as nullable for now — will be enforced in M4
- Metric retention tiers match the spec: raw (2s, 24h), t10s (10s, 7d), t1m (1m, 30d), t10m (10m, 90d), t1h (1h, 1y), t6h (6h, forever)
- The tier column on AgentMetric enables querying by retention level
