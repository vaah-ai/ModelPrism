# F13 — Agent Lifecycle

- **Effort:** Small
- **Phase:** Foundation
- **Depends on:** F6 (Agent Manager), F7 (WebSocket Service — command relay), F11 (Agent Daemon — core)

---

## Description

The agent lifecycle is a four-state machine that governs every agent in the fleet. The four states form a strict progression:

```
register → pause → stop → deregister
```

An agent **must** pass through each state in order. No transitions are skipped and no reversal is allowed within a single lifecycle run (a stopped agent must go through full registration again).

### State machine

```
┌──────────┐   pause   ┌──────────┐   stop    ┌──────────┐   deregister   ┌────────────┐
│ REGISTER │ ──────→   │  PAUSED  │ ──────→   │  STOPPED │ ────────────→  │ DEREGISTER │
└──────────┘           └──────────┘           └──────────┘               └────────────┘
```

**register** – The agent appears in the backend for the first time. A WebSocket is established and the agent enters the pool.
**pause** – The agent stops processing new work but keeps its WebSocket alive. Running jobs drain before the pause completes.
**stop** – The agent terminates all activity, closes the WebSocket, and releases compute resources.
**deregister** – The agent record is removed from the backend permanently.

### Command flow

All lifecycle commands originate in the **dashboard (F14)** or **API (F15)**, travel through **F11 (Agent Manager) backend → F7 (WebSocket Service) → agent daemon**, and return a status update through **F8 (Collector)**.

---

## Examples

### 1. Registration lifecycle (complete flow)

```json
// 1. Agent starts → sends identity payload
// POST /api/agents/register
{
  "agent_id": "agent-7f3a1b",
  "hostname": "worker-42.prod.example.com",
  "capabilities": {
    "gpu": "A100-80GB",
    "vram_mb": 81920,
    "max_jobs": 4,
    "supported_models": ["gpt-4", "claude-3-opus"]
  },
  "version": "1.2.0"
}

// 2. Agent Manager (F11) validates → returns registration token
// 201 Created
{
  "agent_id": "agent-7f3a1b",
  "token": "reg_live_a1b2c3d4e5f6...",
  "ws_endpoint": "wss://ws.modelprism.io/agents/agent-7f3a1b/events",
  "ttl_seconds": 300
}

// 3. Agent opens WebSocket to ws_endpoint
// → sends registration handshake
{
  "type": "agent.handshake",
  "payload": { "token": "reg_live_a1b2c3d4e5f6..." }
}

// 4. F7 confirms → agent state is now REGISTER → Online
{
  "type": "agent.handshake_ack",
  "payload": { "agent_id": "agent-7f3a1b", "status": "online" }
}
```

### 2. Pause from dashboard

```json
// Dashboard (F14) calls F11 API
// POST /api/agents/agent-7f3a1b/pause
{ "reason": "maintenance_window" }

// F11 validates state (must be REGISTER) → sends via F7 WebSocket
// F7 → agent daemon
{
  "type": "agent.command",
  "command": "pause",
  "payload": {
    "agent_id": "agent-7f3a1b",
    "reason": "maintenance_window",
    "drain_timeout_s": 60,
    "requested_by": "user-abc-123"
  }
}

// Agent daemon:
//   - Stops accepting new jobs
//   - Drains running jobs (or waits up to drain_timeout_s)
//   - Sends status update

// F8 Collector receives:
{
  "agent_id": "agent-7f3a1b",
  "type": "status_change",
  "from": "REGISTER",
  "to": "PAUSED",
  "reason": "maintenance_window",
  "timestamp": "2026-06-07T14:30:00Z"
}
```

### 3. Graceful stop with Docker cleanup

```json
// POST /api/agents/agent-7f3a1b/stop
{ "reason": "scale_in" }

// F11 validates state (must be PAUSED) → F7 → agent

// Agent daemon stop sequence:
// 1. Close WebSocket
// 2. Stop job runner
// 3. docker stop $(docker ps -q --filter label=modelprism.agent=agent-7f3a1b)
// 4. docker rm $(docker ps -aq --filter label=modelprism.agent=agent-7f3a1b)
// 5. Release GPU memory (nvidia-smi GPU reset via CUDA_VISIBLE_DEVICES)

// F8 Collector receives:
{
  "agent_id": "agent-7f3a1b",
  "type": "status_change",
  "from": "PAUSED",
  "to": "STOPPED",
  "reason": "scale_in",
  "cleanup": {
    "containers_stopped": 3,
    "containers_removed": 3,
    "gpu_memory_released_mb": 81920,
    "completed_at": "2026-06-07T14:35:00Z"
  }
}
```

### 4. Deregister (backend-initiated)

```json
// POST /api/agents/agent-7f3a1b/deregister
{ "reason": "replacement", "replacement_id": "agent-8b4c2d" }

// F11 validates state (must be STOPPED) → removes record after grace window

// Backend keeps agent record for 60 seconds for reconnect
// After 60s: record deleted permanently

// F8 Collector receives:
{
  "agent_id": "agent-7f3a1b",
  "type": "status_change",
  "from": "STOPPED",
  "to": "DEREGISTER",
  "reason": "replacement",
  "reconnect_grace_window_s": 60,
  "timestamp": "2026-06-07T14:40:00Z"
}
```

### 5. Agent-initiated stop (SIGTERM)

```json
// Agent receives SIGTERM → sends stop command proactively
{
  "type": "agent.command",
  "command": "stop",
  "payload": {
    "agent_id": "agent-7f3a1b",
    "reason": "node_shutdown",
    "initiated_by": "agent"
  }
}

// F11 acknowledges:
{
  "type": "agent.command_ack",
  "command": "stop",
  "payload": { "agent_id": "agent-7f3a1b", "status": "acknowledged" }
}

// Agent proceeds with cleanup:
//   - Drains running jobs
//   - Closes WebSocket
//   - Releases compute
//   - Process exits 0
```

---

## Acceptance Criteria

### AC1: State machine validity
The state machine **must** enforce strict ordering. A direct `register → stop` or `register → deregister` transition is rejected with a `409 Conflict`. Only the four defined edges are allowed.

### AC2: Pause behaviour
When a pause command arrives:
1. The agent immediately stops accepting **new** jobs (before draining existing ones). There is no window where a new job sneaks in after the pause request is acknowledged.
2. Running jobs are given up to `drain_timeout_s` seconds to complete. Jobs that exceed the timeout **must** be terminated (SIGTERM → SIGKILL after 10 s grace).
3. The `PAUSED` state is acknowledged only after all running jobs have been drained or terminated.

### AC3: Stop cleanup completeness
Before the stop acknowledgement is sent:
- All Docker containers tagged with `modelprism.agent=<agent_id>` are stopped **and** removed
- GPU memory tracked by `nvidia-smi` for this agent's `CUDA_VISIBLE_DEVICES` range is verified released (a warning is logged if memory remains allocated after 30 s)
- The WebSocket connection is fully closed

### AC4: Reconnect grace window
When a deregister is requested, the agent record is soft-deleted for **60 seconds** during which a reconnect attempt by the same `agent_id` restores it to `REGISTER` state. After 60 s the record is hard-deleted and any reconnect attempt is rejected with `410 Gone`.

---

## Technical Notes

### File structure

| Layer | File |
|---|---|
| F13 lifecycle spec | `requirements/features/feature-f13-agent-lifecycle.md` |
| State machine models | `modelprism/agents/models.py` |
| F11 route handlers | `modelprism/api/routes/agents.py` |
| F7 WebSocket handlers | `modelprism/ws/handlers.py` |
| Agent daemon | `modelprism/agent/daemon.py` |

### Python code — state machine

```python
from enum import Enum

class AgentLifecycleState(str, Enum):
    REGISTER = "REGISTER"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    DEREGISTER = "DEREGISTER"

# Allowed transitions: current → next
LIFECYCLE_TRANSITIONS: dict[AgentLifecycleState, AgentLifecycleState] = {
    AgentLifecycleState.REGISTER: AgentLifecycleState.PAUSED,
    AgentLifecycleState.PAUSED: AgentLifecycleState.STOPPED,
    AgentLifecycleState.STOPPED: AgentLifecycleState.DEREGISTER,
}

def validate_transition(
    current: AgentLifecycleState, target: AgentLifecycleState
) -> bool:
    """Return True if the transition is valid, False otherwise."""
    expected = LIFECYCLE_TRANSITIONS.get(current)
    return expected is not None and expected == target
```

### Python code — F11 route handler pattern

```python
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/api/agents", tags=["agents"])

class LifecycleRequest(BaseModel):
    reason: str | None = None

class LifecycleResponse(BaseModel):
    agent_id: str
    previous_state: str
    current_state: str
    timestamp: str

@router.post("/{agent_id}/pause", status_code=status.HTTP_200_OK)
async def pause_agent(agent_id: str, req: LifecycleRequest):
    """Transition an agent from REGISTER → PAUSED."""
    agent = await get_agent(agent_id)          # F6 read
    if not agent:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if agent.state != AgentLifecycleState.REGISTER:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Cannot pause agent in state {agent.state}. Must be REGISTER."
        )
    # Send command via F7 WebSocket
    await send_command_via_websocket(agent_id, "pause", req.reason)
    return LifecycleResponse(
        agent_id=agent_id,
        previous_state=agent.state,
        current_state=AgentLifecycleState.PAUSED,
        timestamp=now_iso(),
    )

# pause, stop, and deregister follow the same pattern.
```

### Python code — AgentManager class (in F11)

```python
class AgentManager:
    """Owns the lifecycle of every agent in the fleet."""

    def __init__(self, ws_service: WebSocketService, collector: Collector):
        self._agents: dict[str, AgentRecord] = {}
        self._ws = ws_service
        self._collector = collector

    async def register(
        self, identity: AgentIdentity
    ) -> AgentRegistration:
        """Register a new agent and return a WebSocket endpoint + token."""
        token = generate_registration_token()
        record = AgentRecord(
            agent_id=identity.agent_id,
            state=AgentLifecycleState.REGISTER,
            identity=identity,
            token=token,
            registered_at=utcnow(),
        )
        self._agents[identity.agent_id] = record
        return AgentRegistration(
            agent_id=identity.agent_id,
            token=token,
            ws_endpoint=f"wss://ws.modelprism.io/agents/{identity.agent_id}/events",
            ttl_seconds=300,
        )

    async def transition(
        self, agent_id: str, target: AgentLifecycleState
    ) -> AgentRecord:
        """Validate and apply a lifecycle transition."""
        record = self._agents.get(agent_id)
        if not record:
            raise UnknownAgentError(agent_id)
        current = record.state
        if not validate_transition(current, target):
            raise InvalidTransitionError(current, target)
        record.state = target
        record.transitioned_at = utcnow()
        await self._collector.emit(
            StatusEvent(
                agent_id=agent_id,
                from_state=current,
                to_state=target,
            )
        )
        return record
```

### Python code — command flow (F7 → agent daemon)

```python
# On the F7 WebSocket Service side:
async def send_command(agent_id: str, command: str, payload: dict):
    """Relay a lifecycle command to the agent over its WebSocket connection."""
    ws = await get_agent_connection(agent_id)
    if ws is None:
        raise AgentDisconnectedError(agent_id)
    await ws.send_json({
        "type": "agent.command",
        "command": command,
        "payload": payload,
    })

# On the agent daemon side:
async def handle_command(message: dict):
    cmd = message["command"]
    payload = message["payload"]
    if cmd == "pause":
        await drain_jobs(timeout=payload.get("drain_timeout_s", 60))
        await send_status_change(AgentLifecycleState.PAUSED, reason=payload.get("reason"))
    elif cmd == "stop":
        await stop_job_runner()
        await cleanup_docker_containers()
        await release_gpu_memory()
        await close_websocket()
        await send_status_change(AgentLifecycleState.STOPPED, reason=payload.get("reason"))
    elif cmd == "deregister":
        await send_status_change(AgentLifecycleState.DEREGISTER, reason=payload.get("reason"))
```

### Python code — shutdown signal handler (agent-side stop)

```python
import asyncio, signal

class AgentDaemon:
    async def run(self):
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(self._on_sigterm()))

    async def _on_sigterm(self):
        logger.warning("SIGTERM received — initiating agent stop")
        await self.send_command("stop", {"reason": "node_shutdown", "initiated_by": "agent"})
        await self._drain_jobs()
        await self._cleanup_resources()
        raise SystemExit(0)
```

### Edge cases

| Scenario | Behaviour |
|---|---|
| **Double pause** | Agent is already PAUSED → second pause returns `409 Conflict`. |
| **Concurrent commands** | F11 serialises commands per-agent (lock per `agent_id`). A stop in-flight blocks a deregister until the stop completes. |
| **Token expiry during registration** | If the 300 s TTL expires before the WebSocket handshake, the register token becomes invalid (the agent must re-register to get a fresh token). |
| **Crash mid-stop** | The agent process exits unexpectedly before finishing Docker cleanup. The **F8 Collector** detects the missing heartbeat and emits a `DEREGISTER` event with `reason: "lost_heartbeat"`. **F6** eventually GCs the record after a configurable timeout (default 120 s). |

### Integration points

| Feature | Role |
|---|---|
| **F6** | Agent Manager data store — reads/writes agent state |
| **F7** | WebSocket Service — relays lifecycle commands to agents |
| **F8** | Collector — receives status-change events from agents |
| **F11** | Agent Daemon — processes lifecycle commands on the agent |
| **F14** | Dashboard — UI for triggering lifecycle commands |
| **F15** | Public API — external callers can trigger lifecycle commands |
| **F16** | Auth — protects lifecycle endpoints; only authorised users/roles may issue pause/stop/deregister |
| **F20** | Observability — logs and metrics for every lifecycle transition |
