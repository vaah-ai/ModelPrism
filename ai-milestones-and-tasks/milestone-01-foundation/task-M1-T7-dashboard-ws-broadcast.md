# Task M1-T7 — Dashboard WebSocket Broadcast

> **Milestone:** M1 (Foundation)
> **Priority:** High
> **Status:** ⚪ Not Started
> **Estimated Effort:** 2 days

> **Impact from M1-T4:** Agent metrics are already published to Redis channels `metrics:{agent_id}` and `vllm_metrics:{agent_id}` by the agent WebSocket handler. This task needs to create a *dashboard* WebSocket endpoint (`/ws/dashboard/{agent_id}`) that subscribes to these Redis channels and forwards to browser clients. The `PubSubHelper` class in `app/redis.py` can be used for subscription. Connection state is tracked in Redis at `agent:{id}:ws_connected` (TTL-based). Running vLLM instances are stored at `agent:{id}:running_instances`.

## Description

Implement the pipeline that broadcasts real-time metrics from the backend to browser-based dashboard clients. Metrics arrive from agents via WebSocket and are published to Redis pub/sub channels. A dashboard WebSocket endpoint at `/ws/dashboard/{agent_id}` (or `/ws/dashboard` for all agents) subscribes to these channels and forwards metrics to connected browser clients.

## Task Goals

- Implement Redis pub/sub consumer that listens on agent metric channels
- Implement `GET /ws/dashboard/{agent_id}` — real-time metrics for a specific agent
- Implement `GET /ws/dashboard` — aggregate metrics for all user's agents
- Implement client-side 500ms batching in the dashboard WebSocket composable
- Broadcast agent log entries to dashboard clients in real-time
- Handle multiple concurrent dashboard connections per agent

## Implementation Plan

> ⚠️ Analyze this plan thoroughly before implementing.

### Pre-Implementation Analysis

- Review `requirements/06-api-surface.md` for dashboard WebSocket paths
- Review `requirements/02-architecture-overview.md` for the data flow: Agent → Backend → Redis pub/sub → Browser
- Review `requirements/04-non-functional-requirements.md` NFR1.2 (client-side 500ms batching)
- Review `requirements/03-functional-requirements.md` F2.2 (real-time dashboard data)
- Invoke `fastapi-expert` skill for WebSocket broadcasting patterns with Redis pub/sub

### Steps

1. Create `app/services/broadcast_service.py`:
   - `subscribe_agent_metrics(agent_id)` — subscribe to `metrics:{agent_id}` Redis channel
   - `subscribe_agent_logs(agent_id)` — subscribe to `logs:{agent_id}` Redis channel
   - `publish_metrics(agent_id, metrics_data)` — called by agent WS handler
   - `publish_log(agent_id, log_entry)` — called by log ingest endpoint
   - Manage subscription lifecycle (connect/disconnect reference counting)
2. Create `app/ws/dashboard_ws.py`:
   - `GET /ws/dashboard/{agent_id}` — accept dashboard connection for specific agent
     - Subscribe to `metrics:{agent_id}` and `logs:{agent_id}` Redis channels
     - Forward messages to the WebSocket as they arrive
     - Handle client disconnect — unsubscribe from Redis channels
   - `GET /ws/dashboard` — accept dashboard connection for all agents
     - No auth for MVP — list all connected agents
     - Subscribe to all active agent metric channels
     - Forward messages to the WebSocket
     - Handle client disconnect
3. Add log broadcast integration:
   - When `POST /api/agents/{id}/logs` receives a log entry, publish to `logs:{agent_id}` Redis channel
   - Dashboard WS handler forwards log entries to connected browsers
4. Implement connection management:
   - Track active dashboard WS connections per agent (for metrics)
   - Track active dashboard WS connections for all-agents view
   - Clean up Redis subscriptions when last client disconnects
5. Include dashboard WS router in `app/main.py`
6. Create Pinia store composable for frontend consumption (skeleton — fully implemented in M1-T9):
   - `useWebSocketMetrics.ts` — connects to dashboard WS, batches messages every 500ms

### Skills & MCP Servers

| Resource              | Purpose                      | When to Invoke                   |
| --------------------- | ---------------------------- | -------------------------------- |
| `fastapi-expert`      | WebSocket + Redis pub/sub    | Steps 1-4                       |
| `filesystem` (MCP)    | File creation                | Creating WS and service files    |

## Acceptance Criteria

- [ ] Dashboard WebSocket connects to `/ws/dashboard/{agent_id}`
- [ ] Dashboard receives metrics in real-time as agent pushes them
- [ ] Dashboard WebSocket connects to `/ws/dashboard` and receives all agent metrics
- [ ] Agent log entries are broadcast to dashboard WebSocket in real-time
- [ ] Multiple dashboard clients can connect simultaneously for the same agent
- [ ] Client disconnect properly unsubscribes from Redis channels
- [ ] Messages are forwarded within < 500ms (allowing for client-side batching)

## Completion Criteria

- [ ] All acceptance criteria above pass
- [ ] Python type check passes (`mypy`)
- [ ] Code passes linting (`ruff`)
- [ ] WebSocket tests cover: connect, receive metrics, disconnect

## Testing Checklist

- [ ] Unit test: Redis pub/sub publishing and receiving
- [ ] Integration test: agent WS → Redis → dashboard WS end-to-end flow
- [ ] Integration test: multiple dashboard clients receiving same metrics
- [ ] Integration test: client disconnect cleanup

## Dependencies

- **Requires:** M1-T4 (Agent WebSocket Handler), M1-T6 (Metric Storage + API)
- **Blocks:** M1-T9 (Dashboard Pages)

## Documentation References

- `requirements/06-api-surface.md` — dashboard WebSocket paths
- `requirements/02-architecture-overview.md` — data flow diagram
- `requirements/03-functional-requirements.md` — F2.2
- `requirements/04-non-functional-requirements.md` — NFR1.2

## Notes

- Redis pub/sub is the message bus — no direct agent→dashboard coupling
- The dashboard WS handler is lightweight: just subscribe and forward
- Reference counting on subscriptions: `subscribe()` increments counter, `unsubscribe()` decrements, only actually unsubscribes from Redis when counter reaches 0
- Client-side 500ms batching is implemented in the Pinia store composable (dashboard side), not in the backend
- For MVP, no message filtering or aggregation on the backend — forward as-is
- Message format forwarded to dashboard matches the agent metric format (flat JSON, no envelope)
