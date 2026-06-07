# F16: WebSocket Broadcast

## Metadata
- **ID:** F16
- **Phase:** MVP
- **Effort:** Medium
- **Dependencies:** F7, F10, F12
- **Acceptance Criteria Count:** 6

## Description

The WebSocket Broadcast layer is the real-time data distribution backbone of the ModelPrism dashboard. While the agent-to-backend WebSocket channels (F7) are dedicated, direct connections — one per GPU server — the broadcast layer takes the opposite approach: a single, multi-tenant WebSocket endpoint at `/ws/workspaces/{workspace_id}` that fans out live telemetry from hundreds of agents to authenticated browser clients. Every dashboard user who opens a GPU server view, a deployment progress panel, or the workspace overview establishes one persistent WebSocket connection to this endpoint. From that single connection they receive a multiplexed stream of metric snapshots (F10), log entries (F12), agent status transitions, and deployment command progress — all keyed by `agent_id` so client-side composables can route each message to the correct Pinia store and Vue component.

Architecturally, the broadcast layer is a pure fan-out bridge with no persistence and minimal business logic. It subscribes to four Redis pub/sub channels that other backend services publish to:

| Redis Channel | Publisher | Payload Type | Description |
|---|---|---|---|
| `metrics:{agent_id}` | F10 (metric ingestion) | Raw metric snapshot | GPU/system/vLLM metrics every 2s per agent |
| `logs:{agent_id}` | F12 (log streaming) | Structured log entry | Individual log entries as they arrive from agents |
| `agent_events:{workspace_id}` | F7 (agent WebSocket handler) | Agent status event | `online`, `offline`, `disconnected` transitions |
| `command_events:{workspace_id}` | F11 (agent command handler) | Command progress/result | Deployment and benchmark command status updates |

The FastAPI WebSocket endpoint at `backend/app/ws/dashboard_ws.py` authenticates the user via a JWT token passed as a query parameter (`?token=...`) and resolves their `workspace_id` from the token payload. On successful auth, the handler subscribes to the four Redis channel groups for that workspace and enters a receive-send loop that reads from Redis and writes to the dashboard WebSocket. There is no per-client state — the broadcast is strictly one-to-many from Redis to all connected browsers in the same workspace. This keeps the handler stateless and horizontally scalable: multiple backend instances can each maintain their own set of dashboard WebSocket connections while all receiving the same Redis broadcasts.

On the frontend, a new composable `useDashboardWebSocket` in `app/composables/useDashboardWebSocket.ts` manages the full lifecycle: connection, automatic reconnection with exponential backoff (1s → 30s max), message routing by `type` discriminator, and cleanup on component unmount. Each message carries an `agent_id` and a `type` field so the composable can dispatch to the correct Pinia store — `useAgentMetricsStore` receives `metrics` messages, `useAgentLogsStore` receives `log_entry` messages, `useAgentStore` receives `agent_status` messages, and `useCommandStore` receives `command_progress` and `command_result` messages. If the WebSocket disconnects (network interruption, server restart), the composable buffers up to 500 incoming messages in memory during the reconnect window, replays them in order once the connection is restored, and then transitions to live streaming. This prevents transient disconnections from causing visible gaps in the real-time dashboard.

## Concrete Examples (Specification by Example)

### Example 1: Dashboard Client Receives Metrics Snapshots for Two Agents

- **Input:** A user opens the workspace overview page that shows live GPU utilization for all agents in workspace `ws_abc`. The frontend connects to `wss://api.modelprism.io/ws/workspaces/ws_abc?token=eyJhbGciOiJIUzI1NiIs...`. Two agents in the workspace (`ag_cyan_koala_42` and `ag_red_panda_17`) are both pushing metrics every 2 seconds.

- **Action:** The backend's `dashboard_ws.py` authenticates the user's JWT token, resolves `workspace_id = ws_abc`, and subscribes to all four Redis channel groups for that workspace. The F10 metric ingestion service publishes a snapshot to `metrics:ag_cyan_koala_42` and `metrics:ag_red_panda_17` every 2 seconds. The broadcast handler reads from Redis and forwards to the WebSocket. The `useDashboardWebSocket` composable receives the messages and dispatches `metrics` type messages to `useAgentMetricsStore`.

- **Expected Output:**

  **Dashboard Client receives over WebSocket:**
  ```json
  {
    "type": "metrics",
    "agent_id": "ag_cyan_koala_42",
    "ts": "2026-06-07T14:30:02.000+00:00",
    "gpu": [
      { "index": 0, "util_pct": 87, "mem_used_mb": 42100, "mem_total_mb": 81200, "temp_c": 72, "power_w": 285 },
      { "index": 1, "util_pct": 92, "mem_used_mb": 67200, "mem_total_mb": 81200, "temp_c": 74, "power_w": 295 }
    ],
    "gpu_cache_pct": 62.5,
    "ram_used_gb": 128,
    "ram_total_gb": 512,
    "cpu_pct": 12.5
  }
  ```

  **Two seconds later, another message for the second agent:**
  ```json
  {
    "type": "metrics",
    "agent_id": "ag_red_panda_17",
    "ts": "2026-06-07T14:30:04.000+00:00",
    "gpu": [
      { "index": 0, "util_pct": 34, "mem_used_mb": 28400, "mem_total_mb": 81200, "temp_c": 52, "power_w": 142 }
    ],
    "gpu_cache_pct": 41.2,
    "ram_used_gb": 64,
    "ram_total_gb": 256,
    "cpu_pct": 8.1
  }
  ```

  **Frontend state update:**
  `useAgentMetricsStore` receives both snapshots. The `GpuMetricsChart.vue` component for `ag_cyan_koala_42` updates its GPU utilization bar from 87% to 91% on the next tick. Each agent maintains its own time-series buffer of the last 300 snapshots (10 minutes at 2-second intervals) for the sparkline charts.

### Example 2: Dashboard Client Receives Live Log Entries

- **Input:** Agent `ag_cyan_koala_42` is deploying `Qwen/Qwen2.5-72B-Instruct` (triggered from F11 / F19). The agent sends log entries via the F12 HTTP pipeline. The F12 route handler persists each entry and publishes to Redis channel `logs:ag_cyan_koala_42`.

- **Action:** The broadcast handler receives the Redis publish and forwards the log entry to all WebSocket connections subscribed to workspace `ws_abc`. The `useDashboardWebSocket` composable routes the message to `useAgentLogsStore` by matching `type: "log_entry"`. The `LiveLog.vue` component appends the entry to its display buffer.

- **Expected Output:**

  **Dashboard Client receives:**
  ```json
  {
    "type": "log_entry",
    "agent_id": "ag_cyan_koala_42",
    "entry": {
      "id": "log_550e8400-e29b-41d4-a716-446655440000",
      "timestamp": "2026-06-07T14:31:15.230+00:00",
      "level": "info",
      "module": "downloader",
      "message": "Downloading Qwen2.5-72B-Instruct — shard 7/15 complete, 18.4 GB / 42.0 GB",
      "metadata": { "model_id": "Qwen/Qwen2.5-72B-Instruct", "shard": 7, "shards_total": 15 }
    }
  }
  ```

  **Frontend:**
  The log viewer in the per-agent dashboard (F15) renders a new row with a blue `[INFO]` badge, module tag `downloader`, and the message. If the user has selected a "warnings and errors only" filter, this `info` entry is filtered out client-side and never appended to the visible display buffer (though it remains in the composable's raw buffer for unfiltered export).

### Example 3: Agent Goes Offline — Status Transition Broadcast

- **Input:** Agent `ag_cyan_koala_42` has an unexpected disconnection (process crash). The F7 agent WebSocket handler detects the TCP drop, marks the agent as `offline` in PostgreSQL, and publishes a status event to Redis channel `agent_events:ws_abc`.

- **Action:** The broadcast handler receives the event and forwards it to all connected dashboard clients in workspace `ws_abc`. The composable dispatches to `useAgentStore`, which updates `agents[agent_id].status` from `"online"` to `"offline"` and sets `agents[agent_id].lastSeenAt` to the event timestamp.

- **Expected Output:**

  **Dashboard Client receives:**
  ```json
  {
    "type": "agent_status",
    "agent_id": "ag_cyan_koala_42",
    "status": "offline",
    "previous_status": "online",
    "ts": "2026-06-07T14:32:45.120+00:00",
    "reason": "connection_lost"
  }
  ```

  **Frontend:**
  The workspace overview page (F14) changes the agent's status badge from green "Online" to red "Offline" within 500ms. The per-agent dashboard (F15) shows a persistent banner: "Agent disconnected at 14:32:45 — auto-reconnect in progress". All metric charts for this agent freeze at their last values with a "disconnected" overlay. When the agent reconnects (F7 sends `agent_status` with `status: "online"`), the charts resume and the banner disappears.

### Example 4: Command Progress Broadcast During Deployment

- **Input:** A user starts a deployment of `mistralai/Mixtral-8x7B-Instruct-v0.1` on agent `ag_cyan_koala_42` via the deployment wizard (F19). The F11 command handler sends `{"type": "command", ...}` over the agent WebSocket and publishes progress updates to Redis channel `command_events:ws_abc`.

- **Action:** The broadcast handler forwards each `command_progress` and the terminal `command_result` to all dashboard clients. The `useDashboardWebSocket` composable dispatches to `useCommandStore`. The deployment wizard panel updates its progress bar and status text.

- **Expected Output:**

  **Dashboard Client receives progress:**
  ```json
  {
    "type": "command_progress",
    "agent_id": "ag_cyan_koala_42",
    "command_id": "cmd_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "command": "deploy_model",
    "status": "downloading",
    "progress_pct": 45,
    "message": "Downloading model weights... (2.4 GB / 5.3 GB)",
    "ts": "2026-06-07T14:33:10.000+00:00"
  }
  ```

  **Dashboard Client receives result:**
  ```json
  {
    "type": "command_result",
    "agent_id": "ag_cyan_koala_42",
    "command_id": "cmd_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "command": "deploy_model",
    "status": "success",
    "result": {
      "instance_id": "inst_mixtral_001",
      "port": 8001,
      "pid": 12345,
      "endpoint": "http://localhost:8001/v1",
      "model_name": "mistralai/Mixtral-8x7B-Instruct-v0.1"
    },
    "ts": "2026-06-07T14:35:42.000+00:00"
  }
  ```

  **Frontend:**
  The deployment wizard progress bar advances from 45% to 100% over the deployment duration. On `command_result`, the wizard transitions to the "Deployment Complete" screen showing the endpoint URL, port, and a "Test Connection" button. The `useAgentStore` adds the new `model_deployments` entry to the agent's deployment list — the overview sidebar now shows `Mixtral-8x7B-Instruct-v0.1` as running on agent `ag_cyan_koala_42` without requiring a page refresh.

### Example 5: Reconnection with Message Replay After Network Blip

- **Input:** A dashboard user's laptop experiences a 12-second WiFi dropout while viewing the workspace overview. During this window, 6 metric snapshots are broadcast for `ag_cyan_koala_42` (one every 2 seconds) and 4 log entries arrive.

- **Action:** The `useDashboardWebSocket` composable detects the close event with code 1006 (Abnormal Closure). It enters the reconnection loop with a 1-second initial delay and activates the in-memory buffer (capacity 500 messages). On the first reconnect attempt (1s later), the connection succeeds. The composable sends a `{"type": "replay_request", "since": "2026-06-07T14:30:00.000+00:00"}` message to the server. The server queries the last 60 seconds of recent events from the `replay_buffer` in Redis (a capped list per workspace, TTL 120s, max 1000 entries) and sends them as a batch replay. The composable processes the replay in order, adds the entries to the respective stores, then transitions to live streaming.

- **Expected Output:**

  **Client sends on reconnect:**
  ```json
  {
    "type": "replay_request",
    "since": "2026-06-07T14:30:00.000+00:00"
  }
  ```

  **Server responds with replay batch:**
  ```json
  {
    "type": "replay_batch",
    "entries": [
      { "type": "metrics", "agent_id": "ag_cyan_koala_42", "ts": "2026-06-07T14:30:02.000+00:00", "gpu": [...] },
      { "type": "metrics", "agent_id": "ag_cyan_koala_42", "ts": "2026-06-07T14:30:04.000+00:00", "gpu": [...] },
      { "type": "log_entry", "agent_id": "ag_cyan_koala_42", "entry": {...} },
      "... (8 more entries) ..."
    ],
    "count": 10
  }
  ```

  **Frontend:**
  The metric sparklines show a continuous line across the 12-second gap — the replayed data fills in the missing window. Log entries during the gap appear in the log viewer in correct chronological order. The user sees no visible discontinuity beyond a brief "Reconnecting..." indicator that disappears within 2 seconds.

## Acceptance Criteria

- **ACF16-1: WebSocket endpoint authenticates via JWT query parameter and validates workspace membership** — When a dashboard client opens a WebSocket connection to `/ws/workspaces/{workspace_id}?token=<jwt>`, the backend MUST decode and validate the JWT using the same secret and algorithm as the REST auth middleware (F5). The backend MUST extract the `workspace_id` and `user_id` from the token payload. If the token is missing, expired, or malformed, the backend MUST reject the upgrade with HTTP 401. If the token's `workspace_id` does not match the workspace in the URL path, the backend MUST reject with HTTP 403. On successful auth, the backend MUST accept the upgrade (101 Switching Protocols) and immediately subscribe to the four Redis channel groups for that workspace: `metrics:*` (filtered to agents in the workspace via a Redis set `workspace_agents:{workspace_id}`), `logs:*`, `agent_events:{workspace_id}`, and `command_events:{workspace_id}`.

- **ACF16-2: The fan-out handler publishes every Redis message on subscribed channels to all connected clients within 100ms** — When any backend service publishes a message to a Redis channel that the broadcast handler is subscribed to, the handler MUST forward that message to every authenticated WebSocket connection in the same workspace within 100 milliseconds (measured from Redis PUBLISH to WebSocket `send_json()` call). The forwarded message MUST include the `type` discriminator and `agent_id` fields at the top level. The handler MUST NOT buffer, batch, or filter messages — every publish is forwarded to every connection in the workspace. Under load of 500 messages/second across 100 concurrent dashboard connections (50,000 forwards/second), the handler MUST sustain forwarding without accumulating more than 1 second of latency. If the outbound WebSocket send buffer for a particular client exceeds 1 MB, the handler MUST close that connection with code 1009 (Message Too Large) to prevent memory exhaustion.

- **ACF16-3: The frontend `useDashboardWebSocket` composable implements full lifecycle management with automatic reconnect and message replay** — The composable MUST connect on component mount (or explicit `connect()` call) and disconnect on component unmount or explicit `disconnect()`. On unexpected disconnection (any close code other than 1000), the composable MUST enter a reconnection loop with exponential backoff: 1s, 2s, 4s, 8s, up to a maximum of 30 seconds between attempts. On successful reconnect, the composable MUST send a `replay_request` message with a `since` timestamp set to the `last_received_at` timestamp tracked locally. The composable MUST buffer incoming messages during the live streaming phase in a ring buffer of at most 500 entries (keyed by `type` + `agent_id` + server-side sequence number) to support replay on reconnect. If the composable has not received any message for 60 seconds while the WebSocket is open, it MUST send a `{"type": "ping"}` keepalive and expect a `{"type": "pong"}` response within 5 seconds — if the pong does not arrive, the composable MUST close the connection and enter the reconnection loop.

- **ACF16-4: The backend replay buffer stores recent events in Redis and serves replay requests —** The broadcast handler MUST maintain a Redis capped list per workspace named `replay_buffer:{workspace_id}` with a maximum of 1000 entries and a TTL of 120 seconds. Every message forwarded to dashboard clients MUST also be appended to this replay buffer (lpush + ltrim). When the handler receives a `replay_request` message from a client, it MUST query the replay buffer for entries with `ts >= since`, limit the result to 500 entries, and send them as a single `replay_batch` message. The replay batch MUST preserve chronological order (oldest first). If `since` is older than 120 seconds or there are no matching entries, the handler MUST return a `replay_batch` with an empty `entries` array. The replay buffer MUST NOT block the live forwarding path — Redis writes to the replay buffer MUST be fire-and-forget with no await on the result.

- **ACF16-5: Messages are dispatched to the correct Pinia store via a type-based router —** The `useDashboardWebSocket` composable MUST maintain a type-to-store dispatch map that routes each incoming message to the appropriate store action. The required mappings are:
  - `type: "metrics"` → `useAgentMetricsStore().ingestSnapshot(message)`
  - `type: "log_entry"` → `useAgentLogsStore().appendEntry(message.agent_id, message.entry)`
  - `type: "agent_status"` → `useAgentStore().updateAgentStatus(message.agent_id, message.status, message.ts)`
  - `type: "command_progress"` → `useCommandStore().updateProgress(message.command_id, message)`
  - `type: "command_result"` → `useCommandStore().setResult(message.command_id, message)`
  - `type: "replay_batch"` → iterate entries and recursively dispatch each via the same type router

  If a message arrives with an unrecognized `type`, the composable MUST log a warning to console and silently drop the message. Each store action MUST be implemented as a synchronous state mutation (not async) — the Pinia stores should update their state within a single Vue tick to avoid visual jank in chart components that reactively bind to the store data.

- **ACF16-6: The broadcast handler supports graceful shutdown without dropping active dashboard connections —** When the backend receives SIGTERM (F1 lifespan shutdown), the broadcast handler MUST send a `{"type": "shutdown_notice", "reason": "server_restart", "reconnect_delay_ms": 2000}` message to every connected dashboard WebSocket. The frontend composable, upon receiving `type: "shutdown_notice"`, MUST close the WebSocket cleanly with code 1001 (Going Away) and enter the reconnection loop with the specified delay (2 seconds). During the restart window, the composable continues to buffer messages in memory (up to 500 entries). On reconnect after the backend comes back up, the composable sends a `replay_request` with `since` set to the timestamp of the last message received before the shutdown notice, ensuring no messages are lost across a rolling restart. The backend MUST NOT force-close dashboard connections — it must send the shutdown notice and wait up to 5 seconds for clients to close cleanly before closing the server-side socket.

## Technical Notes

### File Paths

- **Backend WebSocket broadcast handler:** `backend/app/ws/dashboard_ws.py` — Authenticates dashboard clients via JWT query param, subscribes to Redis pub/sub per workspace, and forwards messages to all connected browsers.
- **Backend Redis pub/sub manager:** `backend/app/services/broadcast_service.py` — Manages Redis subscription lifecycle, maintains the per-workspace replay buffer (capped Redis list), and provides a `publish_to_workspace(channel, payload)` helper for other services (F10, F12, F11, F7) to publish events.
- **Backend dependency injection for broadcast service:** `backend/app/dependencies.py` — Provides the `broadcast_service` dependency to route handlers and WebSocket endpoints.
- **Frontend composable:** `app/composables/useDashboardWebSocket.ts` — Manages WebSocket lifecycle, reconnection with backoff, message dispatch to Pinia stores, and replay buffer coordination.
- **Frontend stores (dispatched to):**
  - `app/stores/agentMetricsStore.ts` — Receives `metrics` messages
  - `app/stores/agentLogsStore.ts` — Receives `log_entry` messages
  - `app/stores/agentStore.ts` — Receives `agent_status` messages
  - `app/stores/commandStore.ts` — Receives `command_progress` and `command_result` messages
- **Frontend configuration:** `app/config/ws.ts` — Base URL for WebSocket (`wss://api.modelprism.io/ws`), reconnection backoff parameters (`BASE_DELAY = 1000`, `MAX_DELAY = 30000`, `MULTIPLIER = 2.0`), keepalive interval (`KEEPALIVE_MS = 60000`), and replay buffer max size (`REPLAY_BUFFER_MAX = 500`).

### Redis Channel Convention

All Redis channels use the following naming conventions:

| Channel Pattern | Example | Publisher | Consumer |
|---|---|---|---|
| `metrics:{agent_id}` | `metrics:ag_cyan_koala_42` | F10 metric ingestion | Broadcast handler |
| `logs:{agent_id}` | `logs:ag_cyan_koala_42` | F12 log streamer | Broadcast handler |
| `agent_events:{workspace_id}` | `agent_events:ws_abc` | F7 agent WS handler | Broadcast handler |
| `command_events:{workspace_id}` | `command_events:ws_abc` | F11 command handler | Broadcast handler |
| `replay_buffer:{workspace_id}` | `replay_buffer:ws_abc` | Broadcast handler (writer) | Broadcast handler (reader on replay) |

The broadcast handler subscribes to `metrics:*` and `logs:*` with a Redis `PSUBSCRIBE` pattern, but filters messages to only those agents that belong to the connected workspace. Agent-to-workspace membership is resolved from a Redis set `workspace_agents:{workspace_id}` that is populated by the agent registration flow (F6) and updated by the F7 connection handler on connect/disconnect.

### Frontend Composable Pseudocode

```typescript
// app/composables/useDashboardWebSocket.ts

import { ref, onUnmounted } from 'vue'
import { useAgentMetricsStore } from '~/stores/agentMetricsStore'
import { useAgentLogsStore } from '~/stores/agentLogsStore'
import { useAgentStore } from '~/stores/agentStore'
import { useCommandStore } from '~/stores/commandStore'

const WS_CONFIG = {
  BASE_DELAY: 1000,
  MAX_DELAY: 30000,
  BACKOFF_MULTIPLIER: 2.0,
  KEEPALIVE_MS: 60000,
  REPLAY_BUFFER_MAX: 500,
}

type WsMessage = Record<string, unknown> & { type: string; agent_id?: string }

export function useDashboardWebSocket(workspaceId: string) {
  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const lastReceivedAt = ref<string | null>(null)
  const messageBuffer = ref<WsMessage[]>([])
  let reconnectAttempt = 0
  let keepaliveTimer: ReturnType<typeof setInterval> | null = null

  const dispatchMap: Record<string, (msg: WsMessage) => void> = {
    metrics: (msg) => useAgentMetricsStore().ingestSnapshot(msg),
    log_entry: (msg) =>
      useAgentLogsStore().appendEntry(msg.agent_id!, msg.entry as any),
    agent_status: (msg) =>
      useAgentStore().updateAgentStatus(msg.agent_id as string, msg.status as string, msg.ts as string),
    command_progress: (msg) => useCommandStore().updateProgress(msg.command_id as string, msg),
    command_result: (msg) => useCommandStore().setResult(msg.command_id as string, msg),
    replay_batch: (msg) => {
      const entries = msg.entries as WsMessage[]
      for (const entry of entries) {
        const handler = dispatchMap[entry.type]
        if (handler) handler(entry)
      }
    },
    pong: () => { /* keepalive acknowledged — no action needed */ },
    shutdown_notice: (msg) => {
      // Close cleanly; reconnect loop handles reconnection
      ws.value?.close(1001, 'Server shutting down')
      // Override next delay from the server-provided value
      reconnectAttempt = 0
      const delay = (msg.reconnect_delay_ms as number) || WS_CONFIG.BASE_DELAY
      setTimeout(() => connect(), delay)
    },
  }

  function connect() {
    const token = localStorage.getItem('auth_token')
    const url = `${WS_BASE_URL}/workspaces/${workspaceId}?token=${token}`
    const socket = new WebSocket(url)

    socket.onopen = () => {
      isConnected.value = true
      reconnectAttempt = 0
      startKeepalive()
      // Request replay for any messages missed while disconnected
      if (lastReceivedAt.value) {
        socket.send(JSON.stringify({ type: 'replay_request', since: lastReceivedAt.value }))
      }
      // Flush any buffered messages (from before first connect)
      flushBuffer(socket)
    }

    socket.onmessage = (event) => {
      const msg: WsMessage = JSON.parse(event.data)
      lastReceivedAt.value = msg.ts as string || new Date().toISOString()
      const handler = dispatchMap[msg.type]
      if (handler) {
        handler(msg)
      } else {
        console.warn(`[useDashboardWS] Unknown message type: ${msg.type}`)
      }
    }

    socket.onclose = (event) => {
      isConnected.value = false
      stopKeepalive()
      ws.value = null
      if (event.code !== 1000) {
        scheduleReconnect()
      }
    }

    socket.onerror = () => {
      // onclose will fire after onerror — reconnect is handled there
      socket.close()
    }

    ws.value = socket
  }

  function scheduleReconnect() {
    const delay = Math.min(
      WS_CONFIG.BASE_DELAY * Math.pow(WS_CONFIG.BACKOFF_MULTIPLIER, reconnectAttempt),
      WS_CONFIG.MAX_DELAY
    )
    reconnectAttempt++
    setTimeout(() => connect(), delay)
  }

  function startKeepalive() {
    keepaliveTimer = setInterval(() => {
      if (ws.value?.readyState === WebSocket.OPEN) {
        ws.value.send(JSON.stringify({ type: 'ping' }))
      }
    }, WS_CONFIG.KEEPALIVE_MS)
  }

  function stopKeepalive() {
    if (keepaliveTimer) clearInterval(keepaliveTimer)
    keepaliveTimer = null
  }

  function flushBuffer(socket: WebSocket) {
    while (messageBuffer.value.length > 0) {
      const msg = messageBuffer.value.shift()!
      socket.send(JSON.stringify(msg))
    }
  }

  function disconnect() {
    stopKeepalive()
    ws.value?.close(1000, 'Client disconnect')
    ws.value = null
    isConnected.value = false
  }

  function send(msg: Record<string, unknown>) {
    if (ws.value?.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify(msg))
    } else {
      // Buffer messages for sending once connected
      if (messageBuffer.value.length < WS_CONFIG.REPLAY_BUFFER_MAX) {
        messageBuffer.value.push(msg as WsMessage)
      }
    }
  }

  onUnmounted(() => disconnect())

  return { connect, disconnect, send, isConnected, ws }
}
```

### Backend Broadcast Handler Pseudocode

```python
# backend/app/ws/dashboard_ws.py

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from redis.asyncio import Redis

from app.middleware.auth import decode_dashboard_token
from app.dependencies import get_redis

router = APIRouter()


@router.websocket("/ws/workspaces/{workspace_id}")
async def dashboard_ws(
    websocket: WebSocket,
    workspace_id: uuid.UUID,
    token: str = Query(...),
    redis: Redis = Depends(get_redis),
):
    """Fan-out broadcast endpoint for dashboard real-time updates."""

    # 1. Authenticate
    payload = decode_dashboard_token(token)
    if payload is None:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    token_workspace_id = uuid.UUID(payload.get("workspace_id"))
    if token_workspace_id != workspace_id:
        await websocket.close(code=4003, reason="Workspace mismatch")
        return

    await websocket.accept()

    # 2. Subscribe to Redis channels for this workspace
    pubsub = redis.pubsub()
    # Subscribe to agent-specific metric/log channels via pattern
    await pubsub.psubscribe(f"metrics:*")
    await pubsub.psubscribe(f"logs:*")
    # Subscribe to workspace-level event channels
    await pubsub.subscribe(
        f"agent_events:{workspace_id}",
        f"command_events:{workspace_id}",
    )

    # Resolve which agent IDs belong to this workspace for filtering
    workspace_agents: set[str] = await redis.smembers(f"workspace_agents:{workspace_id}")

    async def redis_reader():
        """Read from Redis pub/sub and forward to the WebSocket."""
        async for message in pubsub.listen():
            if message["type"] not in ("pmessage", "message"):
                continue

            channel: str = message["channel"]
            data: str = message["data"]

            # For agent-scoped channels (metrics:*, logs:*), check workspace membership
            if channel.startswith("metrics:") or channel.startswith("logs:"):
                agent_id = channel.split(":", 1)[1]
                if agent_id not in workspace_agents:
                    continue  # Skip agents not in this workspace

            # Forward to client
            try:
                await websocket.send_json(json.loads(data))
            except Exception:
                break  # Connection likely closed

    async def client_reader():
        """Read messages from the dashboard client (replay requests, pings)."""
        try:
            async for raw in websocket.iter_json():
                msg_type = raw.get("type")
                if msg_type == "replay_request":
                    await handle_replay(websocket, redis, workspace_id, raw.get("since"))
                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            pass

    # 3. Run both loops concurrently; exit if either finishes
    import asyncio
    await asyncio.wait(
        [asyncio.create_task(redis_reader()), asyncio.create_task(client_reader())],
        return_when=asyncio.FIRST_COMPLETED,
    )

    # 4. Cleanup
    await pubsub.punsubscribe()
    await pubsub.close()


async def handle_replay(
    websocket: WebSocket,
    redis: Redis,
    workspace_id: uuid.UUID,
    since: str | None,
):
    """Serve replay buffer entries for the workspace."""
    if not since:
        await websocket.send_json({"type": "replay_batch", "entries": [], "count": 0})
        return

    replay_key = f"replay_buffer:{workspace_id}"
    # Replay buffer is a Redis list: newest-first (LPUSH)
    entries_raw = await redis.lrange(replay_key, 0, 499)
    matching = []
    for raw in entries_raw:
        entry = json.loads(raw)
        if entry.get("ts", "") >= since:
            matching.append(entry)

    matching.reverse()  # Restore chronological order (oldest first)
    await websocket.send_json({
        "type": "replay_batch",
        "entries": matching[:500],
        "count": len(matching[:500]),
    })
```

### Broadcast Service Helper

```python
# backend/app/services/broadcast_service.py

import json
import uuid
from datetime import datetime, timezone

from redis.asyncio import Redis


class BroadcastService:
    """Helper for other services to publish events to the broadcast pipeline."""

    def __init__(self, redis: Redis):
        self._redis = redis

    async def publish_metrics(self, agent_id: uuid.UUID, snapshot: dict) -> None:
        """Publish a metric snapshot to the metrics broadcast channel."""
        payload = json.dumps(snapshot)
        channel = f"metrics:{agent_id}"
        # Fire-and-forget publish + replay buffer append
        await self._redis.publish(channel, payload)

    async def publish_log_entry(self, agent_id: uuid.UUID, entry: dict) -> None:
        """Publish a log entry to the logs broadcast channel."""
        payload = json.dumps({
            "type": "log_entry",
            "agent_id": str(agent_id),
            "entry": entry,
        })
        channel = f"logs:{agent_id}"
        await self._redis.publish(channel, payload)

    async def publish_agent_event(self, workspace_id: uuid.UUID, event: dict) -> None:
        """Publish an agent status event (online/offline) to the workspace channel."""
        payload = json.dumps(event)
        channel = f"agent_events:{workspace_id}"
        await self._redis.publish(channel, payload)

    async def publish_command_event(self, workspace_id: uuid.UUID, event: dict) -> None:
        """Publish a command progress/result event to the workspace channel."""
        payload = json.dumps(event)
        channel = f"command_events:{workspace_id}"
        await self._redis.publish(channel, payload)

    async def push_to_replay_buffer(self, workspace_id: uuid.UUID, entry: dict) -> None:
        """Append an entry to the workspace replay buffer (capped list, TTL 120s)."""
        replay_key = f"replay_buffer:{workspace_id}"
        await self._redis.lpush(replay_key, json.dumps(entry))
        await self._redis.ltrim(replay_key, 0, 999)
        await self._redis.expire(replay_key, 120)
```

### Integration Points with Other Features

| Feature | Integration |
|---|---|
| **F7** (Agent WebSocket Handler) | F7 publishes `agent_events:{workspace_id}` messages when agents connect/disconnect. The broadcast handler subscribes to this channel. F7 also publishes the initial agent-to-workspace mapping to the `workspace_agents:{workspace_id}` Redis set on agent connect. |
| **F10** (Backend Metric Ingestion) | F10 publishes metric snapshots to `metrics:{agent_id}` after successful ingestion and persistence. The broadcast handler's `PSUBSCRIBE metrics:*` pattern captures these. F10 uses the `BroadcastService.publish_metrics()` helper. |
| **F11** (Agent Command Handler) | F11 publishes command progress and result events to `command_events:{workspace_id}`. The broadcast handler forwards these to dashboard clients so deployment wizards (F19) and command panels update in real time. |
| **F12** (Agent Log Streaming) | F12 publishes log entries to `logs:{agent_id}` via `BroadcastService.publish_log_entry()`. The broadcast handler's `PSUBSCRIBE logs:*` pattern captures these and forwards them to the per-agent log viewer (F15). |
| **F14** (Workspace Overview) | The workspace overview page (F14) uses `useDashboardWebSocket` to display live agent status badges and summary metric cards for all agents in the workspace. |
| **F15** (Per-Agent Dashboard) | The per-agent dashboard (F15) uses `useDashboardWebSocket` for live metrics charts, log streaming, and deployment status. It filters messages client-side by the selected `agent_id`. |
| **F19** (Deployment Wizard) | The deployment wizard (F19) uses `useDashboardWebSocket` to subscribe to `command_progress` and `command_result` messages for the deployment being executed. |

### Edge Cases

- **Empty workspace:** If a workspace has no registered agents, the `workspace_agents:{workspace_id}` set is empty. The broadcast handler skips all `metrics:*` and `logs:*` messages for that workspace. Dashboard clients see empty state views (F14 handles this with an "Add your first GPU server" prompt).
- **Agent removed from workspace mid-session:** If an agent is removed from a workspace (F6 de-provisioning), the agent's ID is removed from `workspace_agents:{workspace_id}`. The broadcast handler stops forwarding its metrics/logs within the next message cycle. The dashboard client receives an `agent_status` event with `status: "removed"` and the composable removes the agent from the store.
- **Rapid reconnect (thundering herd):** If the backend restarts, all dashboard clients reconnect within a short window (2s + jitter). The `connect()` method in each composable schedules itself independently via `setTimeout`, so connections spread naturally over the jitter window (±500ms). No server-side rate limiting is needed.
- **Large replay buffer on slow connections:** If a client requests replay and the buffer contains 500 entries of metric data (~200 KB total), the server sends the full batch as a single JSON message. If the client's WebSocket send buffer backs up, the server's `send_json()` may raise an exception — the handler catches this and allows the client reader task to close the connection naturally. The client will reconnect and request replay again once its buffer clears.
- **Clock skew between client and server:** The `since` timestamp in `replay_request` is the client's local clock time. The server compares it against `ts` values in the replay buffer, which are server-side timestamps. If the client clock is more than 30 seconds behind the server, the replay may miss entries. Mitigation: the composable uses the server-provided `ts` from the last received message as `since`, not the local clock.
- **High-frequency metrics and Vue reactivity:** Metric snapshots arrive every 2 seconds per agent. With 50 agents in a workspace, that is 25 messages/second. Each snapshot triggers a store mutation. The chart components use `shallowRef` and manual update batching (update once per second from a rolling buffer) to avoid excessive DOM updates. The `useAgentMetricsStore` maintains a monotonic write counter and only emits a store update signal every 2 seconds (configurable via `UPDATE_INTERVAL_MS`).

### Metrics & Performance Targets

- **Message forwarding latency:** P50 < 20ms, P99 < 100ms from Redis publish to WebSocket `send_json()`.
- **Concurrent connections:** Support 500 simultaneous dashboard WebSocket connections per backend instance.
- **Replay buffer capacity:** 1000 entries per workspace, 120-second TTL — covers any reconnect within 2 minutes.
- **Reconnect success:** > 99.9% of automatic reconnections succeed on the first attempt when the backend is healthy.
- **Memory per connection:** < 1 MB per idle dashboard WebSocket connection (negligible send buffer, no per-connection state beyond the subscription handle).

## Depends on: F7 (Agent WebSocket Handler — agent status events and workspace membership set), F10 (Backend Metric Ingestion — publishes to `metrics:{agent_id}` channel), F12 (Agent Log Streaming — publishes to `logs:{agent_id}` channel)
