# F24: Benchmark Runner

## 1. Specification

### 1.1 Overview

F24 adds a **benchmark runner** to ModelPrism-agent. The benchmark runner lets users send a configurable set of synthetic prompts (or a dataset) to a model endpoint, collect per-request latency and throughput metrics, and view the results in the ModelPrism frontend.

The runner lives entirely in `modelprism-agent` — it calls the local vLLM endpoint via the OpenAI-compatible API just like the chat loop does, but programmatically and without a user typing at the keyboard.

### 1.2 Acceptance Criteria

| # | Criterion | Details |
|---|-----------|---------|
| F24.1 | **Start benchmark** | User clicks "Run Benchmark" from the ModelPrism frontend → the agent receives a `run_benchmark` command → the agent starts sending prompts to the LLM endpoint and streaming progress back. |
| F24.2 | **Metrics collected** | For each prompt the runner measures: time-to-first-token (TTFT), tokens-per-output-token (TPOT), end-to-end latency, and token count (input + output). Aggregate statistics (p50/p95/p99/max) are computed at the end. |
| F24.3 | **Cancel in-flight** | The user can cancel a running benchmark from the frontend. The agent stops sending new prompts, discards partial results, and sends a cancellation acknowledgment. |
| F24.4 | **Results stored & displayed** | When the benchmark completes, the result is saved to `~/.modelprism/benchmarks/benchmark_<timestamp>.json` and the summary is returned to the frontend as a structured command result. |
| F24.5 | **Scenario presets** | Three predefined scenarios are available: *quick smoke* (5 prompts), *standard latency* (20 prompts), and *high throughput* (100 prompts). Each preset controls concurrency, prompt length distribution, and prompt count. |

### 1.3 Technical Architecture

```
┌────────────────────────────────────────────────┐
│ modelprism-agent                               │
│                                                │
│  run_benchmark command                          │
│  ┌───────────────────────┐                     │
│  │ RunBenchmarkExecutor  │                     │
│  │  • parse config       │                     │
│  │  • generate prompts   │                     │
│  │  • spawn workers      │                     │
│  │  • stream progress    │                     │
│  │  • assemble result    │                     │
│  └───────┬───────────────┘                     │
│          │ calls                               │
│          ▼                                     │
│  ┌───────────────────┐                         │
│  │ vLLM client       │                         │
│  │ (OpenAI client)   │ ←→ vLLM endpoint        │
│  └───────────────────┘                         │
│                                                │
│  Results saved to:                             │
│  ~/.modelprism/benchmarks/benchmark_*.json     │
└────────────────────────────────────────────────┘
```

### 1.4 F11 Integration

The benchmark runner plugs into the **F11 command dispatch system** exactly like every other agent command. No new WebSocket message types are needed:

| F11 Message | How F24 uses it |
|-------------|-----------------|
| `send_command` (client → agent) | Client sends `{ type: "send_command", command: "run_benchmark", params: { scenario, concurrency, ... } }` |
| `command_progress` (agent → client) | Agent streams `{ type: "command_progress", command_id, progress: { completed, total, ... } }` every N requests |
| `command_result` (agent → client) | Agent sends final results as `{ type: "command_result", command_id, result: { ... } }` |
| `cancel_command` (client → agent) | Client sends `{ type: "cancel_command", command_id }` to stop an in-flight benchmark |
| `command_cancelled` (agent → client) | Agent acknowledges with `{ type: "command_cancelled", command_id }` |

### 1.5 Error Handling

| Error | Behavior |
|-------|----------|
| 503 from vLLM endpoint | Retry up to 3 times with 1 s backoff; mark request as `failed` if all retries exhausted |
| 429 (rate limit) | Retry up to 5 times with exponential backoff (1, 2, 4, 8, 16 s) |
| Streaming timeout (no token for 60 s) | Abort that request, mark as `failed`, continue with remaining |
| Dataset file not found | Report error in command result, do not start benchmark |
| Concurrency > prompt count | Clamp concurrency to prompt count, emit a warning |
| Agent disconnects mid-benchmark | Benchmark is abandoned; partial results on disk are left in place |
| GPU / endpoint not available | Command returns immediate error: `Benchmark cannot start — vLLM endpoint is unreachable` |

---

## 2. Concrete Examples

### 2.1 Quick Smoke — 5 prompts, low concurrency

**User action:** Selects "Quick Smoke" from the scenario dropdown and clicks "Run Benchmark."

**Request** (WebSocket, client → agent):
```json
{
  "type": "send_command",
  "command_id": "cmd-bench-001",
  "command": "run_benchmark",
  "params": {
    "scenario": "quick_smoke",
    "concurrency": 1,
    "prompt_count": 5,
    "prompt_length_distribution": "short",
    "endpoint_url": "http://localhost:8000/v1/chat/completions",
    "model_name": "microsoft/Phi-4-mini-instruct",
    "max_tokens": 128,
    "temperature": 0.0
  }
}
```

**Progress stream** (agent → client):
```json
{ "type": "command_progress", "command_id": "cmd-bench-001", "progress": { "completed": 1, "total": 5 } }
{ "type": "command_progress", "command_id": "cmd-bench-001", "progress": { "completed": 2, "total": 5 } }
{ "type": "command_progress", "command_id": "cmd-bench-001", "progress": { "completed": 3, "total": 5 } }
{ "type": "command_progress", "command_id": "cmd-bench-001", "progress": { "completed": 4, "total": 5 } }
{ "type": "command_progress", "command_id": "cmd-bench-001", "progress": { "completed": 5, "total": 5 } }
```

**Result** (agent → client):
```json
{
  "type": "command_result",
  "command_id": "cmd-bench-001",
  "result": {
    "status": "completed",
    "scenario": "quick_smoke",
    "started_at": "2026-06-07T10:00:00Z",
    "completed_at": "2026-06-07T10:00:45Z",
    "duration_seconds": 45.2,
    "total_requests": 5,
    "succeeded": 5,
    "failed": 0,
    "latency_ms": {
      "ttft":  { "p50": 320,  "p95": 510,  "p99": 540,  "max": 540 },
      "tpot":  { "p50": 12.4, "p95": 18.2, "p99": 19.1, "max": 19.1 },
      "e2e":   { "p50": 2100, "p95": 4100, "p99": 4400, "max": 4400 }
    },
    "throughput": {
      "requests_per_second": 0.11,
      "tokens_per_second": 48.3
    },
    "config_snapshot": {
      "endpoint_url": "http://localhost:8000/v1/chat/completions",
      "model_name": "microsoft/Phi-4-mini-instruct",
      "max_tokens": 128,
      "temperature": 0.0,
      "concurrency": 1,
      "prompt_count": 5
    },
    "per_request": [
      {
        "request_index": 0,
        "ttft_ms": 320,
        "tpot_ms": 12.4,
        "e2e_latency_ms": 2100,
        "input_tokens": 45,
        "output_tokens": 128,
        "status": "success"
      }
    ]
  }
}
```

### 2.2 Standard Latency — 20 prompts, concurrency 4

**User action:** Selects "Standard Latency" and clicks "Run Benchmark."

**Request:**
```json
{
  "type": "send_command",
  "command_id": "cmd-bench-002",
  "command": "run_benchmark",
  "params": {
    "scenario": "standard_latency",
    "concurrency": 4,
    "prompt_count": 20,
    "prompt_length_distribution": "mixed",
    "endpoint_url": "http://localhost:8000/v1/chat/completions",
    "model_name": "microsoft/Phi-4-mini-instruct",
    "max_tokens": 512,
    "temperature": 0.7
  }
}
```

**Result (abbreviated):**
```json
{
  "type": "command_result",
  "command_id": "cmd-bench-002",
  "result": {
    "status": "completed",
    "scenario": "standard_latency",
    "duration_seconds": 142.0,
    "total_requests": 20,
    "succeeded": 20,
    "failed": 0,
    "latency_ms": {
      "ttft":  { "p50": 410,  "p95": 890,  "p99": 1200, "max": 1250 },
      "tpot":  { "p50": 18.7, "p95": 34.2, "p99": 41.0, "max": 41.0 },
      "e2e":   { "p50": 5800, "p95": 12000, "p99": 15000, "max": 15200 }
    },
    "throughput": {
      "requests_per_second": 0.14,
      "tokens_per_second": 72.0
    },
    "per_request": [
      { "request_index": 0, "ttft_ms": 380, "tpot_ms": 18.1, "e2e_latency_ms": 5500, "input_tokens": 112, "output_tokens": 512, "status": "success" },
      { "request_index": 1, "ttft_ms": 410, "tpot_ms": 18.7, "e2e_latency_ms": 5800, "input_tokens": 89,  "output_tokens": 512, "status": "success" }
    ]
  }
}
```

### 2.3 High Throughput — 100 prompts, concurrency 16

**User action:** Selects "High Throughput" scenario and clicks "Run Benchmark."

**Request:**
```json
{
  "type": "send_command",
  "command_id": "cmd-bench-003",
  "command": "run_benchmark",
  "params": {
    "scenario": "high_throughput",
    "concurrency": 16,
    "prompt_count": 100,
    "prompt_length_distribution": "short",
    "endpoint_url": "http://localhost:8000/v1/chat/completions",
    "model_name": "microsoft/Phi-4-mini-instruct",
    "max_tokens": 256,
    "temperature": 0.3
  }
}
```

**Result (abbreviated, per_request reduced for brevity):**
```json
{
  "type": "command_result",
  "command_id": "cmd-bench-003",
  "result": {
    "status": "completed",
    "scenario": "high_throughput",
    "duration_seconds": 94.5,
    "total_requests": 100,
    "succeeded": 98,
    "failed": 2,
    "errors": [
      { "request_index": 42, "error": "stream timeout after 60s", "phase": "streaming" },
      { "request_index": 73, "error": "503 after 3 retries",      "phase": "request" }
    ],
    "latency_ms": {
      "ttft":  { "p50": 280,  "p95": 620,  "p99": 1440, "max": 1800 },
      "tpot":  { "p50": 9.2,  "p95": 14.5, "p99": 22.0, "max": 24.0 },
      "e2e":   { "p50": 1800, "p95": 4100, "p99": 8900, "max": 9400 }
    },
    "throughput": {
      "requests_per_second": 1.06,
      "tokens_per_second": 271.0
    },
    "per_request": [
      { "request_index": 0, "ttft_ms": 250, "tpot_ms": 8.9, "e2e_latency_ms": 1700, "input_tokens": 32, "output_tokens": 256, "status": "success" }
    ]
  }
}
```

### 2.4 Cancel Mid-Benchmark

**User action:** Clicks "Cancel" after 14 of 100 prompts have completed.

**Cancel request** (client → agent):
```json
{
  "type": "cancel_command",
  "command_id": "cmd-bench-004"
}
```

**Cancellation acknowledgment** (agent → client):
```json
{
  "type": "command_cancelled",
  "command_id": "cmd-bench-004",
  "reason": "user_cancelled"
}
```

No result is sent — partial data on disk is left for debugging but not surfaced in the UI.

### 2.5 Endpoint Unavailable

**User action:** Clicks "Run Benchmark" while the vLLM endpoint is down.

**Request:**
```json
{
  "type": "send_command",
  "command_id": "cmd-bench-005",
  "command": "run_benchmark",
  "params": {
    "scenario": "quick_smoke",
    "concurrency": 1,
    "prompt_count": 5,
    "endpoint_url": "http://localhost:8000/v1/chat/completions",
    "model_name": "microsoft/Phi-4-mini-instruct",
    "max_tokens": 128,
    "temperature": 0.0
  }
}
```

**Immediate error result** (agent → client):
```json
{
  "type": "command_result",
  "command_id": "cmd-bench-005",
  "result": {
    "status": "error",
    "error": "Benchmark cannot start — vLLM endpoint at http://localhost:8000/v1/chat/completions is unreachable",
    "scenario": "quick_smoke"
  }
}
```

---

## 3. JSON Schema for Benchmark Command Params

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "RunBenchmarkParams",
  "type": "object",
  "required": ["scenario", "endpoint_url", "model_name"],
  "properties": {
    "scenario": {
      "type": "string",
      "enum": ["quick_smoke", "standard_latency", "high_throughput", "long_context", "custom"],
      "description": "Predefined scenario, or 'custom' for fully manual parameters."
    },
    "concurrency": {
      "type": "integer",
      "minimum": 1,
      "default": 1,
      "description": "Number of concurrent requests to the endpoint."
    },
    "prompt_count": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000,
      "default": 10,
      "description": "Total number of prompts to send."
    },
    "prompt_length_distribution": {
      "type": "string",
      "enum": ["short", "medium", "long", "mixed"],
      "default": "mixed",
      "description": "Distribution of synthetic prompt lengths."
    },
    "dataset_path": {
      "type": "string",
      "description": "Path to a HuggingFace-style dataset JSONL file for the 'custom' scenario. Ignored for predefined scenarios."
    },
    "endpoint_url": {
      "type": "string",
      "format": "uri",
      "description": "Full URL to the vLLM OpenAI-compatible chat completions endpoint."
    },
    "model_name": {
      "type": "string",
      "description": "Model name as expected by the vLLM endpoint (e.g. 'microsoft/Phi-4-mini-instruct')."
    },
    "max_tokens": {
      "type": "integer",
      "minimum": 1,
      "default": 256
    },
    "temperature": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 2.0,
      "default": 0.0
    }
  }
}
```

---

## 4. File Layout

```
modelprism-agent/
└── modelprism_agent/
    └── benchmark/
        ├── __init__.py           # Public API: run_benchmark(config) → BenchmarkResult
        ├── runner.py             # RunBenchmarkExecutor class (command handler)
        ├── config.py             # BenchmarkConfig dataclass
        ├── scenarios.py          # Predefined scenario presets
        ├── prompt_generator.py   # Synthetic prompt generation + HF dataset loader
        ├── metrics.py            # Latency/throughput aggregation (p50/p95/p99/max)
        └── models.py             # BenchmarkResult, PerRequestMetrics dataclasses
```
