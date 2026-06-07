# F7: Agent WebSocket Handler

## Metadata
- **ID:** F7
- **Phase:** Foundation
- **Effort:** Medium
- **Dependencies:** F1, F6
- **Acceptance Criteria Count:** 6

## Description

The Agent WebSocket Handler is the persistent, bidirectional communication channel between each registered GPU server agent and the ModelPrism backend. After an agent completes registration via the two-phase REST flow (F6), it opens a single long-lived WebSocket connection to the backend at `/ws/agents/{agent_id}`. This connection becomes the primary data plane: the agent pushes high-frequency GPU metrics, vLLM per-instance telemetry, command progress updates, and heartbeat pings over this channel, while the backend sends deployment commands (deploy, stop, restart, benchmark) and configuration updates back to the agent.

The handler lives in `backend/app/ws/agent_ws.py` on the server side and in `modelprism-agent/modelprism_agent/connection.py` on the agent side. It uses a lightweight, type-discriminated JSON protocol (not JSON:API) to minimise overhead on the 2-second metric push cycle. The backend tracks connection state per agent, logs disconnections, transitions the agent's `status` column in PostgreSQL (F3) from `online` to `offline` on unexpected disconnect, and triggers reconnection logic in the agent. Redis pub/sub is used internally to fan out received metrics to WebSocket-connected dashboard browsers (F16), but the agent-backend channel itself is a direct, dedicated WebSocket connection — no intermediary.

## Concrete Examples (Specification by Example)

### Example 1: Successful Connection and Heartbeat Cycle
- **Input:** An agent with ID `ag_cyan_koala_42` has completed registration and received its `ws_url`: `wss://api.modelprism.io/ws/agents/ag_cyan_koala_42`. The agent opens a WebSocket connection to this URL with its agent token in the `Authorization` header: `Authorization: Bearer mp_dGhpcyBpcyBhIHRva2VuIGZvciBleGFtcGxl`.
- **Action:** The backend receives the upgrade request, validates the JWT-signed agent token against the `agents` table, checks that the agent ID in the URL matches the token's agent ID, accepts the connection, and sets `agent.status = 'online'` in PostgreSQL with `last_seen_at = NOW()`. The agent begins sending heartbeat messages every 15 seconds.
- **Expected Output:** The backend responds with HTTP 101 Switching Protocols. Every 15 seconds, the backend receives `{"type": "heartbeat", "ts": 1717094400, "agents_running": ["vllm:5", "vllm:6"]}` and updates `last_seen_at` in the database. If three consecutive heartbeats (45s) are missed, the backend marks the agent `offline`.

### Example 2: Agent Pushes GPU Metrics Every 2 Seconds
- **Input:** Agent `ag_cyan_koala_42` is connected and has 4× NVIDIA A100 GPUs running one vLLM instance serving `Qwen2.5-72B-Instruct`.
- **Action:** Every 2 seconds, the agent collects GPU metrics from `nvidia-smi`, system metrics from `psutil`, and vLLM metrics from the local Prometheus endpoint. It sends the following JSON over the WebSocket:
  ```json
  {
    "type": "metrics",
    "ts": 1717094402,
    "gpu": [
      {
        "index": 0,
        "util_pct": 87,
        "mem_used_mb": 42100,
        "mem_total_mb": 81200,
        "temp_c": 72,
        "power_w": 285
      },
      {
        "index": 1,
        "util_pct": 92,
        "mem_used_mb": 67200,
        "mem_total_mb": 81200,
        "temp_c": 74,
        "power_w": 295
      },
      {
        "index": 2,
        "util_pct": 5,
        "mem_used_mb": 800,
        "mem_total_mb": 81200,
        "temp_c": 38,
        "power_w": 45
      },
      {
        "index": 3,
        "util_pct": 3,
        "mem_used_mb": 600,
        "mem_total_mb": 81200,
        "temp_c": 37,
        "power_w": 42
      }
    ],
    "gpu_cache_pct": 62.5,
    "ram_used_gb": 128,
    "ram_total_gb": 512,
    "cpu_pct": 12.5,
    "load_1": 8.2,
    "load_5": 7.1,
    "load_15": 6.5,
    "disk_used_gb": 548,
    "disk_total_gb": 2048,
    "disk_pct": 26.8
  }
  ```
- **Action:** The backend receives the message, validates the `type` field and required fields (GPU utilization, memory), writes the full snapshot to the `agent_metrics` table (F3) with `agent_id = 'ag_cyan_koala_42'`, `workspace_id` (resolved from the agent record), `ts`, and `data` (the full payload as JSONB). The backend then publishes the metric snapshot to a Redis channel for dashboard broadcast (F16).
- **Expected Output:** A row is inserted into `agent_metrics` every 2 seconds with the complete snapshot. The dashboard WebSocket (F16) receives the same payload within 50ms of the row insertion for real-time chart updates.

### Example 3: Backend Sends a Deploy Command, Agent Reports Progress, Agent Reports Result
- **Input:** A user deploys `Qwen/Qwen2.5-72B-Instruct` on agent `ag_cyan_koala_42` through the frontend. The backend sends the command over the agent's WebSocket.
- **Action (Backend → Agent):**
  ```json
  {
    "type": "command",
    "command_id": "cmd_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "command": "deploy_model",
    "params": {
      "model_id": "Qwen/Qwen2.5-72B-Instruct",
      "huggingface_token": "hf_abc123...",
      "vllm_params": {
        "tensor_parallel_size": 4,
        "quantization": "fp8",
        "max_model_len": 32768,
        "gpu_memory_utilization": 0.9,
        "port": 8001,
        "served_model_name": "qwen2.5-72b"
      }
    }
  }
  ```
- **Action (Agent → Backend — progress):** The agent acknowledges the command and begins downloading. Every few seconds it sends:
  ```json
  {
    "type": "command_progress",
    "command_id": "cmd_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "status": "downloading",
    "progress_pct": 45,
    "message": "Downloading model weights... (2.4 GB / 5.3 GB)"
  }
  ```
  Then:
  ```json
  {
    "type": "command_progress",
    "command_id": "cmd_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "status": "starting",
    "progress_pct": 85,
    "message": "Starting vLLM server on port 8001..."
  }
  ```
- **Action (Agent → Backend — result):** Once healthy, the agent sends:
  ```json
  {
    "type": "command_result",
    "command_id": "cmd_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "status": "success",
    "result": {
      "instance_id": "inst_qwen_001",
      "port": 8001,
      "pid": 12345,
      "endpoint": "http://localhost:8001/v1"
    }
  }
  ```
- **Expected Output:** The backend receives the command_progress messages and broadcasts the deployment log via the dashboard WebSocket (F16). On receiving `command_result`, the backend creates a `model_deployments` row (F3) with `status = 'healthy'`, stores the `instance_id`, port, and PID, and responds to the frontend. If the command fails, the agent sends `{"type": "command_result", "command_id": "...", "status": "failed", "error": "OOM: insufficient GPU memory for 4x tensor_parallel with fp8"}` and the backend marks the deployment as `failed`.

### Example 4: vLLM Metrics Push from Agent to Backend
- **Input:** Agent `ag_cyan_koala_42` has a healthy vLLM instance with ID `inst_qwen_001` serving `Qwen2.5-72B-Instruct`.
- **Action:** The agent parses vLLM's Prometheus `/metrics` endpoint and sends:
  ```json
  {
    "type": "vllm_metrics",
    "instance_id": "inst_qwen_001",
    "ts": 1717094402,
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
    "server_start_ts": 1716800000
  }
  ```
- **Expected Output:** The backend receives the vLLM metrics and merges them into the next `agent_metrics` row (the `data` JSONB column includes both GPU/system metrics and vLLM instance metrics). The dashboard receives the combined snapshot for display in QueueDiagnostics.vue and GpuMetricsChart.vue (F15).

### Example 5: Unexpected Disconnection and Reconnection
- **Input:** Agent `ag_cyan_koala_42` has been connected for 6 hours. The agent process crashes (e.g., OOM kill) and the WebSocket connection drops without a close frame.
- **Action:** The backend detects the TCP disconnection (the `websockets` library raises a `ConnectionClosed` exception in the receive loop). The `agent_ws.py` handler catches the exception, logs `{"level": "WARNING", "module": "agent_ws", "agent_id": "ag_cyan_koala_42", "message": "Agent disconnected unexpectedly"}`, sets `agent.status = 'offline'` and `agent.last_seen_at = NOW()` in PostgreSQL, and cleans up all in-flight command state (marks any pending commands as `failed` with reason `agent_disconnected`).
- **Action (Agent side):** The agent's `connection.py` detects the dropped connection, enters a backoff reconnect loop: wait 1s, retry; wait 2s, retry; wait 4s, retry; up to a maximum of 60s between retries. On the third attempt, the agent process restarts and reconnects.
- **Expected Output:** The agent's `status` in the `agents` table transitions to `offline` within 5 seconds of the disconnect. The dashboard shows the agent as offline (F14). On reconnect, the status transitions back to `online` and the dashboard updates within the next heartbeat cycle.

## Acceptance Criteria

- **ACF7-1: Connection establishment validates agent token and agent ID** — When an agent opens a WebSocket connection to `/ws/agents/{agent_id}`, the backend MUST validate the `Authorization: Bearer mp_...` token against the `agents` table using the same JWT verification used by REST endpoints (F5). The `agent_id` in the URL path MUST match the agent ID encoded in the token. If the token is missing, expired, invalid, or the agent ID mismatch, the backend MUST reject the upgrade with HTTP 401 and a JSON error body `{"error": "unauthorized", "detail": "Invalid or expired agent token"}`. No WebSocket frames are exchanged on a rejected connection.

- **ACF7-2: Heartbeat protocol keeps the connection alive and tracks agent liveness** — The agent MUST send a heartbeat message (`{"type": "heartbeat", "ts": <unix_epoch_seconds>, "agents_running": [...]}`) every 15 seconds after connection is established. The backend MUST respond to each heartbeat (any message, including echo/pong) to keep the connection alive. The backend MUST update `agents.last_seen_at` on each received heartbeat. If three consecutive heartbeats are missed (45s without a message), the backend MUST set `agent.status = 'offline'` and `agent.last_seen_at` to the timestamp of the last received message. On the next successful heartbeat, `agent.status` transitions back to `'online'`.

- **ACF7-3: Metric messages are validated, stored, and broadcast —** When the backend receives a `metrics` type message on the agent WebSocket, it MUST validate that `ts`, `gpu` (array with at least one element), `gpu[].util_pct`, `gpu[].mem_used_mb`, and `gpu[].mem_total_mb` are present and within reasonable ranges (util_pct 0–100, temperatures 0–120, power_w >= 0). Invalid messages MUST be logged as warnings and silently dropped (no error sent back to the agent — avoid disconnecting the agent for malformed data). Valid messages MUST be inserted as a row in `agent_metrics` with the full payload in the `data` JSONB column, and the payload MUST be published to the Redis channel `metrics:{agent_id}` for dashboard broadcast (F16). The round-trip from message receipt to Redis publish MUST complete in under 100ms on an unloaded system.

- **ACF7-4: Command messages from backend to agent are delivered reliably —** When the backend sends a command message to the agent (`{"type": "command", "command_id": "<uuid>", "command": "...", "params": {...}}`), the backend MUST track the command as `pending` in an in-memory map (keyed by `command_id`) and await a `command_result` or `command_progress` response. If the agent disconnects before sending a `command_result`, all pending commands MUST be marked as `failed` with reason `agent_disconnected`. The agent MUST respond with `command_progress` messages during execution and exactly one terminal `command_result` per `command_id`. Duplicate `command_id` values MUST be rejected by the agent with a `command_result` status `rejected` and error `"Duplicate command ID"`.

- **ACF7-5: Disconnect cleanup transitions agent state and releases resources —** When an agent WebSocket disconnects (clean close frame, TCP drop, or timeout) the backend MUST:
  1. Remove the agent's connection handle from the in-memory connection registry.
  2. Log the disconnection with agent ID, duration of the connection in seconds, and reason (if available from the close frame).
  3. Set `agent.status = 'offline'` in PostgreSQL and update `last_seen_at`.
  4. Cancel any pending in-flight commands stored for this agent.
  5. Publish a `{"type": "agent_disconnected", "agent_id": "<uuid>", "ts": "<iso8601>"}` message to the Redis channel `agent_events:{workspace_id}` so the dashboard (F16) can update the UI in real time.
  6. NOT delete the agent record or any associated data (metrics, logs, deployments persist).

- **ACF7-6: The connection handler supports graceful shutdown without dropping active agents —** On backend SIGTERM or SIGINT (shutdown initiated by F1's lifespan handler), the WebSocket server MUST send a `{"type": "shutdown", "reason": "server_restart", "reconnect_delay_seconds": 10}` message to every connected agent. Agents MUST receive this message, close the WebSocket cleanly, and enter the reconnect loop with the specified delay. The backend MUST wait up to 10 seconds for all agents to acknowledge the shutdown frame before closing the server socket. Agents that fail to respond within the 10-second window are disconnected forcefully and will reconnect on the same delay schedule when the server comes back up.

## Technical Notes

### File Paths
- **Backend WebSocket handler:** `backend/app/ws/agent_ws.py` — Handles connection upgrade, message routing, disconnect cleanup, and graceful shutdown signalling.
- **Backend WebSocket manager:** `backend/app/services/agent_manager.py` — Contains the connection registry (in-memory `dict[str, WebSocket]` keyed by agent_id), pending-command tracking, and the Redis pub/sub bridge.
- **Agent-side WebSocket client:** `modelprism-agent/modelprism_agent/connection.py` — Implements connect, heartbeat loop (15s), metric push loop (2s), command receiver, and exponential-backoff reconnection.
- **Shared schemas (model definitions):** `common/modelprism_common/schemas/events.py` — Pydantic models for all message types (`MetricsMessage`, `VllmMetricsMessage`, `HeartbeatMessage`, `CommandMessage`, `CommandProgressMessage`, `CommandResultMessage`, `ShutdownMessage`).

### WebSocket Message Protocol (Lightweight JSON)

All messages are flat JSON objects with a `type` discriminator field, **not** JSON:API format.

| `type` | Direction | Description |
|--------|-----------|-------------|
| `heartbeat` | Agent → Backend | 15s keep-alive with running instances list |
| `metrics` | Agent → Backend | Full GPU + system metrics snapshot (every 2s) |
| `vllm_metrics` | Agent → Backend | Per-instance vLLM metrics (every 2s, interleaved with `metrics`) |
| `command` | Backend → Agent | Deploy, stop, restart, benchmark command |
| `command_progress` | Agent → Backend | Progress update with percentage and message |
| `command_result` | Agent → Backend | Terminal result (success or failure) |
| `shutdown` | Backend → Agent | Graceful server shutdown notification |

### Connection State Machine

```
 CONNECTING ──(auth success)──> ONLINE
     │                              │
     │ (auth fail)                  │ heartbeat timeout (45s)
     v                              v
  REJECTED                      OFFLINE
     ^                              │
     │                              │ reconnect
     └──────────────────────────────┘
```

### Connection Registry

The `agent_manager.py` service maintains a thread-safe, in-memory registry:

```python
# backend/app/services/agent_manager.py

class AgentConnectionRegistry:
    """Thread-safe registry of active agent WebSocket connections."""

    def __init__(self):
        self._connections: dict[uuid.UUID, WebSocket] = {}
        self._pending_commands: dict[uuid.UUID, dict[str, PendingCommand]] = {}
        self._lock = asyncio.Lock()

    async def register(self, agent_id: uuid.UUID, ws: WebSocket) -> None:
        async with self._lock:
            old_ws = self._connections.get(agent_id)
            if old_ws is not None:
                # Force-close any previous connection (duplicate/stale session)
                await old_ws.close(code=1008, reason="Replaced by new connection")
            self._connections[agent_id] = ws
            self._pending_commands.setdefault(agent_id, {})

    async def unregister(self, agent_id: uuid.UUID) -> None:
        async with self._lock:
            self._connections.pop(agent_id, None)
            pending = self._pending_commands.pop(agent_id, {})
        # Return pending commands for failure marking
        return pending

    async def send_command(self, agent_id: uuid.UUID, command: CommandMessage) -> bool:
        async with self._lock:
            ws = self._connections.get(agent_id)
            if ws is None:
                return False
            self._pending_commands[agent_id][command.command_id] = PendingCommand(
                command_id=command.command_id,
                command=command.command,
                sent_at=datetime.now(timezone.utc),
            )
            await ws.send_json(command.model_dump())
            return True

    def get_online_count(self) -> int:
        return len(self._connections)
```

### Graceful Shutdown Integration with F1

The lifespan handler in `backend/app/main.py` (F1) should call the WebSocket manager's shutdown method:

```python
# Pseudocode in F1's lifespan handler
from app.services.agent_manager import agent_registry

async def lifespan(app):
    # Startup...
    yield
    # Shutdown: notify all agents
    await agent_registry.broadcast_shutdown(reconnect_delay_seconds=10)
    await asyncio.sleep(10)  # Wait for acknowledgements
    # Close database, Redis, etc.
```

### Backend Dependencies

- FastAPI `WebSocket` and `WebSocketDisconnect` from `fastapi`.
- `redis.asyncio.Redis` for publishing metric snapshots to `metrics:{agent_id}` channel (F16 subscribes to this).
- SQLAlchemy `AsyncSession` for writing `agent_metrics` rows and updating `agents.status` (F3).
- JWT decode from `backend/app/middleware/auth.py` (F5) for validating the agent token in the `Authorization` header.
- Agent token format: `mp_<base64url-encoded-JWT>` where the JWT payload contains `{ "type": "agent", "agent_id": "<uuid>", "workspace_id": "<uuid>", "exp": <timestamp> }`.

### Agent-Side WebSocket Client (`connection.py`)

```python
# Pseudocode for modelprism-agent/modelprism_agent/connection.py

class AgentWebSocket:
    BASE_DELAY = 1.0       # seconds
    MAX_DELAY = 60.0        # seconds
    BACKOFF_MULTIPLIER = 2.0
    HEARTBEAT_INTERVAL = 15  # seconds
    METRICS_INTERVAL = 2     # seconds

    async def run(self, ws_url: str, token: str):
        delay = self.BASE_DELAY
        while not self._stopped:
            try:
                async with websockets.connect(
                    ws_url,
                    extra_headers={"Authorization": f"Bearer {token}"},
                    ping_interval=10,          # websockets library ping to detect drop
                    ping_timeout=5,
                ) as ws:
                    delay = self.BASE_DELAY   # Reset backoff on successful connect
                    await self._handle_connection(ws)
            except (websockets.ConnectionClosed, OSError) as e:
                logger.warning("Connection lost, reconnecting in %.1fs", delay)
                await asyncio.sleep(delay)
                delay = min(delay * self.BACKOFF_MULTIPLIER, self.MAX_DELAY)

    async def _handle_connection(self, ws):
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(ws))
        metrics_task = asyncio.create_task(self._metrics_loop(ws))
        receiver_task = asyncio.create_task(self._receive_loop(ws))
        done, pending = await asyncio.wait(
            [heartbeat_task, metrics_task, receiver_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()

    async def _receive_loop(self, ws):
        async for raw in ws:
            msg = json.loads(raw)
            if msg["type"] == "command":
                await self.command_handler.handle(msg)
            elif msg["type"] == "shutdown":
                logger.info("Server shutting down, reconnecting in %ds", msg["reconnect_delay_seconds"])
                return  # Exit _handle_connection to trigger reconnect
```

### Edge Cases

- **Duplicate connection:** If an agent connects while a previous connection from the same agent_id is still active (e.g., zombie process), the old connection is force-closed with code 1008 ("Replaced by new connection") and the new one is accepted. The in-flight commands of the old connection are marked as failed.
- **Malformed metric payload:** The backend drops malformed metric messages silently (logs a warning) rather than closing the connection. This prevents a buggy agent from disrupting the control plane.
- **High message rate:** At 1000 agents each pushing metrics every 2 seconds, the backend processes 500 messages/second. The `agent_ws.py` handler must use `asyncio.create_task` to offload the database write and Redis publish so the receive loop is not blocked. A bounded `asyncio.Queue` (max 10,000 items) serves as a buffer between the receive loop and the write tasks. If the queue fills up, older metric messages are dropped (newer metrics are more valuable).
- **Agent reconnection after server restart:** When the server sends `shutdown` and restarts, all agents reconnect within the specified delay plus jitter (±1s). The agent manager must handle a thundering-herd of reconnections gracefully — the `register` method acquires the lock per agent_id, so concurrent reconnections from different agents are non-blocking.
- **Clock skew:** `ts` in metric and heartbeat messages is the agent's local Unix timestamp. The backend uses `NOW()` for its own `last_seen_at` and `created_at` columns. If `ts` is more than 5 minutes in the future or past, the backend logs a warning and uses its own timestamp for the database row. This prevents a misconfigured agent clock from corrupting time-series data.

### Metrics

- **Connection time:** Target < 100ms for full WebSocket handshake + auth validation from the agent's perspective.
- **Message processing latency:** P50 < 10ms, P99 < 50ms from message receipt to Redis publish.
- **Disconnect detection:** > 99% of unexpected disconnects detected within 60 seconds.
- **Reconnection success:** > 99.9% of reconnect attempts succeed on the first try when the backend is healthy.

## Depends on: F1 (Backend scaffolding, lifespan, async engine), F6 (Agent registration, token format, agent record in database)
