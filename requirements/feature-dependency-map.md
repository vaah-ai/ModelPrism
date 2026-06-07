# Feature Dependency Map

Features ordered by **technical dependencies**, not priority.

## Phase A: Foundation (Backend + Frontend + Auth)

| ID | Feature | Dependencies | Effort | Phase |
|----|---------|-------------|--------|-------|
| F1 | Backend scaffolding: FastAPI app, Pydantic settings, database engine, Redis, async lifespan | None | Medium | Foundation |
| F2 | Frontend scaffolding: Nuxt 4 init, layouts, routing, PrimeVue + Tailwind setup, theme | None | Medium | Foundation |
| F3 | Database schema: users, workspaces, agents, model_deployments, api_keys, usage_records, benchmarks, billing tables, agent_logs | None | Large | Foundation |
| F4 | JSON:API serialization layer: base ResourceObject, Document, Pagination, Error formatters, filter/sort parsers | F3 | Medium | Foundation |
| F5 | Email/password auth: register, login, JWT issue, refresh token rotation, session management, password reset | F1, F3 | Medium | Foundation |

## Phase B: Agent System

| ID | Feature | Dependencies | Effort | Phase |
|----|---------|-------------|--------|-------|
| F6 | Agent registration endpoint + token generation (two-phase: claim → complete, 5-min rollback) | F1, F3, F4 | Small | Foundation |
| F7 | Agent WebSocket connection handler: connect, heartbeat (15s), reconnect, disconnect cleanup | F1, F6 | Medium | Foundation |
| F8 | Agent metric collection: nvidia-smi polling, psutil system metrics, local vLLM Prometheus metrics | F13 | Medium | Foundation |
| F9 | Agent metric push over WebSocket: metric message types, batching, push every 2s | F7, F8 | Medium | Foundation |
| F10 | Backend metric ingestion + downsampled storage: raw→2s (24h), 1m→(30d), 5m→(1y) | F1, F3, F7, F9 | Large | Foundation |
| F11 | Agent command handler: receive, execute, progress reporting, response for deploy/stop/restart | F7 | Medium | Foundation |
| F12 | Agent log streaming: HTTP POST to `/api/agents/{id}/logs`, backend storage + WS broadcast to dashboard | F1, F3, F7 | Small | Foundation |
| F13 | Agent lifecycle: register, pause (stop metrics, keep vLLM), stop (clean up containers), deregister | F6, F7, F11 | Small | Foundation |

## Phase C: Dashboard

| ID | Feature | Dependencies | Effort | Phase |
|----|---------|-------------|--------|-------|
| F14 | GPU server overview page: agent list, status, aggregate GPU utilization, VRAM, running models | F2, F5, F7, F10 | Large | MVP |
| F15 | Single GPU server dashboard: real-time charts (uPlot), system resources, diagnostic cards, live log viewer | F2, F5, F7, F9, F12 | XL | MVP |
| F16 | WebSocket broadcast: backend → browser metric stream, log stream, with client-side 500ms batching | F7, F9, F12 | Medium | MVP |
| F17 | Time range selector + historical data query: presets (15m, 1h, 6h, 24h, 7d), custom date range | F10 | Medium | MVP |

## Phase D: Model Management

| ID | Feature | Dependencies | Effort | Phase |
|----|---------|-------------|--------|-------|
| F18 | HuggingFace Hub browser: search, filter, model details, VRAM estimate | F1, F4 | Medium | Enhancement |
| F19 | Model deployment wizard: 5-step stepper (select model → select agent → config → capacity → deploy) | F2, F5, F18 | XL | Enhancement |
| F20 | Docker-based model deployment: container management, GPU device reservation, port allocation, health checks | F11, F13 | Large | Enhancement |
| F21 | Model download (resumable): HF Hub snapshot_download, progress streaming, checksum verification | F11 | Medium | Enhancement |
| F22 | Running model management: list, stop, restart, delete, view logs (container logs + agent logs) | F11, F20 | Large | Enhancement |
| F23 | Model optimization recommendations: rule-based (4 rules) on observed metrics | F10, F22 | Medium | Enhancement |

## Phase E: Benchmarking

| ID | Feature | Dependencies | Effort | Phase |
|----|---------|-------------|--------|-------|
| F24 | Benchmark runner: trigger, config (requests + concurrency), agent execution, real-time results | F11, F22 | Large | Enhancement |
| F25 | Benchmark storage + history: results table, filters, search | F3, F10 | Medium | Enhancement |
| F26 | Benchmark comparison: side-by-side charts (bar, scatter, radar) | F2, F25 | Large | Enhancement |

## Phase F: API Proxy

| ID | Feature | Dependencies | Effort | Phase |
|----|---------|-------------|--------|-------|
| F27 | API key generation & management: key creation with scoping, hashing, revocation, rate limits | F1, F3 | Medium | Scale |
| F28 | OpenAI-compatible proxy endpoints: `/v1/chat/completions`, `/v1/completions`, `/v1/models`, streaming | F1, F22, F27 | XL | Scale |
| F29 | Token counting + usage tracking: tiktoken, per-request input/output tokens, cost accrual | F27, F28 | Large | Scale |
| F30 | Rate limiting: per-key sliding window, per-IP, Redis-backed, burst handling | F27, F28 | Medium | Scale |
| F31 | Request routing: self-hosted vLLM selection by model name, round-robin across agents | F22, F28 | Medium | Scale |

## Phase G: Multi-Tenancy & Workspace

| ID | Feature | Dependencies | Effort | Phase |
|----|---------|-------------|--------|-------|
| F32 | Workspace management: create, settings (name, data retention), members list, member roles | F3, F5 | Medium | Scale |
| F33 | Role-based access: Owner/Admin/Member/Viewer permission matrix enforced on all endpoints | F5, F32 | Large | Scale |
| F34 | Workspace-scoped data isolation: `workspace_id` filter on all queries, cross-workspace access prevention | F3, F32 | Medium | Scale |
| F35 | Data retention configuration UI + cleanup job | F10, F12, F32 | Medium | Scale |

## Phase H: Billing (Cloud Only)

| ID | Feature | Dependencies | Effort | Phase |
|----|---------|-------------|--------|-------|
| F36 | Server hourly pricing config: per-GPU-server hourly rate in agent settings, cost comparison charts | F14, F15 | Small | Growth |
| F37 | Stripe integration: metered billing, checkout, webhook idempotency, invoice generation | F29, F30 | Large | Growth |
| F38 | Billing dashboard: current spend, invoices, payment method, usage breakdown | F2, F37 | Medium | Growth |
| F39 | Billing alerts: spend thresholds, in-app + email notifications | F37, F38 | Medium | Growth |

## Phase I: Admin

| ID | Feature | Dependencies | Effort | Phase |
|----|---------|-------------|--------|-------|
| F40 | Admin panel: system-wide agents, usage, users overview | All above | Medium | Growth |

## Dependency Graph (text)

```
Foundation (F1-F5) ──> Agent System (F6-F13) ──> Dashboard (F14-F17)
                                                        │
                                                        v
                                              Model Management (F18-F23)
                                                        │
                                                        v
                                              Benchmarking (F24-F26)

Foundation (F1-F5) ──> Model Management (F22) ──> API Proxy (F27-F31)
                                                        │
                                                        v
                                              Multi-Tenancy (F32-F35)
                                                        │
                                                        v
                                              Billing (F36-F39)
                                                        │
                                                        v
                                              Admin (F40)
```
