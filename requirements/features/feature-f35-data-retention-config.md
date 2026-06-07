# F35: Data Retention Configuration

## Metadata
- **ID:** F35
- **Phase:** Scale
- **Effort:** Medium
- **Dependencies:** F10, F12, F32
- **Acceptance Criteria Count:** 6

## Description

Feature F35 implements the configurable data retention subsystem for ModelPrism — the UI, API, and background-job infrastructure that lets workspace administrators control how long different classes of operational data are retained before automatic deletion. Without this feature, the `agent_metrics` table (written every 2 seconds per agent via F10), the `agent_logs` table (written on every log emission via F12), and the `usage_records` table (written on every proxy request via F29) would grow unbounded, consuming ever-increasing disk and degrading query performance on the historical metric endpoints (F17) and the log viewer (F15). Retention configuration gives workspace owners a direct control to balance historical visibility against storage cost.

The feature has three architectural layers that work together. At the **configuration layer**, a new `retention` key within the `workspaces.settings` JSONB column (already defined in F3 and exposed via F32) stores per-category retention windows in days. The categories mirror the data tiers already defined in F10 (raw 2s metrics, 1-minute aggregates, 5-minute aggregates) plus agent logs (F12) and usage records (F29 — which are legally fixed at 7 years and are therefore read-only in the UI). Configuration is performed through a dedicated data-retention settings panel under Dashboard → Settings → Data Retention, rendered as a PrimeVue form with labelled sliders or dropdowns per category, a visual storage-impact indicator, and a confirmation dialog when reducing a retention window below its current value (data loss warning).

At the **execution layer**, a new `retention_service.py` module in `backend/app/services/` implements a periodic cleanup job that runs as a configurable asyncio background task within the FastAPI lifespan (F1). On each run, the service iterates over all workspaces, reads each workspace's `settings.retention` configuration, and issues batched `DELETE` statements against the relevant tables for rows whose timestamps fall outside the configured window. The cleanup respects workspace data isolation (F34) — every `DELETE` includes a `WHERE workspace_id = <uuid>` predicate, so data from one workspace is never affected by another workspace's retention policy. Deletes are throttled (max N rows per batch per table per workspace per run) to avoid long-running transactions and replication lag.

At the **feedback layer**, the dashboard displays the effective retention policy for the active workspace, shows the current row counts for each data category (via approximate `SELECT count(*)` or PostgreSQL catalog estimates), and surfaces a warning banner (via the `notifications` sub-object in workspace settings, F32) when any data category is approaching a configurable storage threshold. The workspace settings API endpoint (`PATCH /api/workspace/settings` from F32) is extended to validate retention values against allowed ranges — raw 2s metrics may be set between 1 hour (1h) and 48 hours (48h), 1-minute aggregates between 7 days and 90 days, 5-minute aggregates between 30 days and 365 days, and logs between 7 days and 90 days. Usage records are displayed with a fixed 7-year retention and are read-only in the UI.

The feature integrates with F10 (metric ingestion) by directly deleting from the `agent_metrics`, `metric_aggregates_1m`, and `metric_aggregates_5m` tables. It integrates with F12 (log streaming) by deleting from `agent_logs`. It integrates with F32 (workspace management) by reading retention values from `workspaces.settings` — the same JSONB column that stores theme defaults, rate-limit defaults, and notification preferences. And it integrates with F34 (workspace data isolation) by ensuring every cleanup query is scoped to exactly one workspace. The cleanup job itself is exposed as a JSON:API admin/debug endpoint (`POST /api/workspace/retention/run`) that triggers an immediate on-demand execution, and its schedule and last-run timestamp are readable via `GET /api/workspace/retention`.

## Concrete Examples (Specification by Example)

### Example 1: Admin Configures 7-Day Log Retention from 30-Day Default

- **Input:** A workspace admin navigates to Dashboard → Settings → Data Retention, finds the "Agent Logs" row showing the current slider value of `30 days`, drags it down to `7 days`, and clicks "Save Changes".

- **Action:** The frontend sends `PATCH /api/workspace/settings` with a JSON:API payload containing only the retention sub-object:

  ```json
  {
    "data": {
      "type": "workspaceSettings",
      "id": "aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa",
      "attributes": {
        "retention": {
          "rawMetricsHours": 24,
          "aggregate1mDays": 30,
          "aggregate5mDays": 365,
          "logDays": 7
        }
      }
    }
  }
  ```

- **Expected Output:** HTTP 200 OK. The `workspaces.settings` JSONB column is updated. The response returns the full settings resource including the updated retention values:

  ```json
  {
    "data": {
      "type": "workspaceSettings",
      "id": "aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa",
      "attributes": {
        "name": "Alice's Workspace",
        "slug": "alices-workspace",
        "retention": {
          "rawMetricsHours": 24,
          "aggregate1mDays": 30,
          "aggregate5mDays": 365,
          "logDays": 7
        },
        "updatedAt": "2026-06-07T14:00:00+00:00"
      }
    }
  }
  ```

- **Side effect:** On the next run of the background retention cleanup job (scheduled daily at 03:00 UTC), the job reads `logDays: 7` for this workspace and issues `DELETE FROM agent_logs WHERE workspace_id = 'aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa' AND created_at < NOW() - INTERVAL '7 days'`. All log entries older than 7 days are removed from the workspace.

### Example 2: Reducing Raw Metrics Retention Triggers Data Loss Warning

- **Input:** An admin attempts to reduce `rawMetricsHours` from `24` to `6` on a workspace that has accumulated 18 hours of raw metric data.

- **Action — Pre-submit check:** The frontend detects the decrease (previous value 24, new value 6) and displays a PrimeVue confirmation dialog: *"Reducing raw metrics retention from 24 hours to 6 hours will permanently delete approximately 12 hours of high-resolution metric data (≈ 21,600 rows per active agent). This action cannot be undone. Are you sure?"*

- **Action — Confirmation:** The user confirms. The `PATCH /api/workspace/settings` request includes an additional `meta.confirmDataLoss: true` flag:

  ```json
  {
    "data": {
      "type": "workspaceSettings",
      "id": "aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa",
      "attributes": {
        "retention": { "rawMetricsHours": 6 }
      }
    },
    "meta": {
      "confirmDataLoss": true
    }
  }
  ```

- **Expected Output:** HTTP 200 OK. If the user had cancelled the confirmation dialog, no request would have been sent. If the `PATCH` is submitted without `meta.confirmDataLoss` when the new value is lower than the previous value, the backend returns HTTP 422 with:

  ```json
  {
    "errors": [
      {
        "status": "422",
        "code": "retention_reduction_confirmation_required",
        "title": "Data loss confirmation required",
        "detail": "Reducing rawMetricsHours from 24 to 6 will permanently delete existing data. Set 'meta.confirmDataLoss' to 'true' to confirm."
      }
    ]
  }
  ```

### Example 3: Daily Cleanup Job Removes Expired Data Across All Workspaces

- **Input:** The background retention cleanup job runs at its scheduled time (03:00 UTC on 2026-06-08). Three workspaces exist with the following retention configurations:

  | Workspace | rawMetricsHours | aggregate1mDays | aggregate5mDays | logDays |
  |-----------|----------------|-----------------|-----------------|---------|
  | ws-alpha  | 24             | 30              | 365             | 30      |
  | ws-beta   | 48             | 90              | 365             | 7       |
  | ws-gamma  | 1              | 14              | 90              | 90      |

- **Action:** The retention service in `backend/app/services/retention_service.py` executes the following logic for each workspace:

  1. For `ws-alpha`: Deletes `agent_metrics` rows with `ts < NOW() - INTERVAL '24 hours'`, `metric_aggregates_1m` rows with `ts < NOW() - INTERVAL '30 days'`, `metric_aggregates_5m` rows with `ts < NOW() - INTERVAL '365 days'`, and `agent_logs` rows with `created_at < NOW() - INTERVAL '30 days'`. The `usage_records` table is skipped (fixed 7-year retention, never deleted by job).
  2. For `ws-beta`: Same categories but `logDays` is 7, so logs older than 7 days are purged. `rawMetricsHours` is 48, so only raw metrics older than 48 hours are deleted.
  3. For `ws-gamma`: `rawMetricsHours` is 1 — only the most recent hour of raw metrics is kept. `aggregate1mDays` is 14 and `aggregate5mDays` is 90, so both aggregate tiers are trimmed aggressively.

  The service logs a summary:

  ```
  [retention_service] Run #142 completed in 3.2s
    ws-alpha: agent_metrics=41820 rows, agent_logs=1560 rows, aggregates=342 rows
    ws-beta:  agent_metrics=21200 rows, agent_logs=48900 rows, aggregates=0 rows
    ws-gamma: agent_metrics=78400 rows, agent_logs=0 rows, aggregates=18900 rows
  ```

- **Expected Output:** Each workspace's data tables are trimmed to the configured windows. The total count of deleted rows is recorded in a `retention_cleanup_log` table (for auditing). The job stores its completion timestamp and row-count summary in a new `retention_run_history` JSONB field on the workspace settings, or in a dedicated `cleanup_job_runs` table (whichever approach is chosen during implementation).

### Example 4: On-Demand Retention Run Triggered via Admin API

- **Input:** A workspace admin clicks "Run Cleanup Now" in the Data Retention settings UI.

- **Action:** The frontend calls `POST /api/workspace/retention/run` with a JSON:API request:

  ```json
  {
    "data": {
      "type": "retentionRun",
      "attributes": {}
    }
  }
  ```

- **Expected Output:** HTTP 202 Accepted. Response body:

  ```json
  {
    "data": {
      "type": "retentionRun",
      "id": "rr-55555555-6666-7777-8888-999999999999",
      "attributes": {
        "status": "running",
        "startedAt": "2026-06-07T15:30:00+00:00",
        "workspaceId": "aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa",
        "trigger": "manual"
      },
      "meta": {
        "message": "Retention cleanup started. Results will be available via GET /api/workspace/retention."
      }
    }
  }
  ```

  After job completion, `GET /api/workspace/retention` returns the latest run results:

  ```json
  {
    "data": {
      "type": "retentionStatus",
      "id": "aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa",
      "attributes": {
        "currentPolicy": {
          "rawMetricsHours": 24,
          "aggregate1mDays": 30,
          "aggregate5mDays": 365,
          "logDays": 30,
          "usageRecordsDays": 2555
        },
        "estimatedRowCounts": {
          "agentMetrics": 142000,
          "aggregate1m": 43200,
          "aggregate5m": 105120,
          "agentLogs": 28500,
          "usageRecords": 1250000
        },
        "lastRun": {
          "startedAt": "2026-06-07T15:30:00+00:00",
          "completedAt": "2026-06-07T15:30:03+00:00",
          "rowsDeleted": {
            "agentMetrics": 41820,
            "agentLogs": 1560,
            "aggregate1m": 288,
            "aggregate5m": 54
          },
          "durationMs": 3200
        },
        "nextScheduledRun": "2026-06-08T03:00:00+00:00",
        "schedule": "daily at 03:00 UTC"
      }
    }
  }
  ```

### Example 5: Workspace Switches to Aggressive Retention and Dashboard Updates Live Estimates

- **Input:** A workspace admin reduces `aggregate1mDays` from `365` to `14`. The frontend shows a confirmation warning: *"Reducing 1-minute aggregate retention from 365 days to 14 days will delete approximately 351 days of historical aggregate data (≈ 505,440 rows per active agent)."*

- **Action (frontend):** The confirmation modal uses an approximate estimate based on agent count × 1,440 rows/day/agent × 351 days to display the storage impact. The admin confirms.

- **Action (backend):** `PATCH /api/workspace/settings` with `meta.confirmDataLoss: true` succeeds.

- **Action (dashboard):** After saving, the dashboard's Data Retention page re-fetches retention status via `GET /api/workspace/retention`. The `estimatedRowCounts.aggregate1m` value drops dramatically (from, say, 525,600 to 20,160 for a single agent). The admin sees the updated numbers immediately.

- **Expected Output:** The `estimatedRowCounts` section in the response reflects PostgreSQL's approximate row count (`reltuples` from `pg_class`) for `metric_aggregates_1m` filtered by the active workspace. The next scheduled cleanup job will delete the excess rows. The admin has a clear visual understanding of the storage impact of their change.

## Acceptance Criteria

- **ACF35-1: Retention settings UI renders all tiers with validated ranges** — The Data Retention settings page under Dashboard → Settings → Data Retention displays five categories: raw metrics (2s resolution) with a range of 1–48 hours (default 24), 1-minute aggregates with a range of 7–90 days (default 30), 5-minute aggregates with a range of 30–365 days (default 365), agent logs with a range of 7–90 days (default 30), and usage records as read-only at 2,555 days (7 years). Each editable category uses a PrimeVue `InputNumber` with a labelled suffix ("hours" or "days") or a `SelectButton` slider. Values outside the allowed range are rejected client-side and server-side with a validation error. Changes are not persisted until the user clicks "Save Changes".

- **ACF35-2: Reducing any retention window below its current value triggers a two-step confirmation** — When the user submits a retention value that is lower than the previously persisted value for that category, two things must happen: (a) the frontend displays a PrimeVue confirmation dialog that explicitly states which category is being reduced, the magnitude of the reduction (e.g., "from 30 days to 7 days"), and an approximate row-count estimate of data that will be permanently deleted; and (b) the backend requires `meta.confirmDataLoss: true` in the request body. If the confirmation is missing or `false`, the backend returns HTTP 422 with code `retention_reduction_confirmation_required`. This prevents accidental data loss from a rogue API call or mis-click.

- **ACF35-3: Background retention cleanup job runs on schedule and enforces per-workspace policies** — The `retention_service.py` module implements a scheduled task that runs daily at a configurable time (default 03:00 UTC). On each run, the task iterates all workspaces that have a non-null `settings.retention` object, issues scoped `DELETE` statements against `agent_metrics` (by `ts` column), `metric_aggregates_1m` (by `ts`), `metric_aggregates_5m` (by `ts`), and `agent_logs` (by `created_at`), applying the workspace's retention window as a `WHERE ts < NOW() - INTERVAL 'N days/hours'` filter plus `AND workspace_id = <uuid>`. The `usage_records` table is never touched. Each batch `DELETE` is limited to 50,000 rows per table per workspace per run to avoid transaction timeouts. The job logs a summary and stores its result in a `retention_run_history` table or similar audit trail. The schedule is managed by an asyncio background task started in the FastAPI lifespan (F1), not by an external cron daemon.

- **ACF35-4: On-demand retention run is available via API with audit trail** — A workspace admin or owner can trigger an immediate retention cleanup by calling `POST /api/workspace/retention/run`. The endpoint returns HTTP 202 Accepted immediately, spawns an asyncio background task, and executes the same cleanup logic as the scheduled job but scoped to the caller's active workspace (F34). Only users with role `admin` or `owner` (F33) may call this endpoint. The run is logged in the audit trail with a UUID, start time, duration, rows-deleted counts per table, and the trigger type (`manual`). If a run is already in progress for the same workspace, the endpoint returns HTTP 409 with code `cleanup_already_running`. The results are queryable via `GET /api/workspace/retention`.

- **ACF35-5: Retention status endpoint exposes current policy, row estimates, and last-run metrics** — `GET /api/workspace/retention` returns a JSON:API resource object containing: the current retention policy values (read from `workspaces.settings.retention`), estimated row counts for each data category within the active workspace (obtained via `SELECT COUNT(*)` on small tables or PostgreSQL `pg_class.reltuples` estimates for large tables), the last completed cleanup run's metadata (timestamp, duration, rows deleted per table), and the next scheduled run time. This endpoint requires authentication (F5) and workspace membership (F32/F34). The frontend polls this endpoint on page load to populate the Data Retention settings panel and the storage-impact indicator.

- **ACF35-6: Usage records are never affected by retention changes** — The `usage_records` table has a fixed retention of 7 years (2,555 days) as required by tax and compliance regulations. The retention settings UI renders usage records as a read-only field displaying `2,555 days` with a lock icon. The `PATCH /api/workspace/settings` endpoint silently ignores any attempt to modify `usageRecordsDays` in the `retention` sub-object (it neither rejects nor stores the value). The background cleanup job never issues `DELETE` against `usage_records`. This behaviour is verified by an integration test that configures all retention values to their minimum and confirms that `usage_records` row count remains unchanged after the cleanup job runs.

## Technical Notes

### Implementation Plan

1. **Backend: retention configuration validation** (`backend/app/schemas/workspace.py` or new `backend/app/schemas/retention.py`)
   - Define a `RetentionConfig` Pydantic model within the workspace settings schema:
     ```python
     class RetentionConfig(BaseModel):
         raw_metrics_hours: int = Field(default=24, ge=1, le=48)
         aggregate_1m_days: int = Field(default=30, ge=7, le=90)
         aggregate_5m_days: int = Field(default=365, ge=30, le=365)
         log_days: int = Field(default=30, ge=7, le=90)
     ```
   - Add a `retention: RetentionConfig` field to the `WorkspaceSettings` Pydantic model used by `PATCH /api/workspace/settings`.
   - In the `PATCH` handler, when `retention` is present, compare each new value against the current value stored in `workspaces.settings`. If any value is strictly less than the stored value and `meta.confirmDataLoss` is not `true`, return HTTP 422 with the appropriate error.

2. **Backend: retention service** (`backend/app/services/retention_service.py`)
   - Main entry point: `async def run_retention_cleanup(workspace_id: uuid.UUID | None = None) -> RetentionRunResult`
   - When `workspace_id` is `None`, iterate all workspaces. When set, scope to that workspace only.
   - Per workspace, per table, build and execute:
     ```sql
     DELETE FROM agent_metrics
     WHERE workspace_id = :ws_id
       AND ts < NOW() - CAST(:interval AS INTERVAL)
     LIMIT 50000;
     ```
   - Repeat the batched delete in a loop until zero rows are affected (handle the case where more than 50,000 rows exceed the window).
   - Write a `RetentionRunResult` record to a new `cleanup_job_runs` table:
     ```sql
     CREATE TABLE cleanup_job_runs (
         id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
         workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
         trigger VARCHAR(20) NOT NULL DEFAULT 'scheduled',  -- 'scheduled' | 'manual'
         started_at TIMESTAMPTZ NOT NULL,
         completed_at TIMESTAMPTZ,
         duration_ms INTEGER,
         rows_deleted JSONB NOT NULL DEFAULT '{}',
         -- e.g. {"agent_metrics": 41820, "agent_logs": 1560, "aggregate_1m": 288, "aggregate_5m": 54}
         status VARCHAR(20) NOT NULL DEFAULT 'running',  -- 'running' | 'completed' | 'failed'
         error_message TEXT NULL,
         created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
     );
     CREATE INDEX ix_cleanup_job_runs_ws_started ON cleanup_job_runs(workspace_id, started_at DESC);
     ```
   - Schedule: start an asyncio `BackgroundTask` (or use `asyncio.create_task` in the lifespan) that loops with `while True: await asyncio.sleep(until_next_03_utc())`. The interval is recalculated after each run. The schedule time (default 03:00 UTC) is configurable via `config.py` settings (e.g., `RETENTION_CLEANUP_HOUR = 3`).

3. **Backend: retention API endpoints** (`backend/app/api/workspace.py` — extend the existing workspace routes, or create `backend/app/api/retention.py`)
   - `GET /api/workspace/retention` — Returns retention status for the active workspace. Implementation:
     1. Read `workspaces.settings.retention`.
     2. Query estimated row counts via `SELECT reltuples FROM pg_class WHERE relname = 'agent_metrics'` (for large tables) or `SELECT COUNT(*) ... WHERE workspace_id = :ws_id` (for small tables). If using `reltuples`, multiply by the fraction of rows owned by this workspace: `reltuples * (workspace_rows / total_rows)`. Prefer `COUNT(*)` for tables under 1M rows.
     3. Fetch the most recent `cleanup_job_runs` row for this workspace with `status = 'completed'`.
     4. Calculate `nextScheduledRun` from the config hour.
   - `POST /api/workspace/retention/run` — Triggers immediate on-demand cleanup. Check role (F33). If a run with `status = 'running'` exists for this workspace, return 409. Spawn background task, return 202.
   - Extend `PATCH /api/workspace/settings` to validate `retention` sub-object and enforce the `confirmDataLoss` contract.

4. **Frontend: Data Retention settings UI** (new component `frontend/app/components/workspace/DataRetentionForm.vue`)
   - PrimeVue `Card` containing a `Form` with labelled `InputNumber` controls for each editable category. Each control shows min/max as hint text. A read-only field for usage records with a lock icon.
   - A "storage impact" section computed client-side: estimated row counts from the `GET /api/workspace/retention` response, rendered as a horizontal stacked bar or mini table per category with the estimated disk usage (avg row size × estimated count, e.g., `~350 bytes per agent_metrics row`).
   - On "Save Changes", the component compares old vs new values. For any reduction, it mounts a PrimeVue `Dialog` with text: *"Reducing {categoryLabel} from {oldValue} to {newValue} will permanently delete approximately {estimatedRows.toLocaleString()} rows. This action cannot be undone. Type CONFIRM to proceed."* — with a text input requiring the literal word `CONFIRM` before the "Confirm Data Loss" button is enabled.
   - The form sends the `PATCH` request and on success refreshes the retention status from `GET /api/workspace/retention`. On 422 with `retention_reduction_confirmation_required`, the dialog re-opens.

5. **Frontend: routing and integration**
   - The Data Retention settings page is accessible at `/dashboard/settings` → tab "Data Retention" (or a dedicated sub-route `/dashboard/settings/retention`). The existing settings page at `frontend/app/pages/dashboard/settings/index.vue` is extended with a tabbed layout (PrimeVue `TabPanel`): General, Members (F32), Data Retention (F35).
   - A new Pinia store or composable `useRetention.ts` handles:
     ```typescript
     // frontend/app/composables/useRetention.ts
     export const useRetention = () => {
       const { data, refresh, pending } = useFetch('/api/workspace/retention', {
         headers: { 'Content-Type': 'application/vnd.api+json' }
       })
       const triggerCleanup = async () => {
         return $fetch('/api/workspace/retention/run', { method: 'POST' })
       }
       return { data, refresh, pending, triggerCleanup }
     }
     ```

### Edge Cases

- **New workspaces with no retention config:** If `workspaces.settings` is `NULL` or lacks a `retention` key, the cleanup job uses the defaults defined in `RetentionConfig` (24h raw, 30d aggregate_1m, 365d aggregate_5m, 30d logs). The UI renders the defaults when the API returns no retention configuration for the workspace.
- **Workspace deletion (F32):** When a workspace is hard-deleted (after the 7-day grace period), the `ON DELETE CASCADE` foreign keys from F3 handle all child table cleanup — the retention job does not need special handling for deleted workspaces because the rows are already removed by the cascade.
- **Concurrent cleanup runs:** The service uses a Redis-backed distributed lock (key: `retention:cleanup:lock`) to prevent two backend instances from running the cleanup simultaneously. The lock TTL is 5 minutes. If the lock cannot be acquired, the run is skipped and logged at `warning` level.
- **Large workspaces with millions of rows:** The `LIMIT 50000` per batch prevents long-running transactions. If the job needs multiple batches for the same table, it commits between batches. This is safe because all deletions are idempotent — deleting already-deleted rows is a no-op.
- **User changes retention to a shorter window while cleanup is running:** The cleanup job reads the current retention policy at the start of its per-workspace loop. If a concurrent `PATCH` updates the policy mid-run, the job may use the old value for that workspace or the new value depending on timing. This is acceptable because the maximum discrepancy is one daily cycle — the next run will apply the updated policy. To tighten this, the job could read the policy per table rather than per workspace, but this adds complexity without meaningful benefit for a daily batch job.

### Integration Points

- **F3 (Database schema):** The `workspaces.settings` JSONB column stores the `retention` sub-object. The `cleanup_job_runs` table is a new schema addition (requires a new Alembic migration). No columns are added to existing tables.
- **F10 (Backend metric ingestion):** The retention cleanup job deletes from `agent_metrics`, `metric_aggregates_1m`, and `metric_aggregates_5m` — these tables are written by F10's ingestion pipeline and the downsampler service. The downsample thresholds (raw kept 24h, 1m kept 30d, 5m kept 1y) match the retention defaults exactly, so under default configuration the downsampler naturally phases out raw data around the same time the retention job would delete it. Under custom retention, the retention job takes precedence.
- **F12 (Agent log streaming):** The cleanup job deletes from `agent_logs` by `created_at`. Logs are immutable after insertion, so no special handling is needed for in-flight logs.
- **F16 (WebSocket broadcast):** The retention job does not interact with live WebSocket streams. Logs and metrics that are deleted from the database while a dashboard client is viewing them will simply stop appearing on future scrolls. Real-time broadcasts are unaffected.
- **F17 (Time range selector):** The historical query endpoints already select from the correct aggregate table based on the requested time range (raw for < 1h, 1m aggregate for < 30d, 5m aggregate for < 1y). Shortening retention via F35 may cause queries for time ranges that now exceed the retention window to return fewer data points — this is expected behaviour. The time-range selector UI could optionally query the retention endpoint and disable range options that exceed the workspace's retention for the requested metric granularity.
- **F29 (Token counting/usage):** Usage records are exempt from retention deletion (fixed 7-year requirement). The `GET /api/workspace/retention` endpoint displays this fixed value and the UI renders it as read-only.
- **F32 (Workspace management):** The retention settings are stored in `workspaces.settings.retention` and are exposed through the same `PATCH /api/workspace/settings` endpoint. The workspace serializer in `backend/app/schemas/workspace.py` is extended to include the `retention` sub-object.
- **F33 (Role-based access):** Only `admin` or `owner` roles may modify retention settings or trigger an on-demand cleanup. Members and viewers see the retention status page in read-only mode (all controls disabled). This is enforced by the existing RBAC middleware (F33) on the `PATCH /api/workspace/settings` endpoint and the `POST /api/workspace/retention/run` endpoint.
- **F34 (Workspace data isolation):** Every retention-related query (both the config read/write and the cleanup DELETE statements) includes a `WHERE workspace_id = <uuid>` clause. The `GET /api/workspace/retention` endpoint is scoped to the caller's active workspace. On-demand cleanup runs are scoped to exactly one workspace.

### File Changes Summary

| File | Change |
|------|--------|
| `backend/app/models/cleanup_job_run.py` | New ORM model for `cleanup_job_runs` table |
| `backend/app/services/retention_service.py` | New retention cleanup service with batch delete logic, scheduling, and distributed locking |
| `backend/app/api/retention.py` | New or extended router with `GET /api/workspace/retention` and `POST /api/workspace/retention/run` |
| `backend/app/api/workspace.py` | Extend `PATCH /api/workspace/settings` to validate retention sub-object and `confirmDataLoss` |
| `backend/app/schemas/workspace.py` | Add `RetentionConfig` model and integrate into `WorkspaceSettings` |
| `backend/app/config.py` | Add `RETENTION_CLEANUP_HOUR` (default 3) and `RETENTION_CLEANUP_BATCH_SIZE` (default 50000) settings |
| `backend/app/main.py` | Start retention background task in lifespan |
| `backend/alembic/versions/XXXX_add_cleanup_job_runs.py` | New Alembic migration for `cleanup_job_runs` table |
| `frontend/app/components/workspace/DataRetentionForm.vue` | New PrimeVue form component for retention settings |
| `frontend/app/composables/useRetention.ts` | New composable for retention API calls |
| `frontend/app/pages/dashboard/settings/index.vue` | Extend with tabbed layout including Data Retention tab |

## Depends on
- **F10** (Backend metric ingestion) — provides the `agent_metrics`, `metric_aggregates_1m`, and `metric_aggregates_5m` tables that the retention cleanup job operates on
- **F12** (Agent log streaming) — provides the `agent_logs` table that the retention cleanup job prunes
- **F32** (Workspace management) — provides the `workspaces.settings` JSONB column that stores retention configuration, and the `PATCH /api/workspace/settings` endpoint extended by F35
- **F34** (Workspace data isolation) — ensures retention cleanup queries respect workspace boundaries
