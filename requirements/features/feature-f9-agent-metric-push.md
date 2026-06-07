# F9 — Agent Metric Push (Poll → Push Bridge)

## Owner
**Service:** `Agent Runtime` / `Collector Supervisor`  
**Depends on:** F7 (WebSocket), F8 (Collectors)  
**Consumed by:** F10 (Metric Ingestion), F12 (Log Stream), F15 (Dashboard), F16 (Broadcast), F35 (Retention)

## Summary

When a model-serving process (e.g. vLLM) exposes its own metrics endpoint (typically a Prometheus-format HTTP `/metrics`), the agent cannot poll that endpoint at the same fixed rate as system-level scrapers (F8) — it would miss transient GPU power capping, OOM prelude signals, or queuing spikes. F9 bridges this gap by giving each collector a configurable *per-endpoint poll frequency* and then pushing every result into the WebSocket stream (F7) in real time, so downstream consumers see sub-second granularity when they need it.

---

## Acceptance Criteria

### AC1 — Configurable Poll Frequency per Endpoint
**Given** a vLLM instance running on the same host  
**When** the agent starts  
**Then** it reads the endpoint → poll-interval mapping from `collectors.yml` (or env overrides)  
**And** each endpoint is polled independently at its declared interval (e.g. vLLM `/metrics` every 2 s, system CPU every 15 s)

### AC2 — Redis-Backed Metric Buffer
**Given** a metric payload that failed to send over WebSocket (network blip, reconnecting)  
**When** the send attempt fails  
**Then** the payload is written into a local Redis stream (`metrics:pending:<agent_id>`) with an `XADD MAXLEN ~ 1000`  
**And** a background goroutine replays the stream when the WebSocket connection is restored  
**And** any payload older than 60 s is dropped from the stream to avoid stale data

### AC3 — Heartbeat / Liveness Protocol
**Given** the agent has been running for longer than the configured heartbeat interval (default 10 s)  
**When** no userland metric has been emitted in that window  
**Then** the agent emits a heartbeat JSON payload (see examples below)  
**And** the server (F10) counts missing heartbeats within a sliding 30 s window; if ≥ 3 consecutive heartbeats are missed the agent is marked `STALE` in the registry and a `health.degraded` event is broadcast (F16)

### AC4 — Shared Schema Contract
**Given** any metric payload is about to be serialised  
**When** the payload is constructed  
**Then** it MUST conform to the union type `MetricsSnapshot | Heartbeat` defined in the shared `modelprism.schemas.metrics` module  
**And** the `agent_id`, `sequence_nr`, and `timestamp` fields are present on every message  
**And** a `MetricsSnapshot` with `sequence_nr == 0` (or lower than the last accepted sequence number for that agent) MUST be silently dropped by F10 unless the agent has restarted (indicated by a new `session_id`)

---

## Concrete Examples

### Example 1 — Normal Metrics Snapshot (vLLM + GPU)
```json
{
  "type": "metrics_snapshot",
  "agent_id": "node-7-agent",
  "session_id": "sess-a1b2",
  "sequence_nr": 1423,
  "timestamp": "2026-06-07T14:30:01.123Z",
  "vllm_instances": [
    {
      "model": "llama-3-70b",
      "gpu_mem_used_gb": 68.2,
      "gpu_mem_total_gb": 80.0,
      "kv_cache_usage_pct": 87.3,
      "requests_running": 12,
      "requests_queued": 4,
      "throughput_req_per_sec": 8.7
    }
  ],
  "system": {
    "cpu_usage_pct": 34.1,
    "memory_used_gb": 112.0,
    "memory_total_gb": 256.0,
    "gpu_metrics": [
      {
        "gpu_index": 0,
        "gpu_util_pct": 95.2,
        "gpu_mem_used_gb": 74.1,
        "gpu_mem_total_gb": 80.0,
        "gpu_temp_c": 82,
        "power_draw_w": 385,
        "power_limit_w": 400
      }
    ]
  }
}
```

### Example 2 — Idle Agent (No Running Requests)
```json
{
  "type": "metrics_snapshot",
  "agent_id": "node-7-agent",
  "session_id": "sess-a1b2",
  "sequence_nr": 1424,
  "timestamp": "2026-06-07T14:30:03.156Z",
  "vllm_instances": [
    {
      "model": "llama-3-70b",
      "gpu_mem_used_gb": 68.2,
      "gpu_mem_total_gb": 80.0,
      "kv_cache_usage_pct": 87.3,
      "requests_running": 0,
      "requests_queued": 0,
      "throughput_req_per_sec": 0.0
    }
  ],
  "system": {
    "cpu_usage_pct": 12.5,
    "memory_used_gb": 108.0,
    "memory_total_gb": 256.0,
    "gpu_metrics": [
      {
        "gpu_index": 0,
        "gpu_util_pct": 8.3,
        "gpu_mem_used_gb": 74.1,
        "gpu_mem_total_gb": 80.0,
        "gpu_temp_c": 59,
        "power_draw_w": 62,
        "power_limit_w": 400
      }
    ]
  }
}
```

### Example 3 — Multi-GPU / Multi-Instance
```json
{
  "type": "metrics_snapshot",
  "agent_id": "node-12-agent",
  "session_id": "sess-c3d4",
  "sequence_nr": 2891,
  "timestamp": "2026-06-07T14:30:05.789Z",
  "vllm_instances": [
    {
      "model": "mixtral-8x7b",
      "gpu_mem_used_gb": 42.0,
      "gpu_mem_total_gb": 48.0,
      "kv_cache_usage_pct": 72.1,
      "requests_running": 6,
      "requests_queued": 2,
      "throughput_req_per_sec": 5.2
    },
    {
      "model": "llama-3-8b",
      "gpu_mem_used_gb": 14.5,
      "gpu_mem_total_gb": 16.0,
      "kv_cache_usage_pct": 45.0,
      "requests_running": 3,
      "requests_queued": 1,
      "throughput_req_per_sec": 12.1
    }
  ],
  "system": {
    "cpu_usage_pct": 41.8,
    "memory_used_gb": 198.0,
    "memory_total_gb": 512.0,
    "gpu_metrics": [
      { "gpu_index": 0, "gpu_util_pct": 88.0, "gpu_mem_used_gb": 44.2, "gpu_mem_total_gb": 48.0, "gpu_temp_c": 79, "power_draw_w": 310, "power_limit_w": 350 },
      { "gpu_index": 1, "gpu_util_pct": 76.4, "gpu_mem_used_gb": 14.8, "gpu_mem_total_gb": 48.0, "gpu_temp_c": 71, "power_draw_w": 245, "power_limit_w": 350 },
      { "gpu_index": 2, "gpu_util_pct": 2.1, "gpu_mem_used_gb": 6.1, "gpu_mem_total_gb": 48.0, "gpu_temp_c": 52, "power_draw_w": 55, "power_limit_w": 350 },
      { "gpu_index": 3, "gpu_util_pct": 1.8, "gpu_mem_used_gb": 5.9, "gpu_mem_total_gb": 48.0, "gpu_temp_c": 51, "power_draw_w": 52, "power_limit_w": 350 }
    ]
  }
}
```

### Example 4 — Heartbeat (No Userland Metrics in Window)
```json
{
  "type": "heartbeat",
  "agent_id": "node-7-agent",
  "session_id": "sess-a1b2",
  "sequence_nr": 0,
  "timestamp": "2026-06-07T14:30:12.000Z",
  "uptime_seconds": 84720,
  "last_metric_seq": 1424
}
```

### Example 5 — Validation Error (Server Response)
```json
{
  "type": "metric_error",
  "agent_id": "node-7-agent",
  "session_id": "sess-a1b2",
  "sequence_nr": 1425,
  "timestamp": "2026-06-07T14:30:03.200Z",
  "error_code": "SCHEMA_VIOLATION",
  "detail": "Field 'vllm_instances[0].gpu_mem_used_gb' exceeds declared maximum of 80.0",
  "retryable": false
}
```

---

## Shared Pydantic Schemas (modelprism/schemas/metrics.py)

```python
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class GpuMetric(BaseModel):
    gpu_index: int = Field(..., ge=0)
    gpu_util_pct: float = Field(..., ge=0.0, le=100.0)
    gpu_mem_used_gb: float = Field(..., ge=0.0)
    gpu_mem_total_gb: float = Field(..., ge=0.0)
    gpu_temp_c: float = Field(..., ge=0.0)
    power_draw_w: float = Field(..., ge=0.0)
    power_limit_w: float = Field(..., ge=0.0)


class SystemMetric(BaseModel):
    cpu_usage_pct: float = Field(..., ge=0.0, le=100.0)
    memory_used_gb: float = Field(..., ge=0.0)
    memory_total_gb: float = Field(..., ge=0.0)
    gpu_metrics: List[GpuMetric]


class VllmInstanceMetric(BaseModel):
    model: str
    gpu_mem_used_gb: float = Field(..., ge=0.0)
    gpu_mem_total_gb: float = Field(..., ge=0.0)
    kv_cache_usage_pct: float = Field(..., ge=0.0, le=100.0)
    requests_running: int = Field(..., ge=0)
    requests_queued: int = Field(..., ge=0)
    throughput_req_per_sec: float = Field(..., ge=0.0)


class MetricsSnapshot(BaseModel):
    type: str = "metrics_snapshot"
    agent_id: str
    session_id: str
    sequence_nr: int = Field(..., ge=0)
    timestamp: datetime
    vllm_instances: List[VllmInstanceMetric]
    system: SystemMetric


class Heartbeat(BaseModel):
    type: str = "heartbeat"
    agent_id: str
    session_id: str
    sequence_nr: int = 0
    timestamp: datetime
    uptime_seconds: int = Field(..., ge=0)
    last_metric_seq: int = Field(..., ge=0)


class MetricAck(BaseModel):
    type: str = "metric_ack"
    agent_id: str
    accepted_seq: int
    next_expected_seq: int


class MetricError(BaseModel):
    type: str = "metric_error"
    agent_id: str
    session_id: str
    sequence_nr: int
    timestamp: datetime
    error_code: str
    detail: str
    retryable: bool
```

---

## Edge Cases

| Scenario | Expected Behaviour |
|---|---|
| `nvidia-smi` fails mid-poll | Populate `GpuMetric` fields with `-1.0` or omit the `gpu_metrics` list; set a `warnings` key with the driver error string |
| Clock drift between agent and server | Server (F10) uses its own wall clock for the ingestion timestamp; agent's `timestamp` is stored as a separate `reported_at` field for latency calculations |
| Collector process hangs (e.g. vLLM stuck) | A per-collector watchdog goroutine kills and restarts the poll if it exceeds `poll_interval × 3` without a response; a `collector.hang` warning is appended to the next successful snapshot |
| WebSocket reconnects with pending Redis stream | Replay begins at the oldest entry; if the server responds with `MetricError` + `retryable: false` the stream is purged for that entry to avoid poison messages |
| Agent restarts with same `agent_id` but new `session_id` | F10 resets the sequence-number tracker; previously buffered stream entries with the old `session_id` are dropped |

---

## Redis Stream Integration

```
XADD metrics:pending:node-7-agent MAXLEN ~ 1000 * payload <json>
```

The stream acts as a decoupling buffer: the poll loop writes synchronously to Redis (sub-millisecond), and a separate publisher goroutine reads from the stream and pushes over WebSocket. This prevents a slow WebSocket write from blocking the next poll cycle.

When the WebSocket is healthy, the publisher drains the stream faster than the poll loop fills it, so the stream stays near-empty under normal operation.
