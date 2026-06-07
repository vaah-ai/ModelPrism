# Milestone M1 — Foundation (Backend + Agent + Dashboard)

> **Category:** Infrastructure & Core
> **Priority:** Critical
> **Status:** ⚪ Not Started
> **Estimated Effort:** 3-4 weeks
> **Dependencies:** None

## Objective

Build the foundational components of ModelPrism: a FastAPI backend for agent management and metric storage, the modelprism-agent Python package that runs on GPU servers to collect and push metrics, and a Nuxt 4 dashboard for visualizing GPU server status and real-time metrics. This milestone establishes the core architecture: Agent → WebSocket/REST → FastAPI Backend → Nuxt Dashboard.

## Success Criteria

- [ ] FastAPI backend starts with PostgreSQL + Redis connections and a health check endpoint
- [ ] Database schema created with migrations for agents, tokens, metrics, and logs
- [ ] Agent registration flow works end-to-end (token generation → claim → complete)
- [ ] Agent WebSocket connection persists with heartbeat and reconnection
- [ ] Agent collects GPU (nvidia-smi), system (psutil), and vLLM Prometheus metrics
- [ ] Metrics pushed over WebSocket every 2 seconds and stored with downsampling
- [ ] Agent logs streamed to backend and accessible via API
- [ ] Dashboard WebSocket broadcasts metrics to connected browsers in real-time
- [ ] Nuxt 4 frontend scaffolded with PrimeVue + Tailwind CSS v4
- [ ] Dashboard shows server overview list and single-server detail page with live charts

## Tasks

- M1-T1 — Backend Scaffolding: FastAPI app, config, database engine, Redis, lifespan
- M1-T2 — Database Schema: agents, agent_tokens, metrics, agent_logs + Alembic migrations
- M1-T3 — Agent Registration API: token generation, two-phase registration flow
- M1-T4 — Agent WebSocket Handler: connect, metrics ingestion, heartbeat, reconnect
- M1-T5 — Agent Package: refactor existing collector agent into modelprism-agent
- M1-T6 — Metric Storage + API: raw + downsampled storage, history query endpoints
- M1-T7 — Backend → Dashboard WebSocket Broadcast: metric and log streaming
- M1-T8 — Nuxt Dashboard Scaffold: Nuxt 4, PrimeVue, Tailwind, layouts, routing
- M1-T9 — Dashboard Pages: server overview + single server detail with real-time charts

## Dependencies

- **Blocks:** Milestone M2 (MVP Dashboard Enhancement)
- **Requires:** None (first milestone)
