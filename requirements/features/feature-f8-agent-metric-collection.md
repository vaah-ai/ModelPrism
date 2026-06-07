# F8: Agent metric collection

## Metadata
- **ID:** F8
- **Phase:** Foundation
- **Effort:** Medium
- **Dependencies:** F13
- **Acceptance Criteria Count:** 6

## Description

The modelprism-agent running on each GPU server collects three categories of telemetry and bundles them for transport to the backend: GPU metrics from `nvidia-smi`, system-level metrics via `psutil`, and per-instance vLLM inference metrics scraped from the local vLLM Prometheus endpoint (`/metrics`). This feature covers the on-agent data-plane logic only — the collection, parsing, aggregation, and emission of structured metric snapshots. The actual WebSocket transport that pushes these snapshots to the backend is handled by **F9 (Agent metric push over WebSocket)**.

GPU metrics include per-device utilization percent, VRAM usage, temperature, and power draw, parsed from `nvidia-smi --query-gpu=... --format=csv,noheader,nounits`. System metrics capture CPU utilization, load averages, RAM usage, and disk utilization via `psutil`. vLLM metrics are scraped from the Prometheus endpoint exposed by each running vLLM instance (e.g., `http://localhost:8001/metrics`) and include running/waiting request counts, TTFT percentiles (p50, p99), tokens-per-second throughput, KV cache utilization, prefix cache hit rate, and error/truncation rates.

The collector runs on a configurable poll interval (default: 2 seconds), aligns all three sources to the same timestamp, and emits a structured `MetricSnapshot` payload. Snapshots are handed to the WebSocket connection layer (F9) which batches and transmits them. The collector also integrates with the agent lifecycle (F13): when the agent is paused, metric collection stops (but vLLM continues running); when stopped, collection terminates entirely.

## Concrete Examples (Specification by Example)

### Example 1: Full Metrics Snapshot on a Dual-GPU A100 Server

An agent on a server with 2× NVIDIA A100-80GB GPUs and one running vLLM instance (`Qwen2.5-72B-Instruct` on port 8001) collects a full metrics cycle.

- **Input:** Poll timer fires at `2026-06-07T10:15:30.000Z`.
- **Action:** The collector runs all three probes in sequence:
  1. `nvidia-smi --query-gpu=index,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw --format=csv,noheader,nounits` → parses output for both GPUs.
  2. `psutil.cpu_percent()`, `psutil.getloadavg()`, `psutil.virtual_memory()`, `psutil.disk_usage('/')` → records system stats.
  3. `GET http://localhost:8001/metrics` → parses vLLM Prometheus gauge/histogram values for running requests, waiting requests, `vllm:prompt_tokens_total`, `vllm:generation_tokens_total`, `vllm:time_to_first_token_seconds` histogram (p50, p99), `vllm:gpu_cache_usage_perc`, `vllm:prefix_cache_hit_rate`, `vllm:request_success` / `vllm:request_failure` counters.
- **Expected output:** A `MetricSnapshot` dict emitted to the collector callback:

```python
{
    "type": "metrics",
    "ts": "2026-06-07T10:15:30.000Z",
    "gpu": [
        {
            "index": 0,
            "util_pct": 87,
            "mem_used_mb": 42100,
            "mem_total_mb": 81200,
            "temp_c": 72,
            "power_w": 285.5
        },
        {
            "index": 1,
            "util_pct": 12,
            "mem_used_mb": 3200,
            "mem_total_mb": 81200,
            "temp_c": 48,
            "power_w": 85.0
        }
    ],
    "cpu_pct": 14.2,
    "load_1": 8.2,
    "load_5": 7.1,
    "load_15": 6.5,
    "ram_used_gb": 128.4,
    "ram_total_gb": 512.0,
    "disk_used_gb": 548.3,
    "disk_total_gb": 2048.0,
    "disk_pct": 26.8
}
```

And a separate `VllmMetricsSnapshot` per instance:

```python
{
    "type": "vllm_metrics",
    "instance_id": "inst_a100_001",
    "ts": "2026-06-07T10:15:30.000Z",
    "model_name": "Qwen2.5-72B-Instruct",
    "running": 3,
    "waiting": 2,
    "total_requests": 15234,
    "prompt_tokens_total": 450000000,
    "gen_tokens_total": 120000000,
    "ttft_p50_ms": 280,
    "ttft_p99_ms": 850,
    "gpu_cache_pct": 62.5,
    "tps": 1850,
    "prefix_cache_hit_pct": 34,
    "error_pct": 0.02,
    "trunc_pct": 1.2,
    "server_start_ts": "2026-06-06T02:00:00.000Z"
}
```

### Example 2: nvidia-smi Fails Mid-Collection

The SMI process exits with a non-zero code because a GPU is in recovery mode.

- **Input:** Poll timer fires. `nvidia-smi` returns exit code 8 with `"No devices were found"` on stderr.
- **Action:** The GPU collector catches the `CalledProcessError`, logs a `WARNING` at `modelprism_agent.metrics.gpu` with message `"nvidia-smi failed (exit 8): No devices were found"`, and sets all GPU fields to `None` or omits the `gpu` list. The system and vLLM probes continue unaffected.
- **Expected output:** The snapshot contains the system and vLLM data but reports GPU metrics as unavailable:

```python
{
    "type": "metrics",
    "ts": "2026-06-07T10:15:32.000Z",
    "gpu": None,
    "cpu_pct": 15.1,
    "ram_used_gb": 130.0,
    "disk_pct": 27.0,
    ...
}
```

On the next poll cycle (2 seconds later), the collector retries. If `nvidia-smi` succeeds, GPU metrics resume without any manual intervention or restart.

### Example 3: vLLM Instance Goes Down Mid-Collection

A vLLM instance (`inst_a100_001`) crashes between poll cycles. The Prometheus scrape returns a connection refused error.

- **Input:** `GET http://localhost:8001/metrics` raises `requests.ConnectionError`.
- **Action:** The vLLM metrics collector catches the exception, logs an `ERROR` at `modelprism_agent.metrics.vllm` with message `"vLLM instance inst_a100_001 (port 8001, model Qwen2.5-72B-Instruct) unreachable: Connection refused"`, and omits that instance's vLLM metrics from the snapshot. The GPU and system probes continue normally. The agent's command handler (F11) is notified of the crash via a callback so it can update the deployment state in F13.
- **Expected output:** The `vllm_metrics` message type is not emitted for `inst_a100_001` in this cycle. The `metrics` message still flows with GPU and system data. The agent logs show the error. A subsequent `command` message from the backend (F11) can trigger a restart.

### Example 4: Parsing a New vLLM Metric Version

vLLM v0.8.0 adds a new Prometheus gauge `vllm:request_pending_time_seconds` that the current parser does not recognise.

- **Input:** The Prometheus scrape returns a `/metrics` response containing the new gauge alongside all expected metrics.
- **Action:** The `prometheus_parser.py` module skips unknown metric names gracefully — it does not raise an exception or halt parsing. All recognised metrics (running, waiting, TTFT, TPS, cache usage, etc.) are extracted normally. The unrecognised gauge is logged once at `DEBUG` level with message `"Unrecognised metric: vllm:request_pending_time_seconds"` and discarded.
- **Expected output:** The `VllmMetricsSnapshot` contains all standard fields populated correctly. No data is lost for the recognised metrics. The agent continues operating without crashing or entering an error state.

### Example 5: Agent Paused via Lifecycle (F13)

The user pauses the agent from the dashboard (F13: pause lifecycle action).

- **Input:** The command handler (F11) receives a `{"type": "command", "command": "pause_agent"}`. It invokes `MetricCollector.pause()`.
- **Action:** The collector stops its poll loop (no new `nvidia-smi` or Prometheus scrapes). Existing running vLLM instances are NOT touched — they continue serving inference. The WebSocket connection (F7) remains alive but sends only heartbeats (no metric messages). When `MetricCollector.resume()` is called, the collector immediately runs a full poll cycle and resumes the 2-second interval.
- **Expected output:** No metric snapshots are emitted while paused. After resume, the next snapshot is complete and correctly timestamped. The gap in the data stream is handled gracefully by the backend ingestion (F10) as a natural gap — no backfill or catch-up is attempted.

## Acceptance Criteria

- **ACF8-1: GPU metrics are collected from nvidia-smi at the configured interval** — The `GpuCollector` executes `nvidia-smi --query-gpu=index,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw --format=csv,noheader,nounits` on every poll cycle. The output is parsed into a list of `GpuMetric` objects, one per physical GPU, each containing `index` (int), `util_pct` (float 0–100), `mem_used_mb` (int), `mem_total_mb` (int), `temp_c` (float), and `power_w` (float). If `nvidia-smi` exits with non-zero, all GPU fields are set to `None` and a `WARNING` is logged; the collector retries on the next cycle without requiring a restart.

- **ACF8-2: System metrics are collected via psutil** — The `SystemCollector` reads `psutil.cpu_percent(interval=0.5)` for CPU utilization, `psutil.getloadavg()` for 1/5/15-minute load averages, `psutil.virtual_memory()` for RAM usage (used and total in GB), and `psutil.disk_usage('/')` for disk usage (used in GB, total in GB, and usage percent). All values are collected within a 500 ms window. A failed or hanging `psutil` call (timeout > 2 seconds) is caught, logged as an `ERROR`, and the system metrics for that cycle are set to `None`.

- **ACF8-3: vLLM metrics are scraped from each instance's Prometheus endpoint** — The `VllmCollector` sends `GET /metrics` to every registered vLLM instance (e.g., `http://localhost:{port}/metrics`) on each poll cycle. The Prometheus text format response is parsed to extract: `vllm:num_requests_running`, `vllm:num_requests_waiting`, `vllm:prompt_tokens_total`, `vllm:generation_tokens_total`, `vllm:time_to_first_token_seconds` histogram (p50 and p99 computed from buckets), `vllm:gpu_cache_usage_perc`, `vllm:prefix_cache_hit_rate`, `vllm:request_success`, and `vllm:request_failure`. Unknown metric names are skipped with a `DEBUG` log (rate-limited to once per 5 minutes per unknown name). A connection error for any instance sets that instance's vLLM metrics to `None` and logs an `ERROR`.

- **ACF8-4: All three collectors produce a unified, timestamped snapshot per poll cycle** — The orchestrator (`MetricCollector.collect()`) invokes `GpuCollector`, `SystemCollector`, and `VllmCollector` in sequence, attaches the same ISO 8601 timestamp (`ts`) to all outputs, and returns a tuple of `(MetricSnapshot, list[VllmMetricsSnapshot])`. The entire collection cycle (three probes combined) completes within 1.5 seconds on a reference GPU server (2× A100, 64-core CPU, 512 GB RAM). If any single probe exceeds 3 seconds, the orchestrator logs a `WARNING` with the probe name and duration.

- **ACF8-5: Poll interval is configurable and the agent respects the pause lifecycle** — The poll interval defaults to 2 seconds and is configurable via the agent `config.py` (field `METRIC_POLL_INTERVAL_SECONDS`) and overridable by the backend's registration response (F6 field `config.poll_interval_seconds`). When `MetricCollector.pause()` is called by the lifecycle manager (F13), the poll loop stops within one cycle — no new metrics are collected until `MetricCollector.resume()` is called. Resume immediately triggers a full poll cycle and restarts the interval timer.

- **ACF8-6: All collector modules expose version-robust Prometheus parsing** — The prometheus parser in `modelprism_agent/metrics/prometheus_parser.py` is implemented as a deterministic line-by-line parser (not regex-only) that handles the standard Prometheus exposition format including `# HELP`, `# TYPE`, gauge lines, counter lines, histogram bucket lines with `+Inf`, and summary quantile lines. Unknown metric families are silently skipped. A malformed line (unparseable) is logged once at `WARNING` with the offending line content (truncated to 200 characters), and parsing continues with the next line. The parser never raises an unhandled exception.

## Technical Notes

- **File paths — agent collector modules:**
  - `modelprism-agent/modelprism_agent/metrics/collector.py` — Main `MetricCollector` orchestrator, poll loop, pause/resume.
  - `modelprism-agent/modelprism_agent/metrics/gpu.py` — `GpuCollector`: runs `nvidia-smi` subprocess and parses CSV output.
  - `modelprism-agent/modelprism_agent/metrics/system.py` — `SystemCollector`: wraps `psutil` calls.
  - `modelprism-agent/modelprism_agent/metrics/vllm.py` — `VllmCollector`: scrapes and parses vLLM Prometheus `/metrics` per instance.
  - `modelprism-agent/modelprism_agent/utils/prometheus_parser.py` — Reusable Prometheus text-format line parser (also used by benchmark runner F24).

- **File paths — shared schemas:**
  - `common/modelprism_common/schemas/metrics.py` — `MetricSnapshot`, `GpuMetric`, `VllmMetricsSnapshot` Pydantic models used by both the agent and the backend ingestion service (F10).

- **File paths — backend integration:**
  - `backend/app/api/metrics.py` — Historical metrics query endpoint (`GET /api/metrics/{agent_id}`) consumed by F15 (Single GPU server dashboard) and F17 (Time range selector).
  - `backend/app/services/agent_manager.py` — Agent state management, exposes `pause_metrics()` / `resume_metrics()` for F13 lifecycle integration.

- **nvidia-smi reliability:** On systems with GPU recovery events, `nvidia-smi` may intermittently fail or return `"[Insufficient Permissions]"` for power/temperature on specific GPUs. Handlers should treat per-field parsing failures as partial data — include the GPU entry with `None` for failed fields rather than dropping the entire GPU. The `GpuMetric` Pydantic model should use `Optional` fields for `temp_c` and `power_w` to accommodate driver-permission edge cases.

- **vLLM multimodel note:** A single GPU server may host multiple vLLM instances (F20 — Docker container per model). The `VllmCollector` maintains an internal registry `dict[str, VllmInstanceConfig]` keyed by `instance_id`. The registry is updated via a `register_instance(instance_id, port, model_name)` call from the command handler (F11) when a deployment succeeds, and `deregister_instance(instance_id)` when a model is stopped (F22). The collector scrapes all registered instances in each poll cycle; if the server has no running vLLM instances, the vLLM collector is skipped entirely (no network calls).

- **Prometheus histogram TTFT computation:** vLLM exposes `vllm:time_to_first_token_seconds` as a Prometheus histogram with bucket boundaries `{0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0}` (subject to change by vLLM version). The parser computes p50 and p99 by linear interpolation within the bucket that contains the respective quantile, using cumulative counts. This logic lives in `prometheus_parser.py` and is tested against known vLLM 0.6.x–0.8.x output.

- **Disk metric clarification:** `disk_used_gb` and `disk_total_gb` refer to the filesystem mounted at `/` (or `AGENT_DATA_DIR` if configured). The `HF_HOME` cache directory is typically a subdirectory of this mount and is not reported separately here — the dashboard (F15) may compute HF cache usage from `du` on the HF cache path if needed.

- **GPU cache percent vs vLLM cache percent:** `gpu_cache_pct` in the `metrics` message (from `nvidia-smi`) is the GPU memory utilization percent (total VRAM used / total VRAM available). `gpu_cache_pct` in the `vllm_metrics` message is the vLLM GPU KV cache utilization (from the vLLM internal gauge `vllm:gpu_cache_usage_perc`). These are different values and may diverge — the dashboard (F15) must label them distinctly.

- **Integration — F9 (Agent metric push):** The `MetricCollector` exposes an `on_snapshot` callback that is set by the WebSocket connection layer (`connection.py`). Each collected snapshot is passed to this callback, which enqueues it for batched transmission. The collector does not manage the WebSocket directly — it only emits snapshots. See F9 for the batching and wire protocol.

- **Integration — F10 (Backend metric ingestion):** The metric snapshot format defined here determines the schema that the backend ingestion pipeline (F10) receives over WebSocket. Any change to the snapshot fields must be reflected in the shared Pydantic models in `common/modelprism_common/schemas/metrics.py` and the database models in `backend/app/models/agent_logs.py` (or a dedicated `agent_metrics` table, see F10).

- **Integration — F11 (Command handler):** The `VllmCollector` receives instance registration/deregistration events from the command handler. When a `deploy_model` command completes, the command handler calls `vllm_collector.register_instance(...)`. When a `stop_model` command completes, it calls `vllm_collector.deregister_instance(...)`. This coupling is intentional — the collector scrapes only live instances.

- **Integration — F13 (Agent lifecycle):** The `MetricCollector` exposes `pause()` and `resume()` methods called by the lifecycle manager. The lifecycle manager (F13) owns the "paused" state transition. The collector does not independently decide to pause — it responds to the lifecycle manager's signal.

- **Error isolation:** Each collector runs in its own try/except block within the orchestrator's `collect()` method. A failure in GPU collection (e.g., `nvidia-smi` hung) does NOT prevent system or vLLM metrics from being collected. A failure in vLLM scraping for `instance_a` does NOT prevent scraping `instance_b`. Partial data is valid data.

- **Shared Pydantic schemas (common/modelprism_common/schemas/metrics.py):**

```python
from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime


class GpuMetric(BaseModel):
    index: int
    util_pct: Optional[float] = None  # 0–100
    mem_used_mb: Optional[int] = None
    mem_total_mb: Optional[int] = None
    temp_c: Optional[float] = None
    power_w: Optional[float] = None


class MetricSnapshot(BaseModel):
    gpu: Optional[list[GpuMetric]] = None
    cpu_pct: Optional[float] = None
    load_1: Optional[float] = None
    load_5: Optional[float] = None
    load_15: Optional[float] = None
    ram_used_gb: Optional[float] = None
    ram_total_gb: Optional[float] = None
    disk_used_gb: Optional[float] = None
    disk_total_gb: Optional[float] = None
    disk_pct: Optional[float] = None


class VllmMetricsSnapshot(BaseModel):
    instance_id: str
    ts: datetime
    model_name: str
    running: int
    waiting: int
    total_requests: int
    prompt_tokens_total: int
    gen_tokens_total: int
    ttft_p50_ms: float
    ttft_p99_ms: float
    gpu_cache_pct: float
    tps: float
    prefix_cache_hit_pct: Optional[float] = None
    error_pct: float
    trunc_pct: float
    server_start_ts: datetime
```

## Depends on: F13 (Agent lifecycle — pause/resume integration)
