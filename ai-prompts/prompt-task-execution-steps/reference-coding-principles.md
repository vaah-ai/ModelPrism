---
title: Coding Principles Reference
purpose: Coding discipline rules and quality audit checklist
---

# Coding Principles

## Coding Discipline (Apply During Implementation)

- Use the **Edit** / **Write** tools for file operations. Never `sed`, `awk`, `echo >`, or heredocs in Bash.
- After every file edit, immediately run the relevant typecheck (e.g., `npm run typecheck` for frontend, `mypy` for backend).
- IF a test file exists adjacent to the modified file, run it immediately after editing.
- Follow JSON:API 1.0 spec for all dashboard REST endpoints (`application/vnd.api+json`).
- Use lightweight custom format for agent WebSocket messages (flat JSON, no envelope overhead).
- Auth endpoints use standard `application/json`. OpenAI proxy uses OpenAI format.
- Store all API keys/agent tokens as hashes (bcrypt/SHA-256), only prefix stored in plaintext.
- Scope all database queries by `workspace_id` for multi-tenant isolation.
- Agent communication: WebSocket outbound from agent (no inbound ports), WSS in production.
- Do NOT use sidebase/nuxt-auth — use custom Pinia composable calling FastAPI JWT directly.

## Architecture Rules

- **Backend layer order:** models (SQLAlchemy) → schemas (Pydantic) → services (business logic) → api (routes) → ws (WebSocket)
- **Frontend layer order:** types/interfaces → stores (Pinia) → composables → components → pages
- **Agent layer order:** registration → connection (WebSocket) → metrics collection → command handling → log streaming
- **Api format mapping:** Dashboard REST = JSON:API, Auth = standard JSON, Agent WS = flat JSON, Proxy = OpenAI format
- **Multi-instance support:** Track multiple vLLM instances on the same GPU server, each with its own metric stream
- **Docker mandatory** for vLLM model deployment — each model in its own container with `--gpus` reservation

## Principles Audit Checklist (Apply Before Commit)

| Principle | Check |
|-----------|-------|
| **DRY** | No duplicated logic across files. Extract shared schemas into `common/` package. |
| **KISS** | No over-engineered solutions. Agent metric WS uses flat JSON — no JSON:API overhead for 2s pushes. |
| **YAGNI** | No speculative code, no unused parameters, no future-proofing. `MODELPRISM_CLOUD` flag for billing gating — don't hide other features. |
| **SoC** | DB models / Pydantic schemas / route handlers / services / WebSocket handlers separated. |
| **SRP** | Each function / class / component does one thing. Agent modules separated by concern (registration, metrics, logs, commands). |
| **SOLID** | Abstractions respected, interfaces clean. JSON:API base serializers extendable for each resource. |
| **Accessibility** | ARIA roles, keyboard navigation, focus management, dark mode support (PrimeVue handles most). |
| **Security** | Inputs validated (Pydantic), outputs escaped, no secrets in code, parameterised SQL. API keys hashed. Auth scoped by workspace. |

## Complexity Check

- **Single Responsibility?** Refactor if the function has more than one concern.
- **>30 lines?** Extract cohesive blocks into named sub-functions.
- **>3 levels of nesting?** Apply guard clauses / early returns.
- **Side effects in pure layers?** Move them to the outermost layer.
