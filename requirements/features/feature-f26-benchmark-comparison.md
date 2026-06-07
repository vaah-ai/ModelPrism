# F26: Benchmark comparison

## Metadata
- **ID:** F26
- **Phase:** Enhancement
- **Effort:** Large
- **Dependencies:** F2, F25
- **Acceptance Criteria Count:** 5

## Description

The benchmark comparison feature enables users to select two or more completed benchmark runs and view their metrics side by side in a structured, visual format. While F25 provides the persistence layer, listing, and single-run detail pages, F26 is the analytical layer that turns historical benchmark data into actionable insight: it helps operators answer questions such as *"Which quantisation method yields the best throughput for my model?"*, *"How does vLLM version 0.6.0 compare to 0.5.4 on latency?"*, or *"What is the performance regression after the latest engine config change?"*.

The comparison is surfaced through a dedicated comparison page at `/dashboard/benchmarks/compare` that accepts a comma-separated list of benchmark run UUIDs as a query parameter. It fetches the selected runs from a new JSON:API endpoint (`GET /api/benchmarks/compare`), which returns up to 6 runs at once with all metrics aggregated as a flat key-value map. The frontend renders the comparison as two coordinated visualisations: a side-by-side metric table with colour-coded best-value highlighting and a set of grouped bar charts generated with ECharts. The page supports three comparison modes: manual selection (user picks runs from the history table), baseline comparison (one reference run compared against one or more candidates), and historical trend (same model, same config, multiple timestamps). Users enter the comparison page by clicking "Compare" on a benchmark detail page (F25), from the benchmark history table row action menu, or by navigating directly with explicit run UUIDs in the URL. Once on the page, users can add or remove runs from the comparison set without leaving the page. A shareable URL is generated that encodes the current run selection, so users can bookmark or share a specific comparison.

On the backend, the comparison endpoint is intentionally separate from the single-run detail endpoint to avoid serialising multiple full-run payloads through JSON:API compound documents with `include`. The lightweight comparison payload includes only the attributes needed for comparison: model identity, timestamps, config summary, the 17 standard metrics as a flat key-value map, and the latency distribution histogram. The endpoint accepts up to 6 run UUIDs and enforces workspace-scoped access on each one — if any run belongs to a different workspace, the entire request returns HTTP 403. Runs that have been deleted since the user copied a share link result in a `null` entry in the response array rather than an error, allowing the page to degrade gracefully.

## Concrete Examples (Specification by Example)

### Example 1: Comparing Quantisation Formats for Qwen2.5-72B

The user has completed three benchmark runs for Qwen2.5-72B-Instruct on a single A100-80GB with different precision formats: FP16, GPTQ-Int4, and AWQ.

- **Input:** User navigates to `/dashboard/benchmarks/compare?runs=b8f3a1d0-e29b-41d4-a716-446655440001,c9a4b2e1-3f5a-6b7c-8d9e-0f1a2b3c4d5e,d0b5c3f2-4a6b-7c8d-9e0f-1a2b3c4d5e6f`.

- **Action:** The frontend page calls `GET /api/benchmarks/compare` with the run UUIDs as a comma-separated query parameter. The backend `BenchmarkComparisonService` fetches all three `benchmark_runs` rows in a single query (`SELECT * FROM benchmark_runs WHERE id = ANY(:ids) AND workspace_id = :wid`), joins the `benchmark_results` rows aggregated as a JSONB map per run, and resolves model names from the `model_deployments` table. It returns a JSON:API document with a `data` array of comparison resources.

- **Expected Output:**
  ```json
  {
    "data": [
      {
        "type": "benchmark-comparison",
        "id": "b8f3a1d0-e29b-41d4-a716-446655440001",
        "attributes": {
          "model_name": "Qwen2.5-72B-Instruct",
          "hf_model_id": "Qwen/Qwen2.5-72B-Instruct",
          "deployment_label": "fp16-baseline",
          "agent_friendly_name": "cyan-koala-42",
          "gpu_model": "NVIDIA A100-SXM4-80GB",
          "gpu_count": 1,
          "config": {
            "num_requests": 1000,
            "concurrency": 10,
            "request_rate": "max",
            "input_length": 2048,
            "output_length": 512,
            "dataset": "sharegpt",
            "dtype": "float16",
            "quantization": null,
            "tensor_parallel_size": 1,
            "vllm_version": "0.6.0"
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
          "completed_at": "2026-06-07T14:30:28.700Z",
          "duration_seconds": 28.7
        }
      },
      {
        "type": "benchmark-comparison",
        "id": "c9a4b2e1-3f5a-6b7c-8d9e-0f1a2b3c4d5e",
        "attributes": {
          "model_name": "Qwen2.5-72B-Instruct",
          "hf_model_id": "Qwen/Qwen2.5-72B-Instruct",
          "deployment_label": "gptq-int4",
          "agent_friendly_name": "cyan-koala-42",
          "gpu_model": "NVIDIA A100-SXM4-80GB",
          "gpu_count": 1,
          "config": {
            "num_requests": 1000,
            "concurrency": 10,
            "request_rate": "max",
            "input_length": 2048,
            "output_length": 512,
            "dataset": "sharegpt",
            "dtype": "float16",
            "quantization": "gptq",
            "tensor_parallel_size": 1,
            "vllm_version": "0.6.0"
          },
          "metrics": {
            "ttft_p50_ms": 210.7,
            "ttft_p95_ms": 445.2,
            "ttft_p99_ms": 680.3,
            "tpot_p50_ms": 28.4,
            "tpot_p95_ms": 65.1,
            "tpot_p99_ms": 101.2,
            "throughput_req_per_sec": 54.8,
            "throughput_tok_per_sec": 2740.0,
            "total_tokens": 512000,
            "error_count": 0,
            "error_rate": 0.0,
            "itl_p50_ms": 25.1,
            "itl_p95_ms": 62.4,
            "itl_p99_ms": 98.7,
            "e2e_latency_p50_ms": 3120.5,
            "e2e_latency_p99_ms": 11200.3,
            "duration_seconds": 19.6
          },
          "latency_distribution": [
            {"bucket_ms": 50, "count": 45},
            {"bucket_ms": 100, "count": 210},
            {"bucket_ms": 200, "count": 342},
            {"bucket_ms": 300, "count": 267},
            {"bucket_ms": 400, "count": 95},
            {"bucket_ms": 500, "count": 31},
            {"bucket_ms": 600, "count": 10}
          ],
          "started_at": "2026-06-07T15:00:00.000Z",
          "completed_at": "2026-06-07T15:00:19.600Z",
          "duration_seconds": 19.6
        }
      },
      {
        "type": "benchmark-comparison",
        "id": "d0b5c3f2-4a6b-7c8d-9e0f-1a2b3c4d5e6f",
        "attributes": {
          "model_name": "Qwen2.5-72B-Instruct",
          "hf_model_id": "Qwen/Qwen2.5-72B-Instruct",
          "deployment_label": "awq",
          "agent_friendly_name": "cyan-koala-42",
          "gpu_model": "NVIDIA A100-SXM4-80GB",
          "gpu_count": 1,
          "config": {
            "num_requests": 1000,
            "concurrency": 10,
            "request_rate": "max",
            "input_length": 2048,
            "output_length": 512,
            "dataset": "sharegpt",
            "dtype": "float16",
            "quantization": "awq",
            "tensor_parallel_size": 1,
            "vllm_version": "0.6.0"
          },
          "metrics": {
            "ttft_p50_ms": 198.2,
            "ttft_p95_ms": 420.8,
            "ttft_p99_ms": 645.0,
            "tpot_p50_ms": 26.1,
            "tpot_p95_ms": 60.3,
            "tpot_p99_ms": 95.4,
            "throughput_req_per_sec": 58.1,
            "throughput_tok_per_sec": 2905.0,
            "total_tokens": 512000,
            "error_count": 0,
            "error_rate": 0.0,
            "itl_p50_ms": 23.2,
            "itl_p95_ms": 57.8,
            "itl_p99_ms": 92.1,
            "e2e_latency_p50_ms": 2940.8,
            "e2e_latency_p99_ms": 10800.5,
            "duration_seconds": 18.1
          },
          "latency_distribution": [
            {"bucket_ms": 50, "count": 52},
            {"bucket_ms": 100, "count": 235},
            {"bucket_ms": 200, "count": 365},
            {"bucket_ms": 300, "count": 248},
            {"bucket_ms": 400, "count": 72},
            {"bucket_ms": 500, "count": 22},
            {"bucket_ms": 600, "count": 6}
          ],
          "started_at": "2026-06-07T15:30:00.000Z",
          "completed_at": "2026-06-07T15:30:18.100Z",
          "duration_seconds": 18.1
        }
      }
    ],
    "meta": {
      "count": 3,
      "deleted_count": 0
    }
  }
  ```

- **Expected UI:** A three-column comparison table. The columns are labelled FP16, GPTQ-Int4, and AWQ. Rows show: throughput (tok/s), TTFT P99, TPOT P99, ITL P99, e2e latency P50/P99, error rate, duration. The best value in each row is highlighted with a green background. Bar charts show throughput and latency side-by-side with colour-coded bars. The latency distribution overlay chart shows three curves (one per run).

### Example 2: Baseline Comparison — vLLM Version Upgrade Regression Test

The user upgrades vLLM from 0.5.4 to 0.6.0 and runs the same benchmark with identical config. They want to confirm no regression.

- **Input:** User is on the detail page for the v0.6.0 run (`id = e1f6d4a3-5b7c-8d9e-0f1a-2b3c4d5e6f7a`) and clicks "Compare". The v0.5.4 run ID (`id = f2a7e5b4-6c8d-9e0f-1a2b-3c4d5e6f7a8b`) is pre-selected. The URL becomes `/dashboard/benchmarks/compare?runs=f2a7e5b4-6c8d-9e0f-1a2b-3c4d5e6f7a8b,e1f6d4a3-5b7c-8d9e-0f1a-2b3c4d5e6f7a`.

- **Action:** The frontend renders a two-column comparison with the first run marked as "Baseline" (with a blue "Baseline" badge). The metrics table includes a "Delta" column for each metric, computed as `candidate_value - baseline_value` with green (improved) or red (regressed) colouring and an arrow icon. The delta for throughput shows +12.3% (green, improved), while TTFT P99 shows +8.5% (red, regressed). A summary card at the top reads: "vLLM 0.6.0 vs 0.5.4 — 1 regression flagged (TTFT P99 +8.5%)".

- **Expected UI:** Two columns ("Baseline: vLLM 0.5.4" and "vLLM 0.6.0") with a third "Delta" column. Throughput: 1645.0 → 1850.5 tok/s (+12.5% ↑, green). TTFT P99: 871.2 → 945.1 ms (+8.5% ↑, red). Error rate: 0.001 → 0.002 (+0.1pp, red). A warning icon appears next to any metric where the absolute delta exceeds a configurable threshold (default: 10% regression).

### Example 3: Historical Trend — Same Model, Same Config, Three Timestamps

The user has run `Llama-3.1-8B-Instruct` with identical config on the same agent at weekly intervals for three weeks (June 1, June 8, June 15) to track performance drift.

- **Input:** User navigates to `/dashboard/benchmarks/compare?runs=a1b2c3d4-...,b2c3d4e5-...,c3d4e5f6-...` where all three runs share the same `hf_model_id`, same `config`, same `agent_id`, but different `started_at` dates.

- **Action:** The frontend detects that all runs share the same `hf_model_id` and `deployment_label` is absent or identical. It enters "Historical Trend" mode: the comparison table hides the config summary (identical across runs) and instead shows a "timestamp" row and a week-over-week delta column between each adjacent pair. The latency distribution overlay chart renders three curves with distinct colours and a date legend. A sparkline summary row at the top shows throughput tok/s on a mini line chart (3 data points) with a trend arrow.

- **Expected UI:** Three columns labelled by date ("Jun 1", "Jun 8", "Jun 15"). A sparkline row at the top showing the throughput trend (green up arrow if improving, red down arrow if declining). Delta columns between each adjacent pair: Jun 1→Jun 8: +2.1%, Jun 8→Jun 15: -0.8%. The latency distribution chart shows three overlaid curves with a legend, enabling visual inspection of distribution shape changes over time.

### Example 4: Run Deleted After Share Link Created

A user shares a comparison link with a colleague. One of the runs in the comparison is deleted before the colleague opens the link.

- **Input:** Colleague navigates to `/dashboard/benchmarks/compare?runs=b8f3a1d0-...,c9a4b2e1-...,d0b5c3f2-...` where run `c9a4b2e1-...` has been deleted.

- **Action:** The backend queries all three UUIDs. Run `c9a4b2e1-...` returns zero rows from the workspace-scoped query. The response `data` array contains two valid comparison resources and one `null` entry at index 1. The `meta` block includes `"deleted_count": 1`.

- **Expected Output:**
  ```json
  {
    "data": [
      { /* valid run at index 0 */ },
      null,
      { /* valid run at index 2 */ }
    ],
    "meta": {
      "count": 2,
      "deleted_count": 1
    }
  }
  ```

- **Expected UI:** The third column is rendered as a greyed-out placeholder with a dashed border and text: "This benchmark run has been deleted." The column header shows a crossed-out icon. The latency distribution chart omits the deleted run's curve. A PrimeVue `InlineMessage` at the top of the page reads: "1 of 3 benchmark runs in this comparison has been deleted. Its column has been removed." The user can remove the placeholder column via an "X" button, reducing the comparison to 2 columns.

### Example 5: Maximum Run Limit Exceeded

A user selects 8 benchmark runs from the history table using the checkbox multi-select and clicks "Compare Selected".

- **Input:** User selects 8 runs and clicks "Compare (8)". The frontend constructs the URL with 8 UUIDs: `/dashboard/benchmarks/compare?runs=uuid1,uuid2,...,uuid8`.

- **Action:** Before sending the request, the frontend composable checks the run count. The limit is 6. The frontend shows a PrimeVue `Dialog` reading: "You can compare up to 6 benchmark runs at a time. 8 selected. Please deselect 2 runs to continue." The user deselects 2 runs and the "Compare" button re-enables. On the backend, if more than 6 UUIDs are submitted, the API returns HTTP 422 with a JSON:API error:

  ```json
  {
    "errors": [
      {
        "status": "422",
        "code": "MAX_COMPARISON_RUNS_EXCEEDED",
        "title": "Too many benchmark runs for comparison.",
        "detail": "A maximum of 6 benchmark runs can be compared at once. 8 UUIDs were provided."
      }
    ]
  }
  ```

- **Expected UI:** The dialog explains the limit. No request is sent to the backend. On the backend side, the validation is duplicated: the Pydantic schema enforces `len(runs) <= 6` at the API layer, returning a 422 error before any database query is executed.

## Acceptance Criteria

- **ACF26-1: The `GET /api/benchmarks/compare` endpoint returns a comparison payload with flattened metrics for up to 6 runs, with workspace access control and graceful handling of deleted runs** — The endpoint accepts a query parameter `runs` containing 1 to 6 comma-separated UUIDv4 values. The backend performs the following steps in order:

  1. Parse and validate UUIDs. If the count exceeds 6, return HTTP 422 with error code `"MAX_COMPARISON_RUNS_EXCEEDED"` as a JSON:API error document. If any UUID is malformed, return HTTP 400 with error code `"INVALID_UUID"`.
  2. Query `SELECT * FROM benchmark_runs WHERE id = ANY(:ids) AND workspace_id = :wid`. Runs that do not exist or belong to a different workspace are inherently excluded by the WHERE clause — the endpoint never reveals cross-workspace run existence.
  3. For each found run, query `benchmark_results` aggregated into a JSONB map using `jsonb_object_agg(metric_name, metric_value)`. If a run has zero `benchmark_results` rows (e.g., a failed run with no metrics), its `metrics` attribute is `null`.
  4. Assemble the response `data` array preserving the original UUID order. Runs that were not found (deleted or wrong workspace) are represented as `null` in the array at their original index position. The `meta` block contains `"count"` (number of non-null entries) and `"deleted_count"` (number of null entries).
  5. Each non-null `data` entry is of type `"benchmark-comparison"` with `attributes` containing: `model_name`, `hf_model_id`, `deployment_label` (nullable VARCHAR(64) from the `benchmark_runs` table), `agent_friendly_name`, `gpu_model`, `gpu_count`, `config` (the full JSONB config payload), `metrics` (the flat metric map as a JSON object), `latency_distribution` (array of `{bucket_ms, count}` objects, null if absent), `started_at`, `completed_at`, and `duration_seconds`.
  6. The response has no `included` or `relationships` blocks — the comparison payload is entirely self-contained. Response time for 6 runs with full metric resolution is under 200 ms (p95) on a dataset of 500 total benchmark runs.

- **ACF26-2: The frontend comparison page renders a side-by-side metric table with colour-coded best-value highlighting and configurable metric selection** — The page at `frontend/app/pages/dashboard/benchmarks/compare.vue` uses the `useBenchmarkComparison()` composable to fetch data from `GET /api/benchmarks/compare` on mount. The page renders:

  1. **Run identification header:** A row of PrimeVue `Card` components, one per run, showing: deployment label (or auto-generated "Run N" if not set), model name, GPU hardware summary, benchmark date and duration, and a colour swatch that corresponds to the bar chart colour. The first run is visually distinguished with a "Baseline" badge (PrimeVue `Tag` with severity `"info"`). A config toggle button switches between "Absolute" and "Delta vs Baseline" view modes.

  2. **Configuration summary table** (collapsible via PrimeVue `Accordion`): A key-value table showing all `config` keys across all runs. Cells that differ from the majority value are highlighted with a yellow background, drawing attention to config differences between runs.

  3. **Metrics comparison table** (PrimeVue `DataTable`): One row per metric, one column per run, plus an optional "Delta" column in baseline mode. The table includes:
     - A "Show/Hide metric" toggle per row so users can focus on a subset of metrics (stored in `localStorage` by user preference).
     - Colour coding: green background for the best value in each row (highest throughput = green; lowest latency = green). Red background for the worst value where direction is meaningful.
     - A `severity` column in baseline mode: green checkmark (improvement < 5% change), amber triangle (change 5–15%), red exclamation (regression > 15%). Thresholds defined as constants in the composable (`DELTA_WARN_PCT = 5`, `DELTA_CRITICAL_PCT = 15`).
     - A "Delta %" column showing `((candidate - baseline) / baseline) * 100` with direction arrows (↑ improved, ↓ regressed).
     - Rows are sortable by any column.

  4. **Grouped bar charts** (ECharts, rendered below the table):
     - **Throughput chart:** One bar per run for `throughput_tok_per_sec` and `throughput_req_per_sec`, grouped by metric.
     - **Latency chart:** Grouped bars for `ttft_p99_ms`, `tpot_p99_ms`, `itl_p99_ms`, and `e2e_latency_p99_ms`.
     - **Error rate chart:** A single row of bars for `error_rate`, with a horizontal red dashed line at 0.005 (0.5%) as a warning threshold.
     - All charts use consistent colour assignment per run: run at index 0 = `#4FC3F7` (light blue), index 1 = `#81C784` (green), index 2 = `#FFB74D` (amber), index 3 = `#E57373` (red), index 4 = `#BA68C8` (purple), index 5 = `#4DB6AC` (teal). Colours cycle if more than 6 runs are displayed (though the API enforces a 6-run limit).

  5. **Latency distribution overlay chart** (ECharts): A line chart overlaying the `latency_distribution` curves from all runs. X-axis = bucket_ms (linear scale), Y-axis = count. Each curve uses the run's assigned colour. A legend identifies each curve by its deployment label or model name. If a run has no `latency_distribution`, its curve is omitted and the run is greyed out in the legend.

  6. **Share button:** A PrimeVue `Button` labelled "Share" that copies the current URL (`/dashboard/benchmarks/compare?runs=uuid1,uuid2,...`) to the clipboard. A toast message confirms: "Comparison URL copied to clipboard."

  The page handles the empty state (single run) gracefully: it renders as a single-column metrics summary with no deltas or charts, and displays an inline message: "Add at least one more benchmark run to see comparisons." A "Select runs" button opens a dialog with a filterable list of recent completed benchmark runs (fetched from `GET /api/benchmarks`) for adding rows.

- **ACF26-3: Users can add or remove runs dynamically from the comparison view without navigating away** — The comparison page supports three interaction patterns for modifying the run set:

  1. **Remove a run:** Each run column header card includes an "X" close button (PrimeVue `Button` with `icon="pi pi-times"` and `text` variant). Clicking it removes that run from the comparison. The URL is updated via `useRouter().replace()` with the new `runs` parameter. The page re-fetches the comparison data from the API (since removal may affect delta calculations). If all runs are removed, the page displays the empty state: "No benchmark runs selected for comparison." with two buttons: "Select from history" and "Go to benchmarks".

  2. **Add a run:** A "+ Add" button at the end of the column header row opens a PrimeVue `Dialog` titled "Add benchmark run to comparison". The dialog embeds a `BenchmarkComparisonSelector` component that:
     - Fetches `GET /api/benchmarks?page[limit]=50&filter[status]=completed` (completed runs only).
     - Renders a searchable list with a PrimeVue `InputText` filter and a scrollable list of run items.
     - Each item shows model name, date, throughput, and a checkbox.
     - Already-selected runs are shown as disabled/greyed out.
     - Clicking "Add" appends the selected UUID(s) to the URL's `runs` parameter and re-fetches.
     - The dialog enforces the 6-run limit: if the current count + selected count > 6, the "Add" button is disabled and a message reads: "Maximum 6 runs. You currently have N selected."

  3. **Reorder runs:** The column header cards support drag-to-reorder using PrimeVue `OrderList` behaviour. Reordering updates the `runs` parameter order in the URL. The first column is always treated as the baseline in delta mode — changing the baseline changes all delta values and re-highlights the best/worst values accordingly. Reordering does not trigger a re-fetch since the data is already loaded — only the render order and delta computations change client-side.

  After any modification, the URL is kept in sync with the current run set so the page is always shareable/bookmarkable. The composable exposes `setRuns(uuids: string[])` and `addRun(uuid: string)` and `removeRun(index: number)` methods that update the URL and trigger a re-fetch only when the set of run UUIDs changes (not on reorder).

- **ACF26-4: The backend `BenchmarkComparisonService` supports the `deployment_label` field for semantic grouping and handles cross-model comparison warnings** — The `BenchmarkComparisonService` in `backend/app/services/benchmark_comparison_service.py` implements the following behaviours:

  1. **Deployment label propagation:** When a benchmark run was created with a `deployment_label` (a user-provided VARCHAR(64) tag like `"fp16-baseline"`, `"gptq-int4"`, or `"awq"`), the label is included in the comparison response. The label is stored in the `benchmark_runs.config` JSONB payload under the key `deployment_label`. If absent, the frontend auto-generates `"Run 1"`, `"Run 2"`, etc. based on the position in the response array.

  2. **Cross-model comparison guard:** The service checks whether all runs share the same `hf_model_id`. If the runs contain two or more distinct model IDs (e.g., comparing `Qwen/Qwen2.5-72B-Instruct` with `mistralai/Mistral-7B-Instruct-v0.3`), the response includes a `meta.warning` field:

      ```json
      {
        "meta": {
          "count": 2,
          "deleted_count": 0,
          "warning": {
            "code": "CROSS_MODEL_COMPARISON",
            "message": "Comparing benchmarks across different models. Results may not be directly comparable due to different model architectures, parameter counts, and hardware configurations."
          }
        }
      }
      ```

      The frontend renders a PrimeVue `Message` with severity `"warn"` at the top of the page when this warning is present. The comparison is still rendered — the warning is informational, not blocking.

  3. **Cross-hardware comparison guard:** If the runs were executed on agents with different GPU models (e.g., comparing an A100 run with an H100 run), the response includes a `meta.warning`:

      ```json
      {
        "meta": {
          "count": 2,
          "deleted_count": 0,
          "warning": {
            "code": "CROSS_HARDWARE_COMPARISON",
            "message": "Comparing benchmarks across different GPU hardware (NVIDIA A100-SXM4-80GB vs NVIDIA H100-SXM5-80GB). Differences in architecture (Ampere vs Hopper) will affect all metrics independently of software configuration."
          }
        }
      }
      ```

      Both warnings can appear simultaneously. The frontend stacks them as separate `Message` components.

  4. **Single-run edge case:** If the `runs` parameter contains a single UUID, the service returns a `data` array with one non-null entry and no comparison-specific processing. The frontend renders the single run's metrics in a read-only summary view with the message "Add a second run to start comparing." The response includes no `meta.warning` fields.

  5. **No runs found:** If none of the provided UUIDs exist in the workspace, the endpoint returns an empty `data` array with `meta.count = 0`, `meta.deleted_count = N`. HTTP status is `200 OK` (not 404), because the request is valid — it is the caller's responsibility to check `meta.count`.

- **ACF26-5: The comparison page handles error states, loading states, and latency distribution downsampling correctly** — The following behaviours are verified:

  1. **Loading state:** While the API request is in-flight, the page renders a PrimeVue `Skeleton` placeholder for each column (three skeleton cards in the header row, skeleton rows in the metrics table) and the charts display a spinning loader overlay. The "Add run" and "Share" buttons are disabled during loading. The `loading` state is exposed from the composable as a reactive `ref<boolean>`.
  
  2. **API error state:** If the fetch fails (network error, 5xx), the page shows a PrimeVue `InlineMessage` with severity `"error"` reading "Failed to load comparison data. Please try again." A "Retry" button calls `fetchComparison()`. The page retains the previous successful data if available — it does not clear the charts on a failed refresh. The auto-refresh timer (60 s interval) is paused on error and resumes on the next successful fetch.
  
  3. **Latency distribution downsampling:** When any run's `latency_distribution` array exceeds 50 buckets, the overlay chart downsamples client-side by selecting evenly-spaced buckets: `downsampled = distribution.filter((_, i) => i % Math.ceil(distribution.length / 50) === 0)`. A small note below the chart reads "Latency distributions downsampled to 50 buckets." for any run that was downsampled. If all runs have ≤50 buckets, no note is shown.
  
  4. **Null or missing `latency_distribution`:** If all runs have `latency_distribution: null`, the overlay chart area shows a PrimeVue `InlineMessage` with severity `"info"`: "Latency distribution data was not collected for these runs." The bar charts and metrics table remain fully functional.
  
  5. **Extreme metric outliers:** If any metric value differs from the median by more than 10× (e.g., one run has `throughput_tok_per_sec: 150000` while all others are ~2000), the bar chart Y-axis automatically switches from linear to log scale (ECharts `yAxis.type: 'log'`). A small label "Log scale" appears on the affected Y-axis. The user can toggle back to linear scale via a dropdown in the chart toolbar.
  
  6. **Metric values of exactly zero:** Zero values (e.g., `error_rate: 0.0`) display as "0" with the unit suffix. They are not treated as "no data" — a zero error rate is the best possible value and is highlighted green. The highlight logic in `METRIC_DEFINITIONS.goodWhen` governs the direction; `goodWhen: 'low'` with value 0 correctly receives a green background.

## Technical Notes

### File Paths and Structure

```
backend/app/
├── api/
│   ├── benchmarks.py                   # MODIFY: add GET /api/benchmarks/compare handler
├── services/
│   └── benchmark_comparison_service.py  # NEW: comparison data aggregation logic
├── schemas/
│   └── benchmark.py                     # MODIFY: add BenchmarkComparisonResource schema

frontend/app/
├── pages/dashboard/benchmarks/
│   ├── compare.vue                      # NEW: comparison page with table + charts
├── components/benchmarks/
│   ├── BenchmarkComparison.vue          # NEW (or MODIFY existing stub): comparison table component
│   ├── BenchmarkComparisonChart.vue     # NEW: ECharts bar chart for grouped metrics
│   ├── BenchmarkLatencyDistribution.vue # NEW: ECharts overlay line chart for latency distribution
│   ├── BenchmarkComparisonSelector.vue  # NEW: dialog for adding/removing runs in comparison
│   ├── BenchmarkComparisonCard.vue      # NEW: run column header card with colour/badge/actions
│   └── BenchmarkTable.vue              # MODIFY: add checkbox multi-select + "Compare Selected" button
└── composables/
    └── useBenchmarkComparison.ts        # NEW: composable for comparison data + state management
```

### Benchmark Comparison Service

```python
# backend/app/services/benchmark_comparison_service.py

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

MAX_COMPARISON_RUNS = 6


class BenchmarkComparisonWarning(BaseModel):
    code: str
    message: str


class BenchmarkComparisonItem(BaseModel):
    id: uuid.UUID
    model_name: str | None
    hf_model_id: str | None
    deployment_label: str | None
    agent_friendly_name: str | None
    gpu_model: str | None
    gpu_count: int | None
    config: dict
    metrics: dict[str, float] | None
    latency_distribution: list[dict] | None
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: float | None


class BenchmarkComparisonResult(BaseModel):
    items: list[BenchmarkComparisonItem | None]
    count: int
    deleted_count: int
    warnings: list[BenchmarkComparisonWarning]


class BenchmarkComparisonService:
    """Aggregates multiple benchmark runs into a comparison payload."""

    def __init__(self, db: AsyncSession, workspace_id: uuid.UUID):
        self.db = db
        self.workspace_id = workspace_id

    async def compare(
        self,
        run_ids: list[uuid.UUID],
    ) -> BenchmarkComparisonResult:
        """Fetch up to MAX_COMPARISON_RUNS runs and assemble comparison data.

        Steps:
        1. Validate run_ids length (must be 1..MAX_COMPARISON_RUNS).
        2. Query benchmark_runs WHERE id = ANY(:run_ids) AND workspace_id = :wid.
        3. For each found run, load benchmark_results aggregated as JSONB map.
        4. Resolve agent friendly_name and GPU info from agents table.
        5. Build result array preserving input order (null for missing runs).
        6. Compute warnings: CROSS_MODEL_COMPARISON, CROSS_HARDWARE_COMPARISON.
        7. Return BenchmarkComparisonResult with items, counts, warnings.
        """
        ...

    async def _fetch_aggregated_metrics(
        self, run_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, dict[str, float]]:
        """SELECT run_id, jsonb_object_agg(metric_name, metric_value)
        FROM benchmark_results WHERE run_id = ANY(:ids) GROUP BY run_id."""
        ...

    def _compute_warnings(
        self, items: list[BenchmarkComparisonItem]
    ) -> list[BenchmarkComparisonWarning]:
        """Check for cross-model and cross-hardware comparisons."""
        ...

    def _detect_cross_model(
        self, items: list[BenchmarkComparisonItem]
    ) -> Optional[BenchmarkComparisonWarning]:
        """Return warning if items contain >1 distinct hf_model_id."""
        ...

    def _detect_cross_hardware(
        self, items: list[BenchmarkComparisonItem]
    ) -> Optional[BenchmarkComparisonWarning]:
        """Return warning if items contain >1 distinct gpu_model."""
        ...
```

### Frontend Composable: `useBenchmarkComparison.ts`

```typescript
// frontend/app/composables/useBenchmarkComparison.ts

import { reactive, computed, ref, toRefs } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { BenchmarkComparisonItem, ComparisonMeta } from '~/types/benchmark'

const MAX_RUNS = 6
const DELTA_WARN_PCT = 5
const DELTA_CRITICAL_PCT = 15

// Assigned colours for runs by index (0–5)
const RUN_COLORS = [
  '#4FC3F7', // light blue
  '#81C784', // green
  '#FFB74D', // amber
  '#E57373', // red
  '#BA68C8', // purple
  '#4DB6AC', // teal
]

export function useBenchmarkComparison() {
  const route = useRoute()
  const router = useRouter()

  const state = reactive({
    items: [] as (BenchmarkComparisonItem | null)[],
    meta: { count: 0, deleted_count: 0 } as ComparisonMeta,
    loading: false,
    error: null as string | null,
    baselineIndex: 0,
    viewMode: 'absolute' as 'absolute' | 'delta',
    hiddenMetrics: new Set<string>(),
    visibleMetrics: new Set<string>([
      'throughput_tok_per_sec',
      'ttft_p99_ms',
      'tpot_p99_ms',
      'itl_p99_ms',
      'e2e_latency_p99_ms',
      'error_rate',
    ]),
  })

  const runIds = computed(() => {
    return (route.query.runs as string || '').split(',').filter(Boolean)
  })

  const validCount = computed(() => runIds.value.length)
  const canAddMore = computed(() => validCount.value < MAX_RUNS)

  const warnings = computed(() => state.meta.warning ? [state.meta.warning] : [])

  const metricsTable = computed(() => {
    /* Flatten metrics from all runs into row-oriented format.
       Returns array of { metricName, unit, values: (float|null)[], bestIndex, worstIndex }.
       If viewMode === 'delta', computes delta vs baselineIndex. */
    ...
  })

  function colorForRun(index: number): string {
    return RUN_COLORS[index % RUN_COLORS.length]
  }

  async function fetchComparison() {
    state.loading = true
    state.error = null
    try {
      const response = await $fetch('/api/benchmarks/compare', {
        params: { runs: runIds.value.join(',') },
        headers: { Accept: 'application/vnd.api+json' },
      })
      state.items = response.data
      state.meta = response.meta
    } catch (err: any) {
      state.error = err.message || 'Failed to load comparison data'
      state.items = []
    } finally {
      state.loading = false
    }
  }

  function addRun(uuid: string) {
    if (validCount.value >= MAX_RUNS) return
    const newIds = [...runIds.value, uuid]
    router.replace({ query: { ...route.query, runs: newIds.join(',') } })
  }

  function removeRun(index: number) {
    const newIds = runIds.value.filter((_, i) => i !== index)
    if (newIds.length === 0) {
      router.replace({ query: { ...route.query, runs: undefined } })
      return
    }
    router.replace({ query: { ...route.query, runs: newIds.join(',') } })
  }

  function setBaseline(index: number) {
    state.baselineIndex = index
  }

  function setViewMode(mode: 'absolute' | 'delta') {
    state.viewMode = mode
  }

  function toggleMetric(metricName: string) {
    if (state.hiddenMetrics.has(metricName)) {
      state.hiddenMetrics.delete(metricName)
    } else {
      state.hiddenMetrics.add(metricName)
    }
  }

  // Watch runIds changes and re-fetch
  watch(runIds, () => {
    if (runIds.value.length > 0) {
      fetchComparison()
    }
  }, { immediate: true })

  return {
    ...toRefs(state),
    runIds,
    validCount,
    canAddMore,
    warnings,
    metricsTable,
    colorForRun,
    fetchComparison,
    addRun,
    removeRun,
    setBaseline,
    setViewMode,
    toggleMetric,
  }
}
```

### API Endpoints Summary

| Method | Path | Description | Auth | Max Runs |
|--------|------|-------------|------|----------|
| `GET` | `/api/benchmarks/compare` | Return comparison payload for up to 6 runs | JWT | 6 |

The endpoint accepts a single query parameter `runs` containing comma-separated UUIDv4 values. It returns a JSON:API document with `Content-Type: application/vnd.api+json`. The response is not paginated — the entire comparison is returned in a single response.

### Frontend Route and Pages

- **`frontend/app/pages/dashboard/benchmarks/compare.vue`** — The comparison page. Uses the `useBenchmarkComparison()` composable. Renders:
  - A comparison header with run count, share button, and "Add runs" button.
  - A row of `BenchmarkComparisonCard` components (one per run column), each with colour swatch, model name, deployment label, date, GPU info, and close button.
  - Baseline mode toggle and view mode (absolute/delta) switch.
  - A collapsible config summary accordion (`BenchmarkComparisonConfig.vue`).
  - A metrics comparison `DataTable` (`BenchmarkComparison.vue`) with best-value highlighting and delta columns.
  - Grouped bar charts (`BenchmarkComparisonChart.vue`) for throughput, latency, and error rate.
  - A latency distribution overlay chart (`BenchmarkLatencyDistribution.vue`).
  - An "Add runs" dialog (`BenchmarkComparisonSelector.vue`).
  - The page is SSR-safe: the initial load uses `useAsyncData` with `server: false` to fetch on the client only (since the data depends on client-side UUIDs from the URL).

- **`frontend/app/components/benchmarks/BenchmarkComparisonSelector.vue`** — Dialog component for selecting additional benchmark runs. Contains:
  - A search input that filters the runs list client-side.
  - A PrimeVue `VirtualScroller` for efficient rendering of up to 50 runs.
  - Checkboxes per run item, with already-selected runs disabled.
  - An "Add Selected" button that appends UUIDs to the comparison URL.

### Integration with F25 Benchmark Detail Page

The benchmark detail page (`frontend/app/pages/dashboard/benchmarks/[id].vue`) defined in F25 includes a "Compare" button that navigates to `/dashboard/benchmarks/compare?runs=<current_id>`. This is the primary entry point to F26. The detail page also has a "Compare with..." dropdown that presents the 5 most recent completed runs for the same model, fetched client-side from `GET /api/benchmarks?filter[model]=<same_model>&filter[status]=completed&page[limit]=5&sort=-completed_at`. Selecting a run from the dropdown navigates to the comparison page with both IDs.

### Frontend Composable for Benchmark Table Multi-Select

The benchmark history table component (`BenchmarkTable.vue` or `frontend/app/pages/dashboard/benchmarks/index.vue`) is extended with:

1. A PrimeVue `DataTable` `selection` prop for checkboxes.
2. A `selectedRuns: Ref<BenchmarkRun[]>` reactive array.
3. A "Compare Selected (N)" button above the table, disabled when fewer than 2 runs are selected.
4. Clicking the button calls `router.push({ path: '/dashboard/benchmarks/compare', query: { runs: selectedRuns.map(r => r.id).join(',') } })`.

### Edge Cases

- **Single run in comparison:** The page renders as a single-column metrics summary with no delta, no charts, and an inline message: "Add at least one more run to see comparisons." The "Add runs" button is the primary call to action. This state is valid — the user may be starting from a share link that they know needs another run added.

- **All runs deleted:** If every UUID resolves to `null`, the `data` array is all nulls, `meta.count = 0`, `meta.deleted_count = N`. The page renders a PrimeVue `InlineMessage` with severity `"error"`: "All benchmark runs in this comparison have been deleted. The page is now empty." The page body shows the empty-state view with "Select from history" and "Go to benchmarks" buttons.

- **Inconsistent benchmark configurations:** When comparing runs with different configs (e.g., different `num_requests`, `concurrency`, or `input_length`), the config summary accordion highlights differing cells with a yellow background. A PrimeVue `InlineMessage` with severity `"warn"` is shown at the top: "These benchmarks were run with different configurations. Direct comparisons may be misleading." The comparison is still fully functional.

- **Very large latency distribution arrays:** A benchmark may produce a latency distribution with hundreds of buckets. When overlaying 6 runs on the same chart, the chart must downsample to prevent visual clutter. The chart component uses a Lodash `_.uniqBy()` deduplication approach: it renders at most 50 evenly-spaced buckets per curve. If a run's distribution has more than 50 buckets, it is downsampled client-side before rendering. A small note below the chart reads: "Latency distributions have been downsampled to 50 buckets for visual clarity."

- **Run count changes during page lifetime:** The composable watches `route.query.runs` and re-fetches on change. Users can use browser back/forward navigation to cycle through previous comparison states. The page handles this transparently — there is no "stale comparison" state because the data always reflects the current URL.

- **Non-numeric metric values:** Some metrics (e.g., `error_message`) are strings. The metrics table filters out non-numeric entries automatically by checking `typeof value === 'number'` on the frontend. The backend returns all metrics from `benchmark_results` — the frontend selects only the 17 standard numeric metrics for display.

- **Zero error rate display:** `error_rate: 0.0` displays as "0 %" in the table, not "N/A". The frontend uses explicit zero formatting rather than falsy checks.

- **Metric unit consistency:** The frontend composable maps metric names to display labels and units using a static dictionary:

  ```typescript
  const METRIC_DEFINITIONS: Record<string, { label: string; unit: string; goodWhen: 'low' | 'high' }> = {
    ttft_p50_ms:       { label: 'TTFT P50',       unit: 'ms',    goodWhen: 'low' },
    ttft_p95_ms:       { label: 'TTFT P95',       unit: 'ms',    goodWhen: 'low' },
    ttft_p99_ms:       { label: 'TTFT P99',       unit: 'ms',    goodWhen: 'low' },
    tpot_p50_ms:       { label: 'TPOT P50',       unit: 'ms',    goodWhen: 'low' },
    tpot_p99_ms:       { label: 'TPOT P99',       unit: 'ms',    goodWhen: 'low' },
    throughput_req_per_sec: { label: 'Throughput', unit: 'req/s', goodWhen: 'high' },
    throughput_tok_per_sec: { label: 'Throughput', unit: 'tok/s', goodWhen: 'high' },
    error_rate:        { label: 'Error Rate',      unit: '%',     goodWhen: 'low' },
    duration_seconds:  { label: 'Duration',        unit: 's',     goodWhen: 'low' },
    // ... etc
  }
  ```

  The `goodWhen` field determines which direction is highlighted green: for `goodWhen: 'high'` metrics (throughput), the highest value is green; for `goodWhen: 'low'` metrics (latency, error rate), the lowest value is green.

### Integration Points

- **F2 (Frontend scaffolding):** The comparison page lives at `frontend/app/pages/dashboard/benchmarks/compare.vue`, which was scaffolded as a stub in F2. The dashboard layout, `useApi` composable, auth middleware, and sidebar navigation with "Benchmarks" highlighted are all provided by F2. The page is registered as a child of the `dashboard` layout with auth middleware.

- **F3 (Database schema):** The `benchmark_runs` and `benchmark_results` tables are defined in F3. The `benchmark_runs.raw_data` JSONB column stores the `latency_distribution` array that F26 uses for the overlay chart. The `benchmark_runs.config` JSONB column stores the `deployment_label` field (nullable) that F26 uses for semantic column naming. If `deployment_label` is not yet present in existing runs, the frontend falls back to auto-generated "Run N" labels.

- **F5 (Email/password auth):** The comparison page and API endpoint require a valid JWT. The F5 auth middleware in `backend/app/middleware/auth.py` extracts the `workspace_id` claim and passes it to the `BenchmarkComparisonService` constructor. All database queries are scoped by `workspace_id`.

- **F25 (Benchmark storage + history):** F26 depends on F25 for the underlying benchmark data. The `BenchmarkComparisonService` reads from the `benchmark_runs` and `benchmark_results` tables that F25 populates. The "Compare" button on the benchmark detail page (F25, ACF25-6) navigates to the F26 comparison page. The benchmark history table (F25, `frontend/app/pages/dashboard/benchmarks/index.vue`) is extended with multi-select checkboxes and a "Compare Selected" button, both of which are F26 additions back-ported into the F25 page component. The `BenchmarkStorageService` from F25 is used by the comparison service for fetching individual runs — or the comparison service queries the tables directly for efficiency (single batch query vs. N individual calls to `get_run()`).

- **F34 (Workspace-scoped data isolation):** All comparison queries filter by `workspace_id` derived from the JWT. The `BenchmarkComparisonService` requires `workspace_id` at construction time. Deleted runs from other workspaces are indistinguishable from non-existent runs — the endpoint never leaks cross-workspace data.

### Depends on: F2, F25
