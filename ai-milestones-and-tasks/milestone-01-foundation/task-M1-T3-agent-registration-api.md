# Task M1-T3 — Agent Registration API

> **Milestone:** M1 (Foundation)
> **Priority:** Critical
> **Status:** 🟢 Complete
> **Estimated Effort:** 2 days

## Description

Implement the agent registration flow: token generation endpoint for the dashboard, and the two-phase agent registration endpoint (claim → complete with 5-minute timeout rollback). When an agent registers, it reports its hardware specs (GPUs, CPU, RAM, disk, OS, driver versions) and receives back a persistent agent ID plus WebSocket URL.

## Task Goals

- Implement `POST /api/agents/tokens` — generate a new agent registration token
- Implement `POST /api/agents/register` — two-phase registration (claim + complete)
- Implement `GET /api/agents` — list all registered agents (basic info, no auth for MVP)
- Implement `GET /api/agents/{id}` — single agent details with full hardware info
- Create agent naming utility (adjective-animal-number, e.g., "cyan-koala-42")
- Generate proper agent ID with `ag_` prefix
- Add service layer: `app/services/agent_manager.py`
- Add JSON:API schema serialization for agent resources
- Store agent registration token as bcrypt hash with prefix lookup
- Return agent config with WS URL and polling intervals

## Implementation Plan

> ⚠️ Analyze this plan thoroughly before implementing.

### Pre-Implementation Analysis

- Review `requirements/06-api-surface.md` for exact agent registration request/response shapes
- Review `requirements/02-architecture-overview.md` for the registration flow (claim → complete)
- Review `requirements/03-functional-requirements.md` F1.1 (Agent Registration)
- Review `requirements/04-non-functional-requirements.md` NFR3.1 (token security)
- Invoke `fastapi-expert` skill for FastAPI route patterns and Pydantic schemas

### Steps

1. Create `app/utils/naming.py` — random name generator (adjective-animal-number format) using word lists
2. Create `app/utils/crypto.py` — token generation (`secrets.token_urlsafe(32)`), bcrypt hashing, token prefix extraction
3. Create `app/services/agent_manager.py`:
   - `create_registration_token()` — generate token, hash, store with 24h expiry
   - `claim_agent(token, hostname)` — validate token, create agent with "pending" name, return partial agent record
   - `complete_registration(agent_id, hardware_info)` — update agent with full hardware specs, set status to "online"
   - `get_agent(agent_id)` — single agent lookup
   - `list_agents()` — all agents with basic info
   - Token expiry rollback job or check at claim time
4. Create `app/schemas/jsonapi.py` — JSON:API base serializers, `ResourceObject`, `Document`, `Error` response helpers
5. Create `app/schemas/agent.py` — Pydantic models for agent registration request/response
6. Create `app/api/agents.py` — route handlers:
   - `POST /api/agents/tokens` — generates token, returns `{"token": "mp_...", "prefix": "mp_abc", "expires_at": ...}`
   - `POST /api/agents/register` — two-phase: claim (validate token, reserve) → complete (store full info)
   - `GET /api/agents` — list agents (JSON:API format)
   - `GET /api/agents/{id}` — single agent (JSON:API format)
7. Include agent router in `app/main.py`
8. Add test for registration flow: generate token → register → claim → complete → list

### Skills & MCP Servers

| Resource              | Purpose                      | When to Invoke                   |
| --------------------- | ---------------------------- | -------------------------------- |
| `fastapi-expert`      | FastAPI routes, Pydantic     | Steps 4-7 — API implementation   |
| `filesystem` (MCP)    | File creation                | Creating route and schema files  |

## Acceptance Criteria

- [ ] `POST /api/agents/tokens` returns a token with `mp_` prefix and expiry
- [ ] `POST /api/agents/register` with valid token returns agent with `ag_` prefix ID
- [ ] `POST /api/agents/register` with invalid/expired token returns 401
- [ ] `GET /api/agents` returns list of registered agents in JSON:API format
- [ ] `GET /api/agents/{id}` returns full agent details with hardware info
- [ ] Agent names are unique and follow the adjective-animal-number pattern
- [ ] Token expires after 24 hours (or configurable duration)
- [ ] Same token cannot be used twice
- [ ] Registration payload matches the spec in `requirements/06-api-surface.md`

## Completion Criteria

- [ ] All acceptance criteria above pass
- [ ] Python type check passes (`mypy`)
- [ ] Code passes linting (`ruff`)
- [ ] All tests pass (`pytest`)

## Testing Checklist

- [ ] Unit test: token generation and hashing
- [ ] Unit test: two-phase registration happy path
- [ ] Unit test: duplicate token rejection
- [ ] Unit test: expired token rejection
- [ ] Integration test: full registration flow via FastAPI TestClient

## Dependencies

- **Requires:** M1-T1 (Backend Scaffolding), M1-T2 (Database Schema)
- **Blocks:** M1-T4 (Agent WebSocket Handler), M1-T5 (Agent Package)

## Documentation References

- `requirements/06-api-surface.md` — agent endpoints
- `requirements/02-architecture-overview.md` — registration flow
- `requirements/03-functional-requirements.md` — F1.1

## Notes

- Token prefix should be `mp_` (ModelPrism) — agents identify by prefix in auth header
- Use two-phase registration to prevent token replay in distributed scenarios
- The "claim" phase creates the agent record with a temporary name; "complete" fills in hardware details
- If "complete" doesn't arrive within 5 minutes, the token is released and agent record cleaned up
- For MVP, return WS URL as `ws://host:8000/ws/agents/{agent_id}` (upgrade to WSS in production)
