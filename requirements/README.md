# ModelPrism Requirements

This directory contains the product requirements for **ModelPrism** — the open-source GPU inference management platform.

## Documents

| File | Description |
|------|-------------|
| [01-product-vision.md](./01-product-vision.md) | Product vision, tagline, scope, target audience, open-source commitment |
| [02-architecture-overview.md](./02-architecture-overview.md) | System architecture, deployment models, data flow, API standards, key design decisions |
| [03-functional-requirements.md](./03-functional-requirements.md) | Detailed functional requirements by feature area (F1–F7) |
| [04-non-functional-requirements.md](./04-non-functional-requirements.md) | Performance, reliability, security, maintainability, portability, open-source requirements |
| [05-tech-stack.md](./05-tech-stack.md) | Technology choices with rationale (frontend, backend, agent, dev tooling) |
| [06-api-surface.md](./06-api-surface.md) | API endpoints overview (REST, WebSocket, proxy) |
| [07-directory-structure.md](./07-directory-structure.md) | Repository directory structure |

## Architecture Decision Records

| File | Decision |
|------|----------|
| [adr/ADR-001-jsonapi-scope.md](./adr/ADR-001-jsonapi-scope.md) | JSON:API for dashboard REST only; lightweight format for agent WS + proxy |
| [adr/ADR-002-docker-vllm.md](./adr/ADR-002-docker-vllm.md) | Docker mandatory for vLLM model deployment isolation |
| [adr/ADR-003-auth-approach.md](./adr/ADR-003-auth-approach.md) | Custom Pinia composable + FastAPI JWT (no sidebase/nuxt-auth) |
| [adr/ADR-004-monetization.md](./adr/ADR-004-monetization.md) | Open core model — core OSS, cloud-only features separate |
| [adr/ADR-005-data-retention.md](./adr/ADR-005-data-retention.md) | Configurable per-workspace data retention |

## Feature Dependency Map

| File | Description |
|------|-------------|
| [feature-dependency-map.md](./feature-dependency-map.md) | 40 features ordered by technical dependencies across 9 build phases |

## Machine-Readable

| File | Description |
|------|-------------|
| [.requirements-manifest.json](./.requirements-manifest.json) | Machine-readable manifest for downstream pipeline consumption |

## Key Technology Summary

| Layer | Technology |
|-------|-----------|
| **Frontend** | Nuxt 4 + PrimeVue 4 + Tailwind CSS v4 + TypeScript |
| **Charts** | uPlot (real-time), ECharts (comparison/billing) |
| **State** | Pinia |
| **Auth** | Custom Pinia composable + FastAPI JWT (email/password only) |
| **Backend** | FastAPI + Python 3.11+ |
| **API Format** | JSON:API 1.0 (dashboard REST), lightweight custom (agent WS), OpenAI format (proxy) |
| **Database** | PostgreSQL 15+ with partitioned time-series tables |
| **Cache** | Redis 7+ |
| **Agent** | Python 3.10+ (modelprism-agent), vLLM in Docker containers |
| **Billing** | Stripe (cloud only, behind `MODELPRISM_CLOUD` flag) |
| **Model Source** | HuggingFace Hub (resumable downloads) |

## Per-Feature Specifications

All 40 features have individual specification documents with concrete examples (Specification by Example):

| Phase | Files |
|-------|-------|
| **Foundation (F1–F13)** | [F1](features/feature-f1-backend-scaffolding.md), [F2](features/feature-f2-frontend-scaffolding.md), [F3](features/feature-f3-database-schema.md), [F4](features/feature-f4-jsonapi-serialization-layer.md), [F5](features/feature-f5-email-password-auth.md), [F6](features/feature-f6-agent-registration.md), [F7](features/feature-f7-agent-websocket-handler.md), [F8](features/feature-f8-agent-metric-collection.md), [F9](features/feature-f9-agent-metric-push.md), [F10](features/feature-f10-backend-metric-ingestion.md), [F11](features/feature-f11-agent-command-handler.md), [F12](features/feature-f12-agent-log-streaming.md), [F13](features/feature-f13-agent-lifecycle.md) |
| **MVP (F14–F17)** | [F14](features/feature-f14-gpu-server-overview-page.md), [F15](features/feature-f15-single-server-dashboard.md), [F16](features/feature-f16-websocket-broadcast.md), [F17](features/feature-f17-time-range-selector.md) |
| **Enhancement (F18–F26)** | [F18](features/feature-f18-hf-hub-browser.md), [F19](features/feature-f19-model-deployment-wizard.md), [F20](features/feature-f20-docker-model-deployment.md), [F21](features/feature-f21-model-download-resumable.md), [F22](features/feature-f22-running-model-management.md), [F23](features/feature-f23-model-optimization-recommendations.md), [F24](features/feature-f24-benchmark-runner.md), [F25](features/feature-f25-benchmark-storage-history.md), [F26](features/feature-f26-benchmark-comparison.md) |
| **Scale (F27–F35)** | [F27](features/feature-f27-api-key-management.md), [F28](features/feature-f28-openai-proxy.md), [F29](features/feature-f29-token-counting-usage.md), [F30](features/feature-f30-rate-limiting.md), [F31](features/feature-f31-request-routing.md), [F32](features/feature-f32-workspace-management.md), [F33](features/feature-f33-role-based-access.md), [F34](features/feature-f34-workspace-data-isolation.md), [F35](features/feature-f35-data-retention-config.md) |
| **Growth (F36–F40)** | [F36](features/feature-f36-server-hourly-pricing.md), [F37](features/feature-f37-stripe-integration.md), [F38](features/feature-f38-billing-dashboard.md), [F39](features/feature-f39-billing-alerts.md), [F40](features/feature-f40-admin-panel.md) |

## Cross-Cutting Documents

| File | Description |
|------|-------------|
| [deployment/deployment.md](deployment/deployment.md) | Deployment guide, Docker Compose setup, env vars, TLS, backup |
| [testing/testing-strategy.md](testing/testing-strategy.md) | Testing pyramid, backend/frontend/agent tests, CI pipeline |
| [security/security.md](security/security.md) | Auth, API keys, Docker security, rate limiting, data isolation |
| [api/api-design.md](api/api-design.md) | JSON:API 1.0 spec, WebSocket protocol, OpenAI proxy format |
| [data-models/data-models.md](data-models/data-models.md) | ERD, all 13 database tables with columns, types, constraints |
| [integrations/integrations.md](integrations/integrations.md) | HuggingFace Hub, Docker, NVIDIA, Stripe, Redis, Systemd |
| [analytics/analytics.md](analytics/analytics.md) | Usage tracking, cost comparison, benchmark reporting, alerts |
| [glossary.md](glossary.md) | All key terms and definitions |

## Current Focus

Phase 2 — Agent-based architecture with:
- `modelprism-agent` installable on any GPU server via `curl | bash`
- Central FastAPI backend receiving metrics from agents via WebSocket
- Agent log streaming via HTTP POST to backend
- Nuxt 4 frontend hosted on dedicated VPS or self-hosted
- Real-time WebSocket metrics from agent → backend → browser
- Docker-based model deployment and management from the dashboard
- Configurable data retention per workspace
- Per-server hourly pricing for cost comparison
- Email/password authentication only
