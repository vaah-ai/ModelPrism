# F3: Database Schema

## Metadata
- **ID:** F3
- **Phase:** Foundation
- **Effort:** Large
- **Dependencies:** None
- **Acceptance Criteria Count:** 8

## Description
Define all SQLAlchemy 2.0 async ORM models and Alembic migrations for the ModelPrism platform. Covering nine core entity families — workspaces, users, agents, model deployments, API keys, usage records, benchmarks, billing, and agent logs — with proper foreign-key relationships, composite indexes, enum types, JSON columns for flexible metric payloads, and workspace-level data isolation via a `workspace_id` column on every scoped table. Generate an initial Alembic migration that creates all tables in a single revision so the database can be bootstrapped from scratch with `alembic upgrade head`.

## Concrete Examples (Specification by Example)

### Example 1: Fresh Database Bootstrap
- **Input:** A new developer clones the repository, runs `alembic upgrade head` against a blank PostgreSQL database (`modelprism_dev`).
- **Action:** Alembic reads the migration chain, finds the initial revision (e.g., `0001_initial_schema.py`), and executes all CREATE TABLE statements in dependency order (workspaces first, then users, then everything that references them).
- **Expected Output:** The `alembic_version` table contains the revision ID. Running `\dt` in psql shows tables: `workspaces`, `users`, `agent_registration_tokens`, `agents`, `agent_metrics`, `model_deployments`, `api_keys`, `usage_records`, `benchmark_runs`, `benchmark_results`, `billing_plans`, `billing_invoices`, `billing_meter_events`, `agent_logs`, `workspace_members`, `sessions`, `password_reset_tokens`. All foreign keys, unique constraints, indexes, and enum types are present. No migrations are pending.

### Example 2: Workspace Data Isolation
- **Input:** User A (workspace `ws_1`) and User B (workspace `ws_2`) both run `SELECT * FROM model_deployments`.
- **Action:** The application layer injects `WHERE workspace_id = <current_workspace>` on every query. No cross-workspace foreign keys or joins exist in the table definitions.
- **Expected Output:** User A sees only deployments created under `ws_1`. User B sees only deployments under `ws_2`. Even if User B knows a `model_deployment.id` from workspace `ws_1`, attempting to access it returns an empty result or 404 because the workspace filter is enforced at the query level and no row satisfies both the ID and the workspace predicate.

### Example 3: Agent Metric Ingestion with JSON Payload
- **Input:** The agent on GPU server `ag_cyan_koala_42` pushes a metrics snapshot with GPU utilization, VRAM, and vLLM stats.
- **Action:** The backend receives the WebSocket message, deserializes the flat JSON payload, and writes a row into `agent_metrics` with `agent_id`, `workspace_id`, `timestamp`, and a `data` JSONB column containing the full snapshot.
- **Expected Output:** The `agent_metrics` table stores `{ "agent_id": "ag_cyan_koala_42", "workspace_id": "ws_abc", "ts": "2026-06-07T12:00:02Z", "data": { "gpu_util_pct": 87.2, "vram_used_gb": 42.5, "vram_total_gb": 80.0, "running_requests": 3, "waiting_requests": 2, "ttft_p99_ms": 450, "tok_per_sec": 185.3, "kv_cache_util_pct": 62.1, "gpu_temp_c": 71.0, "power_draw_w": 285.0, "cpu_util_pct": 34.2, "ram_used_gb": 28.1, "ram_total_gb": 64.0 } }`.

### Example 4: Model Deployment Lifecycle
- **Input:** A user deploys `mistral-7b` on server `ag_cyan_koala_42` with specific vLLM parameters.
- **Action:** The backend creates a `model_deployments` row during deployment, updates `status` as the deployment progresses (`downloading` → `starting` → `running` → `healthy`), and stores the full vLLM configuration snapshot in a JSONB column.
- **Expected Output:** `model_deployments` contains a row with `agent_id` → `ag_cyan_koala_42`, `model_name = "mistral-7b"`, `hf_model_id = "mistralai/Mistral-7B-Instruct-v0.3"`, `status = "healthy"`, `docker_container_id = "abc123def456"`, `port = 8001`, `config = { "tensor_parallel_size": 1, "pipeline_parallel_size": 1, "quantization": null, "max_model_len": 32768, "max_num_seqs": 256, "gpu_memory_utilization": 0.9, "kv_cache_dtype": "auto", "enable_prefix_caching": true, "enforce_eager": false, "served_model_name": "mistral-7b" }`.

## Acceptance Criteria

- **ACF3-1: Initial migration creates all tables** — Running `alembic upgrade head` against a blank PostgreSQL database creates all ORM-defined tables with correct columns, types (including custom enums: `agent_status`, `deployment_status`, `log_level`, `benchmark_status`, `user_role`, `key_status`), foreign keys, unique constraints, and indexes. No manual SQL or post-migration scripts are required to have a fully functional schema. Downgrading via `alembic downgrade -1` removes all tables cleanly.

- **ACF3-2: Nine core entity families are modeled** — The schema defines tables for: workspaces, users/workspace-members/sessions/password-reset-tokens, agents/agent-registration-tokens, agent_metrics (raw JSONB snapshots), model_deployments, api_keys, usage_records (per-request token/cost), benchmarks (runs + results), billing (plans/invoices/meter-events), and agent_logs. Every table that belongs to a workspace has a non-null `workspace_id` foreign key to `workspaces.id`.

- **ACF3-3: Workspace data isolation is structural** — All resource tables (`agents`, `model_deployments`, `api_keys`, `usage_records`, `benchmark_runs`, `agent_logs`) contain a `workspace_id` column that is a non-null foreign key to `workspaces.id`. Every SELECT query in the application layer includes a `WHERE workspace_id = <current_workspace>` clause. No application code accesses these tables without a workspace filter. Cross-workspace access returns empty results or 404, not data leaks.

- **ACF3-4: Composite indexes support common query patterns** — Indexes exist for the most frequent access paths: `(workspace_id, status)` on agents (filter servers by status within a workspace), `(agent_id, ts DESC)` on agent_metrics (time-series lookups per agent), `(workspace_id, status)` on model_deployments (running models per workspace), `(api_key_hash, workspace_id)` on api_keys (lookup by hashed key with workspace scope), `(agent_id, created_at DESC)` on agent_logs (log retrieval per agent), `(workspace_id, created_at DESC)` on usage_records (usage listing per workspace), and `(refresh_token_hash)` on sessions (fast refresh token lookup).

- **ACF3-5: JSONB columns store flexible payloads in agent_metrics and model_deployments** — The `agent_metrics.data` column uses `JSONB` (not nullable) to store the full GPU/system/vLLM metric snapshot as a flat object. The `model_deployments.config` column uses `JSONB` (nullable) to store the deployment configuration snapshot. These are storage-only columns — querying individual JSONB fields at the database level is not expected; filtering, aggregation, and downsampling happen in application code.

- **ACF3-6: All ID columns use UUIDs** — Every primary key (`id`) uses PostgreSQL `UUID` type with `uuid_generate_v4()` or server-side UUID generation. No auto-increment integer PKs exist in the schema. This avoids enumeration attacks, simplifies distributed ID generation, and aligns with JSON:API's resource ID format.

- **ACF3-7: Enum types are defined as PostgreSQL enums** — All enumerated fields (`agent_status`, `deployment_status`, `log_level`, `benchmark_status`, `user_role`, `key_status`) use PostgreSQL `ENUM` types created in the migration before any table that references them. Alembic uses `sa.Enum(*values, create_constraint=True)` or the SQLAlchemy `Enum` type mapped to a native PG enum. Enum values are never stored as plain varchar strings.

- **ACF3-8: Foreign keys have explicit ON DELETE behavior** — All foreign key constraints specify `ON DELETE CASCADE` or `ON DELETE SET NULL` as appropriate: deleting a workspace cascades to all its agents, deployments, keys, usage records, benchmarks, and logs. Deleting an agent cascades to its metrics, logs, and deployments. Deleting a user sets `user_id` to `NULL` on workspace membership (the workspace persists). Deleting a workspace member row does not delete the user account.

## Technical Notes

### ORM Model Hierarchy (SQLAlchemy 2.0 async)

All models live in `backend/app/models/` (one file per entity family as per directory structure).

**Mixin / base class pattern:**
```python
# backend/app/models/base.py
import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

class Base(DeclarativeBase):
    pass

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

class WorkspaceScopedMixin:
    """Mixin for tables that belong to a workspace."""
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
```

### Table Definitions

#### 1. `workspaces`
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK, default `uuid.uuid4` |
| `name` | VARCHAR(255) | NOT NULL |
| `slug` | VARCHAR(100) | NOT NULL, UNIQUE |
| `cloud_mode` | BOOLEAN | NOT NULL, default `False` |
| `settings` | JSONB | NULL. Stores workspace preferences: data retention config, theme default, etc. |
| `created_at` | TIMESTAMPTZ | NOT NULL, default `now()` |
| `updated_at` | TIMESTAMPTZ | NOT NULL, auto-update |

#### 2. `users`
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `email` | VARCHAR(320) | NOT NULL, UNIQUE |
| `password_hash` | VARCHAR(255) | NOT NULL |
| `display_name` | VARCHAR(255) | NULL |
| `is_active` | BOOLEAN | NOT NULL, default `True` |
| `failed_login_attempts` | INTEGER | NOT NULL, default `0` |
| `locked_until` | TIMESTAMPTZ | NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL |
| `updated_at` | TIMESTAMPTZ | NOT NULL |

Index: `uq_users_email` — unique on `email` (case-insensitive, PostgreSQL `citext` or application-level lowercasing).

#### 3. `workspace_members`
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `workspace_id` | UUID | FK → `workspaces.id` ON DELETE CASCADE, NOT NULL |
| `user_id` | UUID | FK → `users.id` ON DELETE SET NULL, NOT NULL |
| `role` | user_role | NOT NULL (enum: `owner`, `admin`, `member`, `viewer`) |
| `invited_by` | UUID | FK → `users.id` ON DELETE SET NULL, NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL |

Index: `uq_workspace_members` — unique on `(workspace_id, user_id)`.
Index: `ix_workspace_members_user_id` — on `user_id`.

#### 4. `sessions`
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `user_id` | UUID | FK → `users.id` ON DELETE CASCADE, NOT NULL |
| `refresh_token_hash` | VARCHAR(255) | NOT NULL, UNIQUE |
| `expires_at` | TIMESTAMPTZ | NOT NULL |
| `revoked_at` | TIMESTAMPTZ | NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL |

Index: `ix_sessions_refresh_token_hash` — on `refresh_token_hash` (fast lookup on token rotation).

#### 5. `password_reset_tokens`
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `user_id` | UUID | FK → `users.id` ON DELETE CASCADE, NOT NULL |
| `token_hash` | VARCHAR(255) | NOT NULL, UNIQUE |
| `expires_at` | TIMESTAMPTZ | NOT NULL |
| `used_at` | TIMESTAMPTZ | NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL |

#### 6. `agent_registration_tokens`
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `workspace_id` | UUID | FK → `workspaces.id` ON DELETE CASCADE, NOT NULL |
| `token_hash` | VARCHAR(255) | NOT NULL, UNIQUE |
| `label` | VARCHAR(255) | NULL (user-assigned label for the token) |
| `is_used` | BOOLEAN | NOT NULL, default `False` |
| `expires_at` | TIMESTAMPTZ | NOT NULL |
| `claimed_at` | TIMESTAMPTZ | NULL (two-phase claim timestamp) |
| `created_by` | UUID | FK → `users.id` ON DELETE SET NULL, NOT NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL |
| `updated_at` | TIMESTAMPTZ | NOT NULL |

#### 7. `agents`
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `workspace_id` | UUID | FK → `workspaces.id` ON DELETE CASCADE, NOT NULL |
| `friendly_name` | VARCHAR(100) | NOT NULL (auto-generated, e.g., `cyan-koala-42`) |
| `custom_name` | VARCHAR(255) | NULL (user-assigned) |
| `status` | agent_status | NOT NULL, default `offline` (enum: `online`, `offline`, `paused`, `stopped`, `removed`) |
| `agent_version` | VARCHAR(50) | NULL |
| `last_seen_at` | TIMESTAMPTZ | NULL |
| `registered_at` | TIMESTAMPTZ | NOT NULL |
| `hardware_info` | JSONB | NOT NULL, default `{}`. Stores GPU model/count/VRAM, CPU model/cores, RAM, disk, OS, driver version, CUDA version, vLLM version. |
| `hourly_rate_cents` | INTEGER | NULL (user-configured hourly cost for cost comparison) |
| `created_at` | TIMESTAMPTZ | NOT NULL |
| `updated_at` | TIMESTAMPTZ | NOT NULL |

Index: `ix_agents_workspace_status` — on `(workspace_id, status)`.

#### 8. `agent_metrics`
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | BIGSERIAL | PK (sequential for write throughput on high-frequency inserts) |
| `agent_id` | UUID | FK → `agents.id` ON DELETE CASCADE, NOT NULL |
| `workspace_id` | UUID | FK → `workspaces.id` ON DELETE CASCADE, NOT NULL |
| `ts` | TIMESTAMPTZ | NOT NULL (metric observation timestamp from agent) |
| `data` | JSONB | NOT NULL (full metric snapshot: GPU, system, vLLM) |

Index: `ix_agent_metrics_agent_ts` — on `(agent_id, ts DESC)`.
Index: `ix_agent_metrics_ws_ts` — on `(workspace_id, ts DESC)`.
Note: This table will accumulate rows rapidly (every 2s per agent). The retention cleanup job deletes rows based on workspace retention settings. Partitioning by time range is deferred until the table reaches ~100M rows.

#### 9. `model_deployments`
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `workspace_id` | UUID | FK → `workspaces.id` ON DELETE CASCADE, NOT NULL |
| `agent_id` | UUID | FK → `agents.id` ON DELETE CASCADE, NOT NULL |
| `model_name` | VARCHAR(255) | NOT NULL (user-friendly name, e.g., `mistral-7b`) |
| `hf_model_id` | VARCHAR(500) | NOT NULL (full HuggingFace model ID, e.g., `mistralai/Mistral-7B-Instruct-v0.3`) |
| `status` | deployment_status | NOT NULL, default `pending` (enum: `pending`, `downloading`, `starting`, `running`, `healthy`, `stopping`, `stopped`, `failed`) |
| `docker_container_id` | VARCHAR(64) | NULL |
| `port` | INTEGER | NULL (allocated port on the GPU server host) |
| `config` | JSONB | NOT NULL, default `{}`. Stores all vLLM deployment parameters. |
| `error_message` | TEXT | NULL (populated when status is `failed`) |
| `deployed_at` | TIMESTAMPTZ | NULL |
| `stopped_at` | TIMESTAMPTZ | NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL |
| `updated_at` | TIMESTAMPTZ | NOT NULL |

Index: `ix_model_deployments_workspace_status` — on `(workspace_id, status)`.
Index: `ix_model_deployments_agent_id` — on `agent_id`.
Constraint: `port` must be unique per `agent_id` where status is not `stopped` or `failed` (application-level enforced, not a DB constraint — ports are allocated atomically by the port allocation table/service).

#### 10. `api_keys`
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `workspace_id` | UUID | FK → `workspaces.id` ON DELETE CASCADE, NOT NULL |
| `user_id` | UUID | FK → `users.id` ON DELETE SET NULL, NULL (creator, nullable for system keys) |
| `prefix` | VARCHAR(20) | NOT NULL (e.g., `sk-mp-abc123`, stored plaintext for display/lookup) |
| `key_hash` | VARCHAR(255) | NOT NULL, UNIQUE (SHA-256 hash of the full key) |
| `label` | VARCHAR(255) | NULL (user-assigned label) |
| `status` | key_status | NOT NULL, default `active` (enum: `active`, `revoked`, `expired`) |
| `scope` | JSONB | NOT NULL, default `{}`. Stores allowed model IDs (empty = all models), rate limit config. |
| `last_used_at` | TIMESTAMPTZ | NULL |
| `expires_at` | TIMESTAMPTZ | NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL |
| `updated_at` | TIMESTAMPTZ | NOT NULL |

Index: `ix_api_keys_key_hash` — on `key_hash` (fast lookup during proxy authentication).
Index: `ix_api_keys_workspace_id` — on `workspace_id`.

#### 11. `usage_records`
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `workspace_id` | UUID | FK → `workspaces.id` ON DELETE CASCADE, NOT NULL |
| `api_key_id` | UUID | FK → `api_keys.id` ON DELETE SET NULL, NULL |
| `model_deployment_id` | UUID | FK → `model_deployments.id` ON DELETE SET NULL, NULL |
| `request_id` | VARCHAR(100) | NULL (unique request identifier from proxy) |
| `user_id` | UUID | FK → `users.id` ON DELETE SET NULL, NULL |
| `model_name` | VARCHAR(255) | NOT NULL |
| `input_tokens` | INTEGER | NOT NULL, default `0` |
| `output_tokens` | INTEGER | NOT NULL, default `0` |
| `total_tokens` | INTEGER | NOT NULL, default `0` |
| `cost_cents` | INTEGER | NOT NULL, default `0` (cost in USD cents) |
| `provider` | VARCHAR(50) | NOT NULL, default `"self_hosted"` (enum-like: `self_hosted`, `openai`, `anthropic`) |
| `request_type` | VARCHAR(50) | NOT NULL, default `"chat_completion"` (enum-like: `chat_completion`, `completion`, `embedding`) |
| `duration_ms` | INTEGER | NULL (request duration) |
| `streamed` | BOOLEAN | NOT NULL, default `False` |
| `success` | BOOLEAN | NOT NULL, default `True` |
| `created_at` | TIMESTAMPTZ | NOT NULL |

Index: `ix_usage_records_workspace_created` — on `(workspace_id, created_at DESC)`.
Index: `ix_usage_records_api_key_id` — on `api_key_id`.
Index: `ix_usage_records_model_name` — on `model_name`.
Note: Usage records are immutable — no UPDATE or DELETE in application code. The 7-year retention requirement is enforced by the retention cleanup job (which never deletes usage records).

#### 12. `benchmark_runs`
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `workspace_id` | UUID | FK → `workspaces.id` ON DELETE CASCADE, NOT NULL |
| `agent_id` | UUID | FK → `agents.id` ON DELETE SET NULL, NULL |
| `model_deployment_id` | UUID | FK → `model_deployments.id` ON DELETE SET NULL, NULL |
| `created_by` | UUID | FK → `users.id` ON DELETE SET NULL, NULL |
| `status` | benchmark_status | NOT NULL, default `pending` (enum: `pending`, `running`, `completed`, `failed`, `cancelled`) |
| `config` | JSONB | NOT NULL. Stores number of requests, concurrency, request rate, input/output length distribution, dataset name. |
| `started_at` | TIMESTAMPTZ | NULL |
| `completed_at` | TIMESTAMPTZ | NULL |
| `error_message` | TEXT | NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL |
| `updated_at` | TIMESTAMPTZ | NOT NULL |

Index: `ix_benchmark_runs_workspace_created` — on `(workspace_id, created_at DESC)`.

#### 13. `benchmark_results`
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `run_id` | UUID | FK → `benchmark_runs.id` ON DELETE CASCADE, NOT NULL |
| `metric_name` | VARCHAR(100) | NOT NULL (e.g., `ttft_p50`, `ttft_p99`, `tpot_p50`, `throughput_tok_per_sec`, `error_rate`, `total_tokens`) |
| `metric_value` | DOUBLE PRECISION | NOT NULL |
| `unit` | VARCHAR(50) | NULL (e.g., `ms`, `tok/s`, `req/s`, `%`) |

Index: `ix_benchmark_results_run_id` — on `run_id`.
Unique constraint: `uq_benchmark_result_per_run` on `(run_id, metric_name)`.

#### 14. `billing_plans` (future — cloud only)
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `workspace_id` | UUID | FK → `workspaces.id` ON DELETE CASCADE, NOT NULL |
| `stripe_price_id` | VARCHAR(100) | NULL |
| `input_token_price_per_million_cents` | INTEGER | NOT NULL, default `10` ($0.10 per 1M input tokens) |
| `output_token_price_per_million_cents` | INTEGER | NOT NULL, default `40` ($0.40 per 1M output tokens) |
| `is_active` | BOOLEAN | NOT NULL, default `True` |
| `created_at` | TIMESTAMPTZ | NOT NULL |
| `updated_at` | TIMESTAMPTZ | NOT NULL |

#### 15. `billing_meter_events` (cloud only)
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `workspace_id` | UUID | FK → `workspaces.id` ON DELETE CASCADE, NOT NULL |
| `stripe_meter_event_id` | VARCHAR(100) | NULL (set after successful Stripe submission) |
| `input_tokens` | INTEGER | NOT NULL, default `0` |
| `output_tokens` | INTEGER | NOT NULL, default `0` |
| `status` | VARCHAR(50) | NOT NULL, default `pending` (values: `pending`, `submitted`, `failed`) |
| `failed_at` | TIMESTAMPTZ | NULL |
| `retry_count` | INTEGER | NOT NULL, default `0` |
| `created_at` | TIMESTAMPTZ | NOT NULL |

Index: `ix_billing_meter_events_status` — on `status` (for retry queries).

#### 16. `billing_invoices` (cloud only)
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `workspace_id` | UUID | FK → `workspaces.id` ON DELETE CASCADE, NOT NULL |
| `stripe_invoice_id` | VARCHAR(100) | NULL |
| `period_start` | DATE | NOT NULL |
| `period_end` | DATE | NOT NULL |
| `total_cents` | INTEGER | NOT NULL, default `0` |
| `status` | VARCHAR(50) | NOT NULL, default `pending` (values: `pending`, `paid`, `past_due`, `cancelled`) |
| `paid_at` | TIMESTAMPTZ | NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL |
| `updated_at` | TIMESTAMPTZ | NOT NULL |

Index: `ix_billing_invoices_workspace_period` — on `(workspace_id, period_start DESC)`.

#### 17. `agent_logs`
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | BIGSERIAL | PK (sequential for high-volume log ingestion) |
| `agent_id` | UUID | FK → `agents.id` ON DELETE CASCADE, NOT NULL |
| `workspace_id` | UUID | FK → `workspaces.id` ON DELETE CASCADE, NOT NULL |
| `level` | log_level | NOT NULL (enum: `debug`, `info`, `warning`, `error`) |
| `module` | VARCHAR(100) | NULL (source module, e.g., `model_downloader`, `docker_manager`) |
| `message` | TEXT | NOT NULL |
| `stack_trace` | TEXT | NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL |

Index: `ix_agent_logs_agent_created` — on `(agent_id, created_at DESC)`.
Index: `ix_agent_logs_workspace_level_created` — on `(workspace_id, level, created_at DESC)` (for dashboard log viewer with level filtering).

### Enum Definitions

```python
import enum

class AgentStatus(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    PAUSED = "paused"
    STOPPED = "stopped"
    REMOVED = "removed"

class DeploymentStatus(str, enum.Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    STARTING = "starting"
    RUNNING = "running"
    HEALTHY = "healthy"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"

class LogLevel(str, enum.Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

class BenchmarkStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class UserRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"

class KeyStatus(str, enum.Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
```

### Alembic Migration Strategy

- **Single initial migration:** All tables are created in one revision (`0001_initial_schema.py`). The revision ID follows the format `YYYYMMDD_HHMM_initial_schema.py`.
- **Enum creation:** Alembic `op.execute("CREATE TYPE ...")` is called before any table that references the enum. Drop in reverse order on downgrade.
- **UUID extension:** `op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')` is called at the top of the migration.
- **Future migrations:** Each subsequent feature (F10 metric downsampling, F19 deployment configuration, F32 workspace settings, F35 retention) adds its own Alembic revision. The initial migration should not be edited after merge — changes go in new revisions.
- **Testing:** Alembic's `--sql` flag is used to preview the generated SQL before running against a real database. CI runs `alembic upgrade head` on an ephemeral PostgreSQL instance to verify the migration applies cleanly.

### Error Handling Requirements

- **Constraint violations:** Foreign key violations (e.g., inserting an agent with a non-existent `workspace_id`) raise `IntegrityError`. The application layer catches these and returns JSON:API 409 Conflict or 422 Unprocessable Entity as appropriate.
- **Unique constraint violations:** Duplicate email on `users.email` returns 409 Conflict with a JSON:API error body: `{"errors": [{"status": "409", "code": "UNIQUE_VIOLATION", "title": "Resource already exists", "detail": "A user with this email already exists."}]}`.
- **Null constraint violations:** SQLAlchemy's `nullable=False` combined with Pydantic validation ensures missing required fields are caught before reaching the database.
- **Migration ordering:** The workspace table is created first, followed by users, then workspace_members (depends on both), then everything else. The downgrade reverses this order. If a migration fails mid-way, Alembic rolls back the transaction (all DDL is transactional in PostgreSQL).

### Integration Points

- **F1 (Backend scaffolding):** Provides the SQLAlchemy async engine (`create_async_engine`) and session factory (`async_sessionmaker`) defined in `backend/app/database.py`. The ORM models in `backend/app/models/` are imported and registered with the `Base` metadata in `database.py` so Alembic can autogenerate migrations. The `get_db` dependency yields a session that writes to these tables.

- **F4 (JSON:API serialization):** Defines Pydantic schemas that serialize ORM model instances into JSON:API `Document` and `ResourceObject` formats. Each model gets a corresponding schema in `backend/app/schemas/` (e.g., `AgentSchema`, `ModelDeploymentSchema`).

- **F5 (Auth):** Reads from `users`, `sessions`, `password_reset_tokens` tables. Writes new users on registration, creates session rows on login, rotates refresh tokens.

- **F6 (Agent registration):** Creates rows in `agent_registration_tokens`, validates the two-phase claim flow, creates agents in the `agents` table on successful registration.

- **F10 (Metric ingestion + downsampling):** Writes high-frequency rows to `agent_metrics`, reads from it for dashboard queries, runs retention cleanup.

- **F12 (Agent log streaming):** Writes log rows to `agent_logs` via HTTP POST ingestion, reads from it for dashboard log viewer queries.

- **F22 (Running model management):** Reads and writes `model_deployments` for deployment lifecycle management.

- **F25 (Benchmark storage):** Reads and writes `benchmark_runs` and `benchmark_results` for benchmark history and comparison.

- **F27 (API keys):** Reads and writes `api_keys` for key management.

- **F29 (Usage tracking):** Writes `usage_records` for per-request token counting and cost accrual.

- **F32 (Workspace management):** Reads and writes `workspaces` and `workspace_members` for workspace CRUD and membership management.

- **F37 (Stripe billing):** Reads and writes `billing_plans`, `billing_meter_events`, and `billing_invoices` for cloud billing integration.
