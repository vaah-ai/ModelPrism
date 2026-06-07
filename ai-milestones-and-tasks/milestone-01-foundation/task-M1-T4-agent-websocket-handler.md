# Task M1-T4 — Agent WebSocket Handler

> **Milestone:** M1 (Foundation)
> **Priority:** Critical
> **Status:** ⚪ Not Started
> **Estimated Effort:** 3 days

> **Impact from M1-T3:** Agent Registration API is now implemented. Agents receive a persistent agent_id (UUID string) and ws_url during registration. WS URL format: `ws://localhost:8000/ws/agents/{agent_id}`. The Agent model stores status (online/offline), last_seen_at, and hardware info (gpu_info/cpu_info/disk_info as JSONB). Registration is two-phase: claim (agent_id + ws_url) → complete (hardware). Use `app/services/agent_manager.py` `get_agent()` for agent lookup by UUID. The `app/api/agents.py` router is at `/api/agents` prefix.

## Description

Implement the backend WebSocket handler for agent connections. Agents connect via `wss://backend/ws/agents/{agent_id}`, send periodic heartbeat messages, push metrics every 2 seconds, and receive commands from the backend. The handler manages connection lifecycle (connect, disconnect, reconnect with exponential backoff) and broadcasts received metrics to the dashboard WebSocket pub/sub system.

## Task Goals

- Implement `GET /ws/agents/{agent_id}` — agent WebSocket endpoint
- Handle connection authentication via agent ID (validated from the path)
- Parse and validate incoming metric messages (`type: "metrics"`)
- Parse and validate heartbeat messages (`type: "heartbeat"`)
- Store latest metrics in Redis for fast dashboard access
- Publish incoming metrics to Redis pub/sub channel for dashboard broadcast
- Track agent connection state (online/offline, last_seen_at)
- Handle disconnection with cleanup (set agent status to offline)
- Implement agent command sending (backend → agent message sending)

## Implementation Plan

> ⚠️ Analyze this plan thoroughly before implementing.

### Pre-Implementation Analysis

- Review `requirements/06-api-surface.md` for all WebSocket message types (metrics, vllm_metrics, heartbeat, command)
- Review `requirements/02-architecture-overview.md` for real-time data flow from agent to browser
- Review `requirements/03-functional-requirements.md` for F1.2 (Agent Connection) and F1.3 (Agent Lifecycle)
- Review `requirements/04-non-functional-requirements.md` for NFR2.1 (Agent Resiliency) and NFR1.1 (Real-Time Metrics)
- Invoke `fastapi-expert` skill for FastAPI WebSocket patterns

### Steps

1. Create `app/ws/agent_ws.py` — Agent WebSocket handler:
   - Accept connection at `/ws/agents/{agent_id}`
   - Validate agent_id exists in database
   - Manage connection state in Redis (set `agent:{id}:ws_connected = true`, TTL-based heartbeat)
   - Message receive loop:
     - `heartbeat` → update `last_seen_at`, check for queued commands to send back
     - `metrics` → validate with Pydantic, store latest in Redis (`agent:{id}:latest_metrics`), publish to `metrics:{agent_id}` Redis channel
     - `vllm_metrics` → same pattern, separate channel
     - `command_progress` and `command_result` → stored for dashboard retrieval
   - Handle client disconnect: close connection, set agent status to offline in DB, clean up Redis keys
2. Create `app/services/agent_manager.py` (update) — add connection management methods:
   - `mark_online(agent_id)`
   - `mark_offline(agent_id)`
   - `is_connected(agent_id)` — check Redis key
   - `send_command(agent_id, command)` — queue command for agent to receive on next heartbeat
3. Create `app/schemas/agent.py` (update) — add WebSocket message Pydantic models:
   - `MetricsMessage` — GPU + system metrics payload
   - `VLLMMetricsMessage` — vLLM-specific metrics
   - `HeartbeatMessage` — agent heartbeat
   - `CommandMessage` — backend → agent command
4. `app/main.py` (update) — mount the agent WebSocket router
5. Add comprehensive error handling: malformed messages, unknown types, DB failures
6. Add reconnection support: if agent reconnects with same ID, close old connection

### Skills & MCP Servers

| Resource              | Purpose                      | When to Invoke                   |
| --------------------- | ---------------------------- | -------------------------------- |
| `fastapi-expert`      | FastAPI WebSocket patterns   | Steps 2-4                       |
| `filesystem` (MCP)    | File creation                | Creating WS handler files        |

## Acceptance Criteria

- [ ] Agent can connect via WebSocket at `/ws/agents/{agent_id}`
- [ ] Backend validates agent_id exists and is registered
- [ ] `heartbeat` messages update agent's `last_seen_at` field
- [ ] `metrics` messages are validated and published to Redis pub/sub
- [ ] `vllm_metrics` messages similarly handled
- [ ] On disconnect, agent status changes to offline
- [ ] Reconnecting agent replaces existing connection cleanly
- [ ] Commands can be queued and sent to connected agent
- [ ] Latest metrics available from Redis by agent_id

## Completion Criteria

- [ ] All acceptance criteria above pass
- [ ] Python type check passes (`mypy`)
- [ ] Code passes linting (`ruff`)
- [ ] WebSocket tests cover: connect, metrics push, heartbeat, disconnect, reconnect

## Testing Checklist

- [ ] Unit test: WebSocket connection and authentication
- [ ] Unit test: metrics message validation
- [ ] Unit test: heartbeat processing
- [ ] Integration test: connect → push metrics → disconnect flow
- [ ] Integration test: reconnect with same agent ID

## Dependencies

- **Requires:** M1-T3 (Agent Registration API)
- **Blocks:** M1-T5 (Agent Package), M1-T6 (Metric Storage + API), M1-T7 (Dashboard WS Broadcast)

## Documentation References

- `requirements/06-api-surface.md` — WebSocket message types
- `requirements/02-architecture-overview.md` — data flow diagram
- `requirements/03-functional-requirements.md` — F1.2, F1.3
- `requirements/04-non-functional-requirements.md` — NFR2.1

## Notes

- Use `websockets` library — FastAPI's built-in WebSocket support handles the connection lifecycle
- Redis pub/sub is the backbone: agent metrics → Redis channel → dashboard consumer
- Keep connection state in Redis (fast, distributed) — DB is source of truth for agent record
- Commands are queued in Redis and delivered on next agent heartbeat (polling pattern)
- For MVP, no message batching on ingest side — each 2s metrics push is processed individually
- Client-side batching (500ms) happens in the dashboard layer, not the backend
