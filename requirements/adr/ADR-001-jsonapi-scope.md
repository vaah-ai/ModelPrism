# ADR-001: JSON:API Scope

## Status
Accepted

## Context
The requirements specified JSON:API 1.0 format for "all FastAPI endpoints." However:

1. The agent WebSocket protocol uses real-time messages (metrics every 2s, commands, logs) — JSON:API's envelope overhead (10-15%) adds latency without benefit for internal consumers.
2. The OpenAI-compatible proxy (`/v1/chat/completions`, etc.) must match OpenAI's format exactly — JSON:API would break compatibility.
3. Auth endpoints (login, register) need simple shapes; JSON:API adds friction.
4. Manual JSON:API implementation for every resource is a significant effort multiplier (~40% more serializer code).

## Decision
- **Dashboard REST endpoints** (agents, models, deployments, benchmarks, users, workspaces, keys, usage) → JSON:API 1.0 format
- **Agent WebSocket messages** → lightweight type-discriminated JSON (no envelope)
- **Agent REST endpoints** (registration, log push) → JSON:API for registration, standard JSON for log push
- **OpenAI proxy endpoints** → OpenAI standard format (not JSON:API)
- **Auth endpoints** → standard `application/json` (exception)

## Consequences
- Two API formats in the codebase, clearly documented
- JSON:API base serializers in `backend/app/schemas/jsonapi.py` for reuse
- OpenAPI auto-docs will document JSON:API endpoints with their actual format
- Clear section in architecture docs documenting which format applies where
