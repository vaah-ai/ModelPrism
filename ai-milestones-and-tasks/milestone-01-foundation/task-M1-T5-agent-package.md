# Task M1-T5 — Agent Package

> **Milestone:** M1 (Foundation)
> **Priority:** Critical
> **Status:** 🟢 Complete
> **Estimated Effort:** 4 days

> **Impact from M1-T4:** Agent WebSocket handler backend is at `/ws/agents/{agent_id}` (FastAPI WebSocket endpoint in `app/ws/agent_ws.py`). The agent must send typed messages: `heartbeat` (every 15s with `agents_running` list), `metrics` (every 2s with GPU + system data), `vllm_metrics` (per-instance), `command_progress`, and `command_result`. All message schemas are in `app/schemas/ws_messages.py`. The backend delivers queued commands on heartbeat, so the agent must handle receiving commands via WebSocket. Latest metrics are stored in Redis at `agent:{id}:latest_metrics`. Use `async with client.ws_connect(...)` to establish connection.

## Description

Refactor the existing `vllm-collector-agent.py` into the proper `modelprism-agent` Python package structure. The agent collects GPU metrics (nvidia-smi), system metrics (psutil), and vLLM Prometheus metrics, registers with the ModelPrism backend using a token, maintains a persistent WebSocket connection, and pushes metric snapshots every 2 seconds. It also handles log streaming, reconnection with exponential backoff, and command processing.

## Task Goals

- Create `modelprism-agent/` package with `pyproject.toml` and proper module structure
- Implement `registration.py` — register with backend using token (two-phase flow)
- Implement `metrics/collector.py` — orchestrator that collects all metrics
- Implement `metrics/gpu.py` — nvidia-smi parsing (GPU util, VRAM, temp, power)
- Implement `metrics/system.py` — psutil-based CPU, RAM, disk collection
- Implement `metrics/vllm.py` — vLLM Prometheus metrics parser (reuse collector agent logic)
- Implement `connection.py` — WebSocket client with reconnection (exponential backoff)
- Implement `log_streamer.py` — push logs to backend via HTTP POST
- Implement `config.py` — agent settings (backend URL, token, poll interval)
- Implement `main.py` — entry point that orchestrates registration → connection → polling

## Implementation Plan

> ⚠️ Analyze this plan thoroughly before implementing.

### Pre-Implementation Analysis

- Read the existing `vllm-collector-agent.py` thoroughly — it contains working nvidia-smi parsing, Prometheus metric parsing, and system metric collection logic to refactor
- Review `requirements/07-directory-structure.md` for the agent directory layout
- Review `requirements/06-api-surface.md` for metric message shapes and registration API
- Review `requirements/02-architecture-overview.md` for agent architecture
- Review `requirements/05-tech-stack.md` for agent dependencies (httpx, psutil, websockets)
- Invoke `fastapi-expert` skill for httpx async HTTP/WS patterns

### Steps

1. Create `modelprism-agent/pyproject.toml` and `modelprism-agent/requirements.txt` with:
   - httpx (async HTTP + WebSocket)
   - psutil (system metrics)
   - huggingface_hub (future)
   - pydantic (config validation)
2. Create `modelprism-agent/modelprism_agent/__init__.py`
3. Create `modelprism-agent/modelprism_agent/config.py`:
   - `AgentConfig` Pydantic model: `backend_url`, `token`, `agent_id`, `poll_interval` (default 2s)
   - Load from CLI args + env vars
4. Create `modelprism-agent/modelprism_agent/registration.py`:
   - `register(backend_url, token)` → POST to `/api/agents/register`
   - Collect hardware info: GPUs (nvidia-smi), CPU (/proc/cpuinfo), RAM (/proc/meminfo), disk, OS
   - Return agent_id and ws_url from response
   - Retry with backoff on failure
5. Create `modelprism-agent/modelprism_agent/metrics/gpu.py`:
   - Refactor nvidia-smi parsing from existing collector agent
   - `get_gpu_count()`, `get_gpu_utilization()`, `get_gpu_memory()`, `get_gpu_temperature()`, `get_gpu_power()`
   - Handle no GPU installed gracefully
6. Create `modelprism-agent/modelprism_agent/metrics/system.py`:
   - Refactor psutil/proc-based system metrics from collector agent
   - `get_cpu_usage()`, `get_memory_usage()`, `get_disk_usage()`, `get_load_average()`
   - HF cache size via `du` on `~/.cache/huggingface/hub`
7. Create `modelprism-agent/modelprism_agent/metrics/vllm.py`:
   - Refactor Prometheus metrics parser from collector agent
   - `fetch_vllm_metrics(vllm_metrics_url)` → structured vLLM metrics dict
   - Handles: requests running/waiting, token counts, TTFT percentiles, GPU cache, throughput
8. Create `modelprism-agent/modelprism_agent/metrics/collector.py`:
   - `collect_all(vllm_metrics_url=None)` → combines GPU + system + vLLM metrics into one snapshot dict
   - Error handling per subsystem — partial data on individual failures
9. Create `modelprism-agent/modelprism_agent/connection.py`:
   - WebSocket client using httpx
   - `AgentConnection` class: `connect()`, `send_metrics(data)`, `send_heartbeat()`, `receive_commands()`
   - Exponential backoff reconnection (1s, 2s, 4s, 8s, max 60s)
   - Buffer metrics during disconnection (up to 60s / 30 samples)
   - Replay buffered metrics on reconnect
10. Create `modelprism-agent/modelprism_agent/log_streamer.py`:
    - `push_log(level, module, message, stack_trace=None)` → POST to `/api/agents/{id}/logs`
    - Async HTTP via httpx
    - Retry on network failure
11. Create `modelprism-agent/modelprism_agent/main.py`:
    - Parse args: `--backend` (required), `--token` (required), `--vllm-metrics` (optional), `--interval` (default 2)
    - Registration phase: call registration.py → get agent_id + ws_url
    - Connection phase: open WebSocket to backend
    - Poll loop: collect metrics → send over WS every `interval` seconds
    - Heartbeat thread: send heartbeat every 15 seconds
    - Command receive loop: process incoming commands (MVP: just log them)
    - Graceful shutdown on SIGTERM/SIGINT

### Skills & MCP Servers

| Resource              | Purpose                      | When to Invoke                   |
| --------------------- | ---------------------------- | -------------------------------- |
| `fastapi-expert`      | httpx async HTTP/WS patterns | Steps 4-10                      |
| `filesystem` (MCP)    | File creation                | Creating all agent package files |

## Acceptance Criteria

- [ ] Agent registers with backend and receives agent_id + ws_url
- [ ] Agent connects to WebSocket and stays connected
- [ ] Agent sends heartbeat every 15 seconds
- [ ] Agent pushes metrics every 2 seconds over WebSocket
- [ ] Metrics include: GPU util, VRAM used/total, temp, power, CPU, RAM, disk, vLLM stats
- [ ] Agent reconnects with exponential backoff on disconnect
- [ ] Agent buffers up to 60 seconds of metrics during disconnection
- [ ] Agent handles SIGTERM/SIGINT for graceful shutdown
- [ ] Existing `vllm-collector-agent.py` metric parsing logic is reused (not rewritten)

## Completion Criteria

- [ ] All acceptance criteria above pass
- [ ] Python type check passes (`mypy`)
- [ ] Code passes linting (`ruff`)
- [ ] Agent runs as standalone script

## Testing Checklist

- [ ] Unit test: nvidia-smi output parsing
- [ ] Unit test: vLLM Prometheus metrics parsing
- [ ] Unit test: collector aggregrates metrics correctly
- [ ] Integration test: registration → WS connect → push → disconnect flow

## Dependencies

- **Requires:** M1-T4 (Agent WebSocket Handler) — consumes the WS API
- **Blocks:** M1-T9 (Dashboard Pages) — agent needs to be running to show live data

## Documentation References

- `requirements/06-api-surface.md` — metric message types, registration API
- `requirements/07-directory-structure.md` — agent directory layout
- `requirements/05-tech-stack.md` — agent dependencies
- `requirements/03-functional-requirements.md` — F1.2, F1.3
- `requirements/04-non-functional-requirements.md` — NFR2.1

## Notes

- Reuse parsing logic from `vllm-collector-agent.py` — it has battle-tested nvidia-smi, proc filesystem, and Prometheus metric parsers
- The registration flow must match the backend's two-phase pattern from M1-T3
- Use `httpx.AsyncClient` for both HTTP and WebSocket — one client, one event loop
- Log to stdout with structured JSON format for production log aggregation
- The `pyproject.toml` should support `pip install` and `pip install -e .` for development
- Add a `__main__.py` so `python -m modelprism_agent` works as entry point
