# F25: Benchmark storage + history

## Metadata
- **ID:** F25
- **Phase:** Enhancement
- **Effort:** Medium
- **Dependencies:** F3, F10
- **Acceptance Criteria Count:** 6

## Description

After a benchmark run completes execution on the agent (F24), its raw results — TTFT latencies, throughput, token counts, error rates — must be persisted to PostgreSQL so users can review, filter, and search historical runs from the dashboard. F25 provides the storage backend and read-side API for benchmark persistence, covering the `benchmark_runs` and `benchmark_results` tables defined in F3, a full CRUD REST API surface using JSON:API 1.0 format, and the frontend pages and composables that list, filter, and display individual benchmark results.

The feature is the persistence tier between the benchmark runner (F24), which triggers and streams results from the agent, and the benchmark comparison system (F26), which aggregates multiple completed runs into side-by-side visualisations. When F24's agent-side runner finishes a benchmark, the agent sends a `command_result` message containing the full result payload over WebSocket. The backend's `benchmark_runner.py` service (F24) calls into the storage service defined here to persist the run config, individual metric values, and the raw per-request latency distribution as a JSONB payload. Once stored, the data is immediately queryable via the `GET /api/benchmarks` endpoint, which supports pagination, field-based filtering, full-text search on model names, and ordering by any combination of `created_at`, `throughput`, or model name.

On the frontend, the benchmark history page at `/dashboard/benchmarks/` renders a PrimeVue `DataTable` with sortable columns (model name, throughput, TTFT p99, date, configuration summary) and a search input that filters the list in real time. Each row links to a detail page at `/dashboard/benchmarks/[id]` that shows the full configuration, all metric values as a structured summary, and optionally a latency distribution histogram rendered from the stored raw data. The page integrates with the workspace data isolation layer (F34) so each workspace sees only its own benchmark runs. Benchmark runs and results are immutable once stored — no UPDATE paths exist in the API.

## Concrete Examples (Specification by Example)

### Example 1: Agent Completes Benchmark and Sends Results via WebSocket

- **Input:** Agent `ag_cyan_koala_42` completes a benchmark run on model deployment `md_qwen_001` (Qwen2.5-72B-Instruct, workspace `ws_abc`). The agent sends a `command_result` WebSocket message with the full benchmark payload:

```json
{
  "type": "command_result",
  "command_id": "cmd_bench_001",
  "status": "success",
  "result": {
    "benchmark_id": "b8f3a1d0-e29b-41d4-a716-446655440001",
    "status": "completed",
    "config": {
      "num_requests": 1000,
      "concurrency": 10,
      "request_rate": "max",
      "input_length": 2048,
      "output_length": 512,
      "dataset": "sharegpt"
    },
    "metrics": {
      "ttft_p50_ms": 285.3,
      "ttft_p95_ms": 612.4,
      "ttft_p99_ms": 945.1,
      "tpot_p50_ms": 42.1,
      "tpot_p95_ms": 98.7,
      "tpot_p99_ms": 152.3,
      "throughput_req_per_sec": 37.2,
      "throughput_tok_per_sec": 1850.5,
      "total_tokens": 512000,
      "error_count": 2,
      "error_rate": 0.002,
      "itl_p50_ms": 38.4,
      "itl_p95_ms": 91.2,
      "itl_p99_ms": 145.8,
      "e2e_latency_p50_ms": 4520.1,
      "e2e_latency_p99_ms": 15230.5,
      "duration_seconds": 28.7
    },
    "latency_distribution": [
      {"bucket_ms": 100, "count": 12},
      {"bucket_ms": 200, "count": 89},
      {"bucket_ms": 300, "count": 245},
      {"bucket_ms": 400, "count": 318},
      {"bucket_ms": 500, "count": 187},
      {"bucket_ms": 600, "count": 94},
      {"bucket_ms": 800, "count": 42},
      {"bucket_ms": 1000, "count": 11},
      {"bucket_ms": 1500, "count": 2}
    ],
    "started_at": "2026-06-07T14:30:00.000Z",
    "completed_at": "2026-06-07T14:30:28.700Z"
  }
}
```

- **Action:** The backend command handler in `backend/app/services/benchmark_runner.py` receives the result, instantiates the `BenchmarkStorageService.enrich_and_persist()` method. This method:
  1. Validates the payload against `BenchmarkResultComplete` from `backend/app/schemas/benchmark.py`.
  2. Updates the `benchmark_runs` row (created by F24 when the benchmark was triggered): sets `status = "completed"`, `completed_at`, and `raw_latency_distribution` (the JSONB histogram).
  3. Inserts one row per metric into `benchmark_results` — 17 rows total, each with `run_id`, `metric_name`, `metric_value`, and `unit`.

- **Expected Output:** The `benchmark_runs` table has one updated row:

| Column | Value |
|--------|-------|
| `id` | `b8f3a1d0-e29b-41d4-a716-446655440001` |
| `workspace_id` | `7c9d1b2a-3e4f-5a6b-7c8d-9e0f1a2b3c4d` |
| `agent_id` | `550e8400-e29b-41d4-a716-446655440000` |
| `model_deployment_id` | `d4f1e2c3-5a6b-7c8d-9e0f-1a2b3c4d5e6f` |
| `created_by` | `a1b2c3d4-e5f6-7890-abcd-ef1234567890` |
| `status` | `completed` |
| `config` | `{"num_requests": 1000, "concurrency": 10, ...}` |
| `raw_data` | `{"latency_distribution": [...], "metrics": {...}}` |
| `started_at` | `2026-06-07T14:30:00.000Z` |
| `completed_at` | `2026-06-07T14:30:28.700Z` |

The `benchmark_results` table receives 17 rows including:

| `run_id` | `metric_name` | `metric_value` | `unit` |
|----------|---------------|----------------|--------|
| `b8f3a1d0...` | `ttft_p50_ms` | `285.3` | `ms` |
| `b8f3a1d0...` | `ttft_p99_ms` | `945.1` | `ms` |
| `b8f3a1d0...` | `throughput_tok_per_sec` | `1850.5` | `tok/s` |
| `b8f3a1d0...` | `error_rate` | `0.002` | `%` |
| `b8f3a1d0...` | `duration_seconds` | `28.7` | `s` |

The `raw_data` JSONB column stores the latency distribution histogram verbatim for F26 to render as bar charts.

### Example 2: User Lists All Benchmark Runs with Filters

- **Input:** A user in workspace `ws_abc` navigates to the benchmark history page at `/dashboard/benchmarks/` and types "qwen" into the search box. The page sends:

```
GET /api/benchmarks?filter[model]=qwen&sort=-throughput_tok_per_sec&page[limit]=20
Authorization: Bearer <jwt>
```

- **Action:** The backend query in `backend/app/api/benchmarks.py` builds a query joining `benchmark_runs` with `model_deployments` (to get `hf_model_id` and `model_name`), applies a case-insensitive ILIKE filter on `model_deployments.model_name` or `model_deployments.hf_model_id`, orders by the throughput metric extracted from the latest `benchmark_results` row for each run, and paginates to 20 results. The workspace filter is injected via the JWT claim.

- **Expected Output:** JSON:API response (truncated):

```json
{
  "data": [
    {
      "type": "benchmark-runs",
      "id": "b8f3a1d0-e29b-41d4-a716-446655440001",
      "attributes": {
        "model_name": "Qwen2.5-72B-Instruct",
        "hf_model_id": "Qwen/Qwen2.5-72B-Instruct",
        "status": "completed",
        "config_summary": {
          "num_requests": 1000,
          "concurrency": 10,
          "dataset": "sharegpt"
        },
        "throughput_tok_per_sec": 1850.5,
        "ttft_p99_ms": 945.1,
        "error_rate": 0.002,
        "started_at": "2026-06-07T14:30:00.000Z",
        "completed_at": "2026-06-07T14:30:28.700Z",
        "duration_seconds": 28.7
      },
      "relationships": {
        "agent": {
          "data": { "type": "agents", "id": "550e8400-e29b-41d4-a716-446655440000" }
        },
        "model_deployment": {
          "data": { "type": "model-deployments", "id": "d4f1e2c3-5a6b-7c8d-9e0f-1a2b3c4d5e6f" }
        }
      }
    },
    {
      "type": "benchmark-runs",
      "id": "c9f4b2e1-3f5a-6b7c-8d9e-0f1a2b3c4d5e",
      "attributes": {
        "model_name": "Qwen2.5-32B-Instruct-GPTQ-Int4",
        "hf_model_id": "Qwen/Qwen2.5-32B-Instruct-GPTQ-Int4",
        "status": "completed",
        "config_summary": {
          "num_requests": 500,
          "concurrency": 5,
          "dataset": "sonnet"
        },
        "throughput_tok_per_sec": 3200.1,
        "ttft_p99_ms": 520.3,
        "error_rate": 0.0,
        "started_at": "2026-06-07T13:00:00.000Z",
        "completed_at": "2026-06-07T13:01:15.300Z",
        "duration_seconds": 75.3
      },
      "relationships": {
        "agent": {
          "data": { "type": "agents", "id": "550e8400-e29b-41d4-a716-446655440000" }
        },
        "model_deployment": {
          "data": { "type": "model-deployments", "id": "e5f2a3b4-6c7d-8e9f-0a1b-2c3d4e5f6a7b" }
        }
      }
    }
  ],
  "meta": {
    "total": 2,
    "count": 2,
    "offset": 0,
    "limit": 20
  },
  "links": {
    "self": "/api/benchmarks?filter%5Bmodel%5D=qwen&sort=-throughput_tok_per_sec&page%5Blimit%5D=20",
    "first": "/api/benchmarks?filter%5Bmodel%5D=qwen&sort=-throughput_tok_per_sec&page%5Blimit%5D=20&page%5Boffset%5D=0"
  }
}
```

### Example 3: User Views Single Benchmark Detail with Full Metrics

- **Input:** A user clicks on a completed benchmark run row, navigating to `/dashboard/benchmarks/b8f3a1d0-e29b-41d4-a716-446655440001`. The frontend calls:

```
GET /api/benchmarks/b8f3a1d0-e29b-41d4-a716-446655440001?include=agent,model-deployment
Authorization: Bearer <jwt>
```

- **Action:** The backend fetches the `benchmark_runs` row by ID, verifies workspace ownership, includes the `benchmark_results` rows as a `metrics` attribute, resolves the `include` relationships to return `agent` and `model_deployment` as included resources, and serialises the `raw_data` JSONB column containing the latency distribution histogram.

- **Expected Output:** JSON:API response (main resource only, relationships truncated):

```json
{
  "data": {
    "type": "benchmark-runs",
    "id": "b8f3a1d0-e29b-41d4-a716-446655440001",
    "attributes": {
      "model_name": "Qwen2.5-72B-Instruct",
      "hf_model_id": "Qwen/Qwen2.5-72B-Instruct",
      "status": "completed",
      "config": {
        "num_requests": 1000,
        "concurrency": 10,
        "request_rate": "max",
        "input_length": 2048,
        "output_length": 512,
        "dataset": "sharegpt"
      },
      "metrics": [
        {"name": "ttft_p50_ms", "value": 285.3, "unit": "ms"},
        {"name": "ttft_p95_ms", "value": 612.4, "unit": "ms"},
        {"name": "ttft_p99_ms", "value": 945.1, "unit": "ms"},
        {"name": "tpot_p50_ms", "value": 42.1, "unit": "ms"},
        {"name": "tpot_p95_ms", "value": 98.7, "unit": "ms"},
        {"name": "tpot_p99_ms", "value": 152.3, "unit": "ms"},
        {"name": "throughput_req_per_sec", "value": 37.2, "unit": "req/s"},
        {"name": "throughput_tok_per_sec", "value": 1850.5, "unit": "tok/s"},
        {"name": "total_tokens", "value": 512000, "unit": "tokens"},
        {"name": "error_count", "value": 2, "unit": null},
        {"name": "error_rate", "value": 0.002, "unit": "%"},
        {"name": "itl_p50_ms", "value": 38.4, "unit": "ms"},
        {"name": "itl_p95_ms", "value": 91.2, "unit": "ms"},
        {"name": "itl_p99_ms", "value": 145.8, "unit": "ms"},
        {"name": "e2e_latency_p50_ms", "value": 4520.1, "unit": "ms"},
        {"name": "e2e_latency_p99_ms", "value": 15230.5, "unit": "ms"},
        {"name": "duration_seconds", "value": 28.7, "unit": "s"}
      ],
      "latency_distribution": [
        {"bucket_ms": 100, "count": 12},
        {"bucket_ms": 200, "count": 89},
        {"bucket_ms": 300, "count": 245},
        {"bucket_ms": 400, "count": 318},
        {"bucket_ms": 500, "count": 187},
        {"bucket_ms": 600, "count": 94},
        {"bucket_ms": 800, "count": 42},
        {"bucket_ms": 1000, "count": 11},
        {"bucket_ms": 1500, "count": 2}
      ],
      "started_at": "2026-06-07T14:30:00.000Z",
      "completed_at": "2026-06-07T14:30:28.700Z",
      "duration_seconds": 28.7
    },
    "relationships": {
      "agent": {
        "data": { "type": "agents", "id": "550e8400-e29b-41d4-a716-446655440000" }
      },
      "model_deployment": {
        "data": { "type": "model-deployments", "id": "d4f1e2c3-5a6b-7c8d-9e0f-1a2b3c4d5e6f" }
      }
    }
  },
  "included": [
    {
      "type": "agents",
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "attributes": {
        "friendly_name": "cyan-koala-42",
        "hardware_info": {
          "gpu_model": "NVIDIA A100-SXM4-80GB",
          "gpu_count": 2
        }
      }
    }
  ]
}
```

### Example 4: User Deletes an Old Benchmark Run

- **Input:** A user clicks the "Delete" action on benchmark run `c9f4b2e1-...` from the history table and confirms the dialog.

- **Action:** The frontend sends `DELETE /api/benchmarks/c9f4b2e1-3f5a-6b7c-8d9e-0f1a2b3c4d5e` with `Authorization: Bearer <jwt>`. The backend verifies the run belongs to the user's workspace and calls `DELETE FROM benchmark_runs WHERE id = :rid AND workspace_id = :wid`. The `ON DELETE CASCADE` constraint on `benchmark_results.run_id` removes all associated metric rows automatically.

- **Expected Output:** HTTP `204 No Content`. The benchmark run and its 17 metric rows are removed from the database. The history table no longer shows the deleted run. Any in-flight benchmark comparison pages (F26) that referenced this run show a stale-data indicator ("One benchmark run has been deleted") rather than failing entirely.

## Acceptance Criteria

- **ACF25-1: Completed benchmark results from the agent are persisted to `benchmark_runs` and `benchmark_results` tables** — When the agent sends a `command_result` message with `status: "success"` and a valid benchmark payload (containing `config`, `metrics` with all required fields, and an optional `latency_distribution` array), the `BenchmarkStorageService.enrich_and_persist()` method performs an atomic database transaction that: (a) updates the `benchmark_runs` row setting `status = "completed"`, `raw_data` (JSONB latency distribution), `completed_at`; (b) inserts one row per metric key into `benchmark_results` with the correct `metric_name`, `metric_value`, and `unit`. If any metric value is `null` or negative for non-error metrics (e.g., `throughput_tok_per_sec: -1`), the entire transaction is rolled back and the benchmark is marked `status = "failed"` with an `error_message` describing the validation failure. If the `latency_distribution` array is missing or null, the run is still persisted — the field is optional. The insert is verified by querying `benchmark_results` with `WHERE run_id = :rid` and counting exactly 17 result rows for a full benchmark suite.

- **ACF25-2: The `GET /api/benchmarks` endpoint returns paginated, filterable, and sortable benchmark history in JSON:API format** — The endpoint supports the following query parameters, all optional:
  - `page[limit]` (integer, 1–100, default 20) and `page[offset]` (integer, default 0) define pagination. The response includes `meta.total` (total matching rows), `meta.count` (rows in this page), and `links.first`, `links.self`, `links.next`, `links.prev` (when applicable).
  - `filter[model]` performs a case-insensitive ILIKE search against both `model_deployments.model_name` and `model_deployments.hf_model_id` columns.
  - `filter[status]` filters by benchmark status (`completed`, `running`, `failed`, `cancelled`).
  - `filter[agent]` filters by agent UUID.
  - `filter[since]` and `filter[until]` accept ISO 8601 timestamps and filter by `started_at`.
  - `sort` accepts comma-separated field names with optional `-` prefix for descending order. Valid fields: `created_at`, `started_at`, `completed_at`, `throughput_tok_per_sec`, `ttft_p99_ms`, `error_rate`. The throughput, TTFT, and error rate sorts require a subquery joining `benchmark_results` to extract the relevant metric value for each run.
  - All queries are scope-filtered to the JWT's `workspace_id`. The response includes `type: "benchmark-runs"` resources with attributes containing model name, HF model ID, status, config summary, throughput, TTFT p99, error rate, timestamps, and duration. The `relationships` block includes `agent` and `model_deployment` resource identifier objects. Response time for the first page with no filters on a dataset of 500 benchmark runs is under 300 ms (p95).

- **ACF25-3: The `GET /api/benchmarks/{id}` endpoint returns a single benchmark run with full metrics and optional related resources** — The endpoint accepts `include=agent,model-deployment` to resolve related resources as JSON:API `included` array. The response `attributes` contain:
  - The full `config` JSONB payload (all fields, not just summary).
  - A `metrics` array: `[{"name": "...", "value": 123.4, "unit": "ms"}, ...]` sorted alphabetically by metric name.
  - The `latency_distribution` array from `raw_data` (null if absent).
  - All timestamps, status, and duration.
  If the run ID does not exist within the authenticated user's workspace, the endpoint returns HTTP `404 Not Found` with a JSON:API error code `"RESOURCE_NOT_FOUND"` — it never reveals the existence of benchmark runs belonging to other workspaces.

- **ACF25-4: The `DELETE /api/benchmarks/{id}` endpoint removes a benchmark run and cascades to its results** — Only runs with `status = "completed"` or `status = "failed"` may be deleted. Runs with `status = "running"` or `status = "pending"` return HTTP `409 Conflict` with error code `"BENCHMARK_IN_PROGRESS"` and detail `"Cannot delete a benchmark run that is currently in progress."`. The deletion is verified by querying `benchmark_results` for the deleted `run_id` after the operation — zero rows are returned. The cascade is database-level (ON DELETE CASCADE on the foreign key from `benchmark_results.run_id` to `benchmark_runs.id`).

- **ACF25-5: The frontend benchmark history page renders a PrimeVue DataTable with search, sorting, and pagination against the JSON:API endpoint** — The page at `frontend/app/pages/dashboard/benchmarks/index.vue` uses a Pinia composable `useBenchmarks()` (defined in `frontend/app/composables/useBenchmarks.ts`) that wraps `useFetch` or a custom fetch wrapper to call `GET /api/benchmarks`. Key behaviour:
  - The DataTable displays columns: Model Name, Throughput (tok/s), TTFT P99 (ms), Status, Started, Duration. Each column is sortable via the `sort` parameter.
  - A PrimeVue `InputText` search field with debounce (300 ms) emits the `filter[model]` query parameter.
  - Pagination uses PrimeVue `Paginator` component bound to `meta.offset` and `meta.total`.
  - Clicking a row navigates to `/dashboard/benchmarks/[id]` via `useRouter().push()`.
  - The composable manages `items`, `total`, `loading`, `filters` reactive state and exposes `fetchList()`, `fetchOne(id)`, `deleteRun(id)`, and `refresh()` methods. `deleteRun()` calls `DELETE /api/benchmarks/{id}` and on success (`204`) removes the item from the local list without re-fetching. On `409` error, it shows a PrimeVue `Message` with severity `"error"` reading "Cannot delete a running benchmark".

- **ACF25-6: The benchmark detail page displays full metrics and latency distribution, and handles missing fields gracefully** — The page at `frontend/app/pages/dashboard/benchmarks/[id].vue` renders:
  - A configuration summary card showing all keys from `config` as labelled key-value pairs (PrimeVue `Fieldset`).
  - A metrics summary table (PrimeVue `DataTable` with columns Metric, Value, Unit) populated from the `metrics` array attribute.
  - A latency distribution histogram (rendered using ECharts bar chart) if `latency_distribution` is non-null and non-empty. The chart X-axis is the bucket upper-bound in ms, Y-axis is request count. If `latency_distribution` is null, a PrimeVue `InlineMessage` reads "Latency distribution data was not collected for this run."
  - All fields display properly when values are zero (e.g., `error_rate: 0`) — the field shows "0 %" not "N/A". When `error_message` is present on a failed run, a PrimeVue `Message` with severity `"error"` displays the error text at the top of the page.
  - A primeVue `Button` labelled "Compare" navigates to `/dashboard/benchmarks/compare?runs=<current_id>` for F26 integration.

## Technical Notes

### File Paths and Structure

```
backend/app/
├── api/
│   └── benchmarks.py              # MODIFY: add GET list, GET detail, DELETE handlers
├── services/
│   ├── benchmark_runner.py         # MODIFY: call storage service on command_result
│   └── benchmark_storage_service.py  # NEW: persist, query, delete logic
├── models/
│   ├── benchmark.py                # (F3) benchmark_runs and benchmark_results ORM models
├── schemas/
│   └── benchmark.py                # MODIFY: add JSON:API schemas for benchmark list/detail
├── middleware/
│   └── auth.py                     # (F5) JWT workspace extraction — reuse existing

frontend/app/
├── pages/
│   └── dashboard/
│       └── benchmarks/
│           ├── index.vue           # MODIFY: history table with search + sort + paginate
│           └── [id].vue            # MODIFY: detail page with metrics table + histogram
├── components/
│   └── benchmarks/
│       ├── BenchmarkTable.vue      # MODIFY or REFERENCE: existing skeleton
│       └── BenchmarkDetail.vue     # NEW: metrics summary card, latency chart
└── composables/
    └── useBenchmarks.ts            # NEW: Pinia-style composable for benchmark CRUD
```

### Benchmark Storage Service: `benchmark_storage_service.py`

```python
class BenchmarkStorageService:
    """Handles persistence and retrieval of benchmark runs and results."""

    def __init__(self, db: AsyncSession, workspace_id: uuid.UUID):
        self.db = db
        self.workspace_id = workspace_id

    async def persist_result(
        self,
        run_id: uuid.UUID,
        status: BenchmarkStatus,
        metrics: dict[str, float],
        config: dict,
        raw_data: dict | None,
        started_at: datetime,
        completed_at: datetime,
        error_message: str | None = None,
    ) -> BenchmarkRun:
        """Atomic transaction to persist a completed benchmark result.
        
        Steps:
        1. Validate all metric values are non-negative where applicable.
        2. Update benchmark_runs row: status, completed_at, raw_data, error_message.
        3. Delete any existing benchmark_results for this run_id (idempotent).
        4. Bulk INSERT benchmark_results rows for each metric.
        5. Return the updated BenchmarkRun ORM instance.
        
        Raises ValueError if critical metrics (throughput, ttft) are null/negative.
        """
        ...

    async def list_runs(
        self,
        filters: BenchmarkFilterParams,
        sort: BenchmarkSortParams,
        pagination: PaginationParams,
    ) -> tuple[list[BenchmarkRun], int]:
        """Paginated, filtered listing of benchmark runs for the workspace.
        
        Builds a query that:
        - Joins benchmark_runs with model_deployments on model_deployment_id.
        - Applies workspace_id filter from self.workspace_id.
        - Applies optional ILIKE filter on model_name/hf_model_id.
        - Applies optional status, agent_id, since, until filters.
        - Applies sort (with subquery into benchmark_results for metric-based sorts).
        - Applies LIMIT/OFFSET pagination.
        - Returns (runs, total_count).
        """
        ...

    async def get_run(self, run_id: uuid.UUID) -> BenchmarkRun | None:
        """Fetch single run by ID, scoped to workspace. Returns None if not found."""
        ...

    async def delete_run(self, run_id: uuid.UUID) -> bool:
        """Delete run and cascaded results. Returns False if run is in progress."""
        ...
```

### BenchmarkFilterParams — Pydantic Model

```python
class BenchmarkFilterParams(BaseModel):
    model: str | None = None           # ILIKE on model name / HF ID
    status: BenchmarkStatus | None = None
    agent: uuid.UUID | None = None
    since: datetime | None = None       # ISO 8601
    until: datetime | None = None       # ISO 8601

class BenchmarkSortParams(BaseModel):
    fields: list[str] = ["-created_at"]  # Prefix "-" = DESC
    # Valid: created_at, started_at, completed_at, 
    #        throughput_tok_per_sec, ttft_p99_ms, error_rate
```

### Integration with F24 (Benchmark Runner)

The F24 `benchmark_runner.py` service creates a `benchmark_runs` row with `status = "pending"` when a user triggers a benchmark from the dashboard. F25 does not change this creation step. When F24 receives the agent's `command_result`, it calls:

```python
# In benchmark_runner.py, on receiving command_result:
from backend.app.services.benchmark_storage_service import BenchmarkStorageService

storage = BenchmarkStorageService(db=db, workspace_id=agent.workspace_id)
run = await storage.persist_result(
    run_id=run_id,
    status=BenchmarkStatus.COMPLETED if result["status"] == "success" else BenchmarkStatus.FAILED,
    metrics=result["metrics"],
    config=result["config"],
    raw_data={"latency_distribution": result.get("latency_distribution")},
    started_at=parse_iso(result["started_at"]),
    completed_at=parse_iso(result["completed_at"]),
    error_message=result.get("error_message"),
)
```

### API Endpoints Summary

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/api/benchmarks` | List runs (paginated, filterable, sortable) | JWT |
| `GET` | `/api/benchmarks/{id}` | Single run detail with metrics + optional includes | JWT |
| `DELETE` | `/api/benchmarks/{id}` | Delete run (only completed/failed) | JWT |

All responses follow JSON:API 1.0 format (`Content-Type: application/vnd.api+json`).

### Frontend Composable: `useBenchmarks.ts`

```typescript
// frontend/app/composables/useBenchmarks.ts

interface BenchmarkFilters {
  model?: string
  status?: string
  agent?: string
  since?: string
  until?: string
}

interface BenchmarksState {
  items: BenchmarkRun[]
  total: number
  loading: boolean
  error: string | null
  filters: BenchmarkFilters
  sort: string
  offset: number
  limit: number
}

export function useBenchmarks() {
  const state = reactive<BenchmarksState>({
    items: [],
    total: 0,
    loading: false,
    error: null,
    filters: {},
    sort: '-created_at',
    offset: 0,
    limit: 20,
  })

  async function fetchList() { /* calls GET /api/benchmarks with params */ }
  async function fetchOne(id: string): Promise<BenchmarkRun> { /* GET /api/benchmarks/{id} */ }
  async function deleteRun(id: string): Promise<boolean> { /* DELETE + handle 409 */ }
  function refresh() { /* reset offset and re-fetch */ }
  function setFilter(key: string, value: string | undefined) { /* update filters and re-fetch */ }
  function setSort(field: string) { /* toggle sort direction and re-fetch */ }

  return { ...toRefs(state), fetchList, fetchOne, deleteRun, refresh, setFilter, setSort }
}
```

### Edge Cases

- **Benchmark fails before any metrics:** If the agent sends a `command_result` with `status: "error"` and no `metrics` dictionary, the storage service sets `benchmark_runs.status = "failed"`, populates `error_message`, and does not attempt to insert any `benchmark_results` rows. This is a valid state — the run appears in the history list with a "failed" badge and the user can inspect the error message.

- **Benchmark cancelled mid-run:** The F24 command handler can receive a cancellation request. F25 does not handle cancellation logic — it only persists the result. If a cancelled run has partial metrics (e.g., 300 of 1000 requests completed), the config and partial metrics are stored with `status = "cancelled"`. The `metrics` array may have fewer entries than a full run (e.g., missing `ttft_p99_ms` if too few requests completed). The frontend handles missing metric fields by displaying "—" instead of a value.

- **Duplicate metric names:** The `benchmark_results` table has a unique constraint on `(run_id, metric_name)`. If the agent sends duplicate metric keys (e.g., two `throughput_tok_per_sec` values), the storage service deletes existing results for the run before inserting (`DELETE WHERE run_id = :rid` then `INSERT`), making the persist operation idempotent for retries. This covers the edge case where the benchmark runner receives a duplicate `command_result` due to WebSocket replay.

- **Model deployment deleted before benchmark completes:** If the `model_deployment_id` foreign key references a deployment that was deleted while the benchmark was running, the `benchmark_runs` row is still valid — the FK has `ON DELETE SET NULL`, so the column becomes `NULL`. The `hf_model_id` and `model_name` are stored directly on the benchmark run response (resolved at query time via a LEFT JOIN), so the model identity is preserved even if the deployment is gone.

- **Concurrent deletes:** If two users in the same workspace attempt to delete the same benchmark run simultaneously, the first DELETE succeeds and the second returns zero affected rows (checked via `result.rowcount`). The storage service returns `False` for the second caller, and the frontend shows a PrimeVue `Message` "This benchmark run was already deleted."

- **Empty list state:** When no benchmark runs exist for a workspace, `GET /api/benchmarks` returns `{"data": [], "meta": {"total": 0, "count": 0, "offset": 0, "limit": 20}}`. The frontend renders PrimeVue `DataTable` with an `emptyMessage` prop: "No benchmark runs yet. Deploy a model and run a benchmark to see results here."

- **Large latency distribution payloads:** A benchmark with 10,000 requests may produce a latency distribution array with hundreds of buckets. The `raw_data` column is JSONB with a default 1 MB limit on the stored document — distributions larger than 250 KB (roughly 5,000 buckets) are truncated to 500 evenly-spaced buckets before storage, with a `truncated: true` flag in the `raw_data` object. The storage service checks `len(json.dumps(raw_data))` and truncates if > 250,000 bytes, logging a `WARNING` with the run ID.

### Integration Points

- **F3 (Database schema):** The `benchmark_runs` and `benchmark_results` tables are defined in the F3 initial migration (`backend/app/models/benchmark.py`). F25 depends on these tables existing with the correct schema: `benchmark_runs` has `raw_data` JSONB column (nullable, stores latency distribution and raw per-request data) and F25 adds an Alembic migration to ensure the `raw_data` column exists if it was not part of the initial migration. The `benchmark_results` table's unique constraint on `(run_id, metric_name)` is enforced at the database level.

- **F10 (Backend metric ingestion):** The downsampling and retention patterns established in F10 (batch writes, tiered storage, workspace-scoped queries) serve as architectural precedent for F25's storage service. However, benchmark data is immutable and low-volume (a few dozen rows per run, not 50 rows/second), so no buffering or downsampling is needed — each persist is a direct transactional write.

- **F24 (Benchmark runner):** F24 creates the initial `benchmark_runs` row with `status = "pending"` and passes the `run_id` to the agent via the deploy command. F25 completes the lifecycle by updating the row and inserting results. The two features share the `backend/app/services/benchmark_runner.py` file — F24 handles the trigger and agent communication, F25 handles the persistence. The storage service is called from within the command-result handler in `benchmark_runner.py`.

- **F26 (Benchmark comparison):** F26 reads from the same `benchmark_runs` and `benchmark_results` tables. The `GET /api/benchmarks/compare` endpoint (defined in F26) reuses the `BenchmarkStorageService.get_run()` method to fetch individual runs for comparison. The latency distribution JSONB stored in `raw_data` is the data source for F26's bar chart renders.

- **F34 (Workspace-scoped data isolation):** All benchmark queries in F25 filter by `workspace_id` derived from the JWT. The `BenchmarkStorageService` requires `workspace_id` at construction time. No endpoint returns benchmark data from a different workspace, even if the requesting user knows the UUID of a run in another workspace.

### Depends on: F3, F10
