# F11: Agent command handler

## Metadata
- **ID:** F11
- **Phase:** Foundation
- **Effort:** Medium
- **Dependencies:** F7
- **Acceptance Criteria Count:** 6

## Description

The agent command handler is the bidirectional command execution system that connects the ModelPrism backend to each registered GPU-server agent via the persistent WebSocket channel established in F7. When the dashboard user triggers an action — deploying a model, stopping a running inference server, restarting a container, downloading weights, or running a benchmark — the backend serializes the request into a structured command message and pushes it over the agent's WebSocket connection. The agent receives the command, executes it against the local system (Docker, vLLM, model downloader, or benchmark runner), and streams progress updates and a final result back over the same WebSocket.

The system follows a fire-and-respond pattern: the backend stores no command queue on the server side — commands are sent directly over the live WebSocket. If the agent is offline, the backend rejects the command immediately with a clear error identifying the agent's disconnected state. For long-running operations (model downloads, benchmark runs), the agent emits periodic `command_progress` messages that the backend relays to any connected dashboard WebSocket client, giving the user real-time visibility into the operation's status. Each command carries a `command_id` (UUID v4) that correlates progress updates and the final result across all WebSocket subscribers.

This feature depends on F7 (the agent WebSocket connection handler) for the underlying transport channel. It integrates with F20 (Docker-based model deployment) and F21 (resumable model download) on the agent side for execution, and with F15/F16 on the dashboard side for real-time progress visualization. The agent language runtime is Python; the command dispatcher lives in `modelprism-agent/modelprism_agent/command_handler.py`, and the shared command message schemas are defined in `common/modelprism_common/schemas/commands.py`.

## Concrete Examples (Specification by Example)

### Example 1: Deploy Model — Successful Flow

- **Input:** The dashboard user completes the deploy wizard (F19) selecting `mistralai/Mistral-7B-Instruct-v0.3` to deploy on agent `ag_cyan_koala_42` with `tensor_parallel_size=1`, `max_model_len=32768`, `gpu_memory_utilization=0.9`, and port `8001`.
- **Action:** The backend route handler `POST /api/models/deploy` serializes the deployment request into a `deploy_model` command and pushes it via the F7 WebSocket to the target agent. The agent's `command_handler.py` receives the message, dispatches to `model_downloader.py` (downloads weights from HuggingFace Hub), then to `docker_manager.py` (starts a Docker container with vLLM), then performs a health check against `http://localhost:8001/v1/models`. Throughout execution, the agent emits `command_progress` messages.
- **Expected Output — Backend → Agent WebSocket command:**
  ```json
  {
    "type": "command",
    "command_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "command": "deploy_model",
    "params": {
      "hf_model_id": "mistralai/Mistral-7B-Instruct-v0.3",
      "huggingface_token": null,
      "vllm_params": {
        "tensor_parallel_size": 1,
        "max_model_len": 32768,
        "gpu_memory_utilization": 0.9,
        "port": 8001,
        "served_model_name": "mistral-7b",
        "quantization": null,
        "max_num_seqs": 256,
        "enable_prefix_caching": true,
        "enforce_eager": false,
        "kv_cache_dtype": "auto"
      },
      "timeout_seconds": 600
    }
  }
  ```

- **Expected Output — Agent → Backend progress messages (sequential):**
  ```json
  {"type": "command_progress", "command_id": "a1b2c3d4-...", "status": "downloading", "progress_pct": 0,   "message": "Initiating model download from HuggingFace Hub..."}
  {"type": "command_progress", "command_id": "a1b2c3d4-...", "status": "downloading", "progress_pct": 45,  "message": "Downloading model weights... (2.4 GB / 5.3 GB)"}
  {"type": "command_progress", "command_id": "a1b2c3d4-...", "status": "downloading", "progress_pct": 100, "message": "Download complete. Verifying checksums..."}
  {"type": "command_progress", "command_id": "a1b2c3d4-...", "status": "starting",    "progress_pct": null, "message": "Starting Docker container for vLLM..."}
  {"type": "command_progress", "command_id": "a1b2c3d4-...", "status": "starting",    "progress_pct": null, "message": "Container started (abc123def456). Running health check..."}
  ```

- **Expected Output — Agent → Backend result:**
  ```json
  {
    "type": "command_result",
    "command_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "status": "success",
    "result": {
      "instance_id": "inst_mistral7b_001",
      "port": 8001,
      "docker_container_id": "abc123def456",
      "endpoint": "http://localhost:8001/v1",
      "model_name": "mistral-7b",
      "pid": 12345,
      "startup_duration_ms": 42300
    }
  }
  ```

### Example 2: Deploy Model — Agent Offline

- **Input:** The dashboard user submits `POST /api/models/deploy` with `hf_model_id: "mistralai/Mistral-7B-Instruct-v0.3"` targeting agent `ag_offline_koala_99`, but the agent's WebSocket connection is not active (F7 connection status shows `offline`).
- **Action:** The backend route handler checks the agent's online status before constructing the command. Since the agent is offline, it returns an error immediately without attempting to send a WebSocket message. No Docker container is created; no weights are downloaded.
- **Expected Output — HTTP 409 Conflict:**
  ```json
  {
    "errors": [
      {
        "status": "409",
        "code": "AGENT_OFFLINE",
        "title": "Agent is offline",
        "detail": "Agent 'ag_offline_koala_99' is currently offline. Commands cannot be delivered until the agent reconnects.",
        "meta": {
          "agent_id": "ag_offline_koala_99",
          "last_seen_at": "2026-06-07T10:15:00+00:00"
        }
      }
    ]
  }
  ```

### Example 3: Stop Model — Graceful Shutdown with Progress

- **Input:** The dashboard user clicks "Stop" on a running model deployment with ID `550e8400-e29b-41d4-a716-446655440000` (vLLM serving `Qwen/Qwen2.5-72B-Instruct` on agent `ag_cyan_koala_42`).
- **Action:** The backend route handler `POST /api/models/550e8400-.../stop` looks up the active WebSocket connection for the agent and sends a `stop_model` command. The agent sends SIGTERM to the Docker container, waits up to 30 seconds for graceful shutdown, then force-kills if necessary. It reports progress at each stage and finalizes with a success or partial-failure result.
- **Expected Output — Backend → Agent WebSocket command:**
  ```json
  {
    "type": "command",
    "command_id": "f1a2b3c4-d5e6-7890-abcd-ef1234567891",
    "command": "stop_model",
    "params": {
      "instance_id": "inst_001",
      "docker_container_id": "abc123def456",
      "graceful_timeout_seconds": 30,
      "force": false
    }
  }
  ```

- **Expected Output — Agent → Backend progress messages:**
  ```json
  {"type": "command_progress", "command_id": "f1a2b3c4-...", "status": "stopping",  "progress_pct": null, "message": "Sending SIGTERM to container abc123def456..."}
  {"type": "command_progress", "command_id": "f1a2b3c4-...", "status": "stopping",  "progress_pct": null, "message": "Waiting for running requests to complete (5 remaining)..."}
  {"type": "command_progress", "command_id": "f1a2b3c4-...", "status": "stopping",  "progress_pct": null, "message": "Container stopped successfully."}
  ```

- **Expected Output — Agent → Backend result:**
  ```json
  {
    "type": "command_result",
    "command_id": "f1a2b3c4-d5e6-7890-abcd-ef1234567891",
    "status": "success",
    "result": {
      "instance_id": "inst_001",
      "docker_container_id": "abc123def456",
      "stopped_gracefully": true,
      "shutdown_duration_ms": 5200,
      "port_freed": 8001
    }
  }
  ```

### Example 4: Command Timeout — Agent Does Not Respond

- **Input:** The backend sends a `deploy_model` command for a very large model (`meta-llama/Llama-3.1-405B-Instruct`) with `timeout_seconds: 1800` (30 minutes) on agent `ag_cyan_koala_42`. The download stalls at 73% and no progress or result message arrives within the timeout window.
- **Action:** The agent-side command executor detects the timeout via an `asyncio.wait_for` wrapping the execution coroutine. It cancels the running task, cleans up partial resources (removes partially downloaded weights, kills any spawned container), and sends a `command_result` with `status: "timeout"`. The backend receives the timeout result, updates the `model_deployments` row to `failed`, and broadcasts the failure to dashboard WebSocket subscribers.
- **Expected Output — Agent → Backend result after timeout:**
  ```json
  {
    "type": "command_result",
    "command_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "status": "timeout",
    "error": {
      "code": "EXECUTION_TIMEOUT",
      "message": "Command execution exceeded the 1800 second timeout.",
      "details": "Download stalled at 73% for 300 seconds with no bytes transferred. Partial download cleaned up."
    },
    "partial_result": {
      "downloaded_bytes": 3890000000,
      "total_bytes": 5300000000,
      "elapsed_seconds": 1800
    }
  }
  ```

### Example 5: Agent Disconnects Mid-Command

- **Input:** The agent is executing a `run_benchmark` command (running 1000 requests against the local vLLM instance) when its network connection drops (WiFi failure, DHCP lease expiry). The WebSocket closes unexpectedly. The benchmark was 60% complete.
- **Action:** The F7 connection handler detects the disconnect and sets the agent status to `offline`. The backend marks all in-flight commands for that agent as `interrupted` and updates the `benchmark_runs` table status to `failed`. On reconnect (exponential backoff from the agent), the agent checks for any previously incomplete operations by scanning local state files in `/tmp/modelprism/`. It does not auto-resume unrequested commands — the dashboard user must re-issue the command. The backend cleans up stale command-tracker entries after a 5-minute grace period.
- **Expected Output — Backend-side cleanup on disconnect:**
  - `benchmark_runs` row updated: `status = "failed"`, `error_message = "Agent disconnected during execution (WebSocket closed unexpectedly)"`, `completed_at = "2026-06-07T14:30:15+00:00"`
  - Backend log entry: `WARNING — "Agent ag_cyan_koala_42 disconnected with 2 in-flight commands (cmd_001, cmd_002). Marking as interrupted."`
  - Dashboard WebSocket broadcast: `{"type": "command_interrupted", "command_id": "b2c3d4e5-...", "agent_id": "ag_cyan_koala_42", "message": "Agent disconnected during benchmark run. Please re-issue the command after reconnection."}`

## Acceptance Criteria

- **ACF11-1: Commands are delivered exclusively over live WebSocket connections** — The backend SHALL send a command to an agent only if the agent's WebSocket connection is active (status `online` per F7's connection tracker). If the agent is `offline`, `paused`, or `stopped`, the backend SHALL reject the command with an `AGENT_OFFLINE` JSON:API error (HTTP 409) and SHALL NOT queue the command for later delivery. The response SHALL include the `agent_id` and `last_seen_at` timestamp in the error `meta` object.

- **ACF11-2: Every command carries a UUID `command_id` and is correlated end-to-end** — The backend SHALL generate a UUID v4 `command_id` for each command before sending it over the WebSocket. The agent SHALL include this exact `command_id` in every `command_progress` and `command_result` message it sends back. The backend SHALL use the `command_id` to correlate progress updates and the final result with the original request stored in a lightweight in-memory tracker (`backend/app/services/command_tracker.py`). The tracker SHALL store the mapping of `command_id → { agent_id, command_type, status, created_at, completed_at }`. Stale entries (no activity for 5 minutes after the command completes or fails) SHALL be evicted from the tracker.

- **ACF11-3: The agent provides granular progress updates for long-running commands** — For any command with an estimated duration exceeding 5 seconds (`deploy_model`, `stop_model`, `download_model`, `run_benchmark`), the agent SHALL emit `command_progress` messages at meaningful state transitions. The progress message SHALL contain:
  - `command_id` (UUID v4, matches the original command)
  - `status` (string: one of `"downloading"`, `"starting"`, `"stopping"`, `"restarting"`, `"running"`, `"cleaning_up"`, or a command-specific phase name)
  - `progress_pct` (integer 0–100, or `null` for status phases that have no percentage progress)
  - `message` (human-readable string describing the current operation)
  
  The agent SHALL send at minimum one progress message at each phase transition. The backend SHALL relay these progress messages to any dashboard WebSocket subscribers (F16) listening to the target agent, wrapping them in a `{"type": "agent_command_progress", ...}` envelope. No progress message from the agent SHALL be dropped or buffered for longer than 200ms on the backend.

- **ACF11-4: Every command completes with a terminal result message containing success or structured failure** — The agent SHALL send exactly one `command_result` message per command, carrying one of four terminal statuses:
  - `"success"` — command completed. The `result` object SHALL contain command-specific payload (e.g., `instance_id`, `docker_container_id`, `port` for `deploy_model`; summary metrics for `run_benchmark`).
  - `"failed"` — command completed with an error. The payload SHALL include an `error` object with `code` (string error code, e.g., `"DOWNLOAD_FAILED"`, `"DOCKER_ERROR"`, `"HEALTH_CHECK_FAILED"`), `message` (human-readable summary), and optional `details` (free-form string or object with additional context).
  - `"timeout"` — command exceeded its `timeout_seconds` parameter. The payload SHALL include the `error` object plus a `partial_result` object documenting any work completed before the timeout was enforced.
  - `"cancelled"` — command was explicitly cancelled by the backend via a `cancel_command` message while the agent was executing it.

  The backend SHALL process the terminal result and propagate it to all relevant downstream systems: update the `model_deployments` or `benchmark_runs` table row with the final status, log the result, and broadcast the outcome to dashboard WebSocket subscribers.

- **ACF11-5: Agent disconnection during command execution marks the command as interrupted** — When the F7 connection handler detects an agent WebSocket disconnection, the backend SHALL immediately query the in-memory command tracker for any in-flight `command_id` values associated with that agent. Each in-flight command SHALL be:
  1. Removed from the in-memory tracker (no further progress expected).
  2. Logged with timestamp and agent ID.
  3. Broadcast to dashboard WebSocket subscribers as `{"type": "command_interrupted", "command_id": "..."}`.
  4. The affected database record (`model_deployments` or `benchmark_runs`) SHALL be updated to `failed` or `stopped` status with the error message `"Agent disconnected during execution (WebSocket closed unexpectedly at <timestamp>)"`.
  
  The backend SHALL NOT auto-retry interrupted commands. The dashboard user SHALL re-issue the command after the agent reconnects. The agent SHALL clean up any partially-completed work (partial downloads, zombie containers) during its reconnect sequence by scanning for orphaned state files in `/tmp/modelprism/`.

- **ACF11-6: All command types, their parameter schemas, and their result schemas are defined in the shared common package** — The file `common/modelprism_common/schemas/commands.py` SHALL define Pydantic models for every supported command type:
  - `DeployModelParams`: `hf_model_id` (str), `huggingface_token` (Optional[str]), `vllm_params` (nested `VllmParams` model with `tensor_parallel_size`, `max_model_len`, `gpu_memory_utilization`, `quantization`, `port`, `served_model_name`, `max_num_seqs`, `enable_prefix_caching`, `enforce_eager`, `kv_cache_dtype`), `timeout_seconds` (int, default 600).
  - `StopModelParams`: `instance_id` (str), `docker_container_id` (str), `graceful_timeout_seconds` (int, default 30), `force` (bool, default false).
  - `RestartModelParams`: `instance_id` (str), `docker_container_id` (str), `timeout_seconds` (int, default 120).
  - `DownloadModelParams`: `hf_model_id` (str), `huggingface_token` (Optional[str]), `revision` (Optional[str]), `timeout_seconds` (int, default 3600).
  - `RunBenchmarkParams`: `config` (BenchmarkConfig model with `num_requests`, `concurrency`, `input_length_distribution`, `output_token_count`, `dataset_name`), `timeout_seconds` (int, default 1800).
  - `CancelCommandParams`: `command_id` (UUID, the ID of the command to cancel).

  Each params model SHALL inherit from a `CommandParams` base class. The `CommandMessage` wrapper SHALL contain `type: Literal["command"]`, `command_id: UUID`, `command: str` (one of the command type names), and `params: CommandParams` (discriminated union). The `CommandProgress` and `CommandResult` messages SHALL also be defined as shared Pydantic models. The agent's `command_handler.py` SHALL import and validate incoming commands against these schemas before dispatching to the appropriate executor. The backend SHALL import the same schemas when constructing commands.

## Technical Notes

### File Structure

```
modelprism-agent/modelprism_agent/
├── command_handler.py              # WebSocket message dispatch, command execution orchestration
├── manager/
│   ├── docker_manager.py           # Docker container lifecycle (start, stop, restart, inspect)
│   ├── vllm_manager.py            # vLLM config generation and health-check polling
│   └── model_downloader.py        # HF Hub snapshot_download with resume and progress callbacks

backend/app/
├── ws/agent_ws.py                 # F7 WebSocket connection handler (receives agent messages, dispatches)
├── services/
│   ├── command_tracker.py          # In-memory tracker of in-flight commands per agent
│   └── agent_manager.py           # Agent state management, online/offline status
├── api/models.py                   # REST routes: /api/models/deploy, stop, restart, etc.

common/modelprism_common/schemas/
├── commands.py                     # Shared Pydantic models: CommandMessage, CommandProgress,
│                                   #   CommandResult, DeployModelParams, StopModelParams,
│                                   #   RestartModelParams, DownloadModelParams,
│                                   #   RunBenchmarkParams, CancelCommandParams
└── events.py                       # Shared event message types (metrics, heartbeat, log)
```

### Command Wire Protocol (WebSocket Message Types)

All agent WebSocket messages use the lightweight format defined in the API surface (not JSON:API — that is for dashboard REST only). The relevant message types for F11 are:

| Direction | `type` field | Purpose |
|-----------|-------------|---------|
| Backend → Agent | `"command"` | Issue a new command to the agent |
| Backend → Agent | `"cancel_command"` | Request cancellation of a running command |
| Agent → Backend | `"command_progress"` | Report execution progress |
| Agent → Backend | `"command_result"` | Report terminal outcome (success/fail/timeout/cancelled) |

### Command Tracker (`backend/app/services/command_tracker.py`)

An in-memory dictionary (thread-safe for async via `asyncio.Lock`) maps `command_id → CommandRecord`. The record contains:

```python
@dataclass
class CommandRecord:
    command_id: uuid.UUID
    agent_id: str
    command_type: str            # "deploy_model", "stop_model", etc.
    status: str                  # "in_flight", "completed", "failed", "timeout", "cancelled", "interrupted"
    created_at: datetime
    completed_at: datetime | None = None
    progress_messages: list[CommandProgress] = field(default_factory=list)
    result: CommandResult | None = None
```

The tracker exposes:
- `register(agent_id, command_type) → CommandRecord` — creates a new record with a fresh UUID
- `get(command_id) → CommandRecord | None`
- `get_in_flight(agent_id) → list[CommandRecord]` — all running commands for an agent
- `update_progress(command_id, progress_msg)` — appends a progress message
- `complete(command_id, result_msg)` — marks as completed/failed/timeout/cancelled and sets `completed_at`
- `eviction_cleanup()` — removes records older than 5 minutes from `completed_at`

The tracker is **not** persisted to the database — it is an ephemeral state store. On backend restart, all in-flight commands are implicitly lost and the agent will receive no further progress updates. The agent handles this by detecting WebSocket disconnection and cleaning up locally.

### Agent-Side Command Handling (`command_handler.py`)

The `CommandHandler` class is instantiated once per agent process and registered as a message handler on the WebSocket connection. Its structure:

```python
class CommandHandler:
    def __init__(self, docker_mgr: DockerManager, downloader: ModelDownloader,
                 vllm_mgr: VllmManager, benchmark_runner: BenchmarkRunner):
        self._executors: dict[str, Callable] = {
            "deploy_model": self._execute_deploy,
            "stop_model": self._execute_stop,
            "restart_model": self._execute_restart,
            "download_model": self._execute_download,
            "run_benchmark": self._execute_benchmark,
        }

    async def handle_command(self, ws, message: CommandMessage) -> None:
        """Validate, dispatch, and manage lifecycle of a single command."""
        executor = self._executors.get(message.command)
        if executor is None:
            await ws.send(CommandResult(
                command_id=message.command_id,
                status="failed",
                error={"code": "UNKNOWN_COMMAND", "message": f"No executor for '{message.command}'"}
            ).model_dump_json())
            return

        # Execute with timeout
        try:
            result = await asyncio.wait_for(
                executor(ws, message.command_id, message.params),
                timeout=message.params.timeout_seconds
            )
            await ws.send(result.model_dump_json())
        except asyncio.TimeoutError:
            # Cleanup partial work
            await self._cleanup_partial(message)
            await ws.send(CommandResult(
                command_id=message.command_id,
                status="timeout",
                error={"code": "EXECUTION_TIMEOUT", "message": f"Exceeded {message.params.timeout_seconds}s timeout"}
            ).model_dump_json())
```

Each executor function is an async coroutine that:
1. Validates parameters (check disk space, available VRAM, port availability).
2. Executes the operation by calling the appropriate manager module.
3. Calls `send_progress(ws, command_id, ...)` on state transitions.
4. Returns a `CommandResult` on completion.

The `send_progress` helper:
```python
async def send_progress(ws, command_id: str, status: str, pct: int | None, msg: str):
    await ws.send(CommandProgress(
        command_id=command_id, status=status, progress_pct=pct, message=msg
    ).model_dump_json())
```

### Cancellation Protocol

The backend can cancel a running command by sending:
```json
{
  "type": "cancel_command",
  "command_id": "a1b2c3d4-..."
}
```

The agent's command handler SHALL:
1. Look up the running `asyncio.Task` for the given `command_id`.
2. Call `task.cancel()` which raises `asyncio.CancelledError` inside the executor.
3. The executor's exception handler catches `CancelledError`, cleans up partial resources, and sends a `command_result` with `status: "cancelled"`.
4. If no running task is found for the `command_id`, the cancel is silently ignored (the command may have already completed).

### Supported Commands and Their Executors

| Command | Executor | Agent Module(s) | Notes |
|---------|----------|----------------|-------|
| `deploy_model` | `_execute_deploy` | `model_downloader.py` → `docker_manager.py` → `vllm_manager.py` | Full lifecycle: download, create container, start vLLM, health check |
| `stop_model` | `_execute_stop` | `docker_manager.py` | SIGTERM → wait → SIGKILL if needed |
| `restart_model` | `_execute_restart` | `docker_manager.py` | `docker restart`, then health check |
| `download_model` | `_execute_download` | `model_downloader.py` | HF Hub download only, no deployment |
| `run_benchmark` | `_execute_benchmark` | `benchmark/runner.py` | Run benchmark against local vLLM endpoint |

### Agent-Side State Files

To survive agent restarts, the agent writes a state file per running command to `/tmp/modelprism/commands/`:
```json
{
  "command_id": "a1b2c3d4-...",
  "command": "deploy_model",
  "started_at": "2026-06-07T12:00:00+00:00",
  "status": "running",
  "docker_container_id": "abc123"
}
```
On agent restart, the startup sequence reads these files and either cleans up orphaned containers (if the command is incomplete) or leaves running containers intact (if the command completed but the result wasn't delivered). State files are deleted when the command reaches a terminal status.

### Integration Points

- **F7 (Agent WebSocket handler):** Provides the transport layer. F7 establishes the WebSocket connection, handles heartbeats, and detects disconnection. F11 builds on top by defining the command message types that flow over the established connection. F7's `on_message` dispatcher routes incoming messages by `type` field — `"command_progress"` and `"command_result"` are routed to the command tracker; the agent-side F7 client dispatches incoming `"command"` and `"cancel_command"` messages to the `CommandHandler`.

- **F9 (Agent metric push):** Metrics and commands share the same WebSocket but are independent message types. Metric pushes (`"metrics"`, `"vllm_metrics"`) continue uninterrupted during command execution. The command handler does not block the metrics push cycle.

- **F15/F16 (Dashboard WebSocket broadcast):** Progress messages and terminal results received by the backend are relayed to any frontend WebSocket connections subscribed to that agent. The relay envelope adds the `agent_id` field so the frontend can route it to the correct agent dashboard.

- **F20 (Docker-based model deployment) and F21 (Model download):** These are the agent-side execution modules that F11 calls when executing `deploy_model`, `stop_model`, `restart_model`, and `download_model` commands. F11 is the orchestrator; F20/F21 are the workers. The command handler does not duplicate their logic — it delegates.

- **F22 (Running model management):** The backend routes `POST /api/models/{id}/stop`, `POST /api/models/{id}/restart`, and `DELETE /api/models/{id}` all use F11 to send commands to the agent. The backend route handler creates a command via the command tracker, sends it over the WebSocket, and returns a 202 Accepted response with the `command_id` in the response body so the frontend can subscribe to progress updates.

- **F24 (Benchmark runner):** `POST /api/benchmarks` uses F11 to send a `run_benchmark` command to the agent. The backend route handler creates a `benchmark_runs` row with `status: "pending"`, issues the command, and updates the row as progress and result messages arrive.

- **F19 (Model deployment wizard):** The frontend deploy wizard calls `POST /api/models/deploy` which internally uses F11. The wizard receives the `command_id` in the 202 response and opens a WebSocket subscription to stream progress to `DeploymentLogViewer.vue` and `GpuLoadingGraph.vue`.

### Error Handling

| Scenario | Backend Behavior | Agent Behavior |
|----------|-----------------|----------------|
| Agent offline | Reject with 409 `AGENT_OFFLINE` | N/A — command never sent |
| Unknown command type | Log warning; no message sent to agent | Return `"UNKNOWN_COMMAND"` error result |
| Invalid command params (Pydantic validation) | Catch at backend before sending; return 422 | Catch at agent before executing; send error result |
| Command execution throws unhandled exception | N/A (agent-side) | Catch in executor wrapper; send `"failed"` with `"INTERNAL_ERROR"` code and traceback in `details` |
| Docker daemon unavailable | N/A (agent-side) | Return `"DOCKER_DAEMON_ERROR"` with details |
| HuggingFace Hub authentication failure | N/A (agent-side) | Return `"HF_AUTH_ERROR"` with message indicating invalid or missing token |
| Insufficient disk space for model download | N/A (agent-side) | Return `"INSUFFICIENT_DISK"` with required/available bytes in `details` |
| Port conflict (port already in use) | N/A (agent-side) | Return `"PORT_CONFLICT"` with conflicting port number |
| Health check fails after deployment | N/A (agent-side) | Return `"HEALTH_CHECK_FAILED"` with endpoint URL and HTTP status/reason |
| Backend crashes mid-command | On restart, all in-flight commands are lost | Agent detects WS disconnect during reconnect; marks command as interrupted locally; cleans up partial work |
| Command cancelled by user | Sends `cancel_command` over WebSocket | Cancels running task; cleans up; sends cancelled result |

### Depends on: F7
