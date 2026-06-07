# ModelPrism Roadmap

## Milestone 1: Foundation (Phases A+B)
**Goal:** Working agent registration, real-time metric pipeline, basic dashboard.

| Build Phase | Features | Estimated Effort |
|-------------|----------|------------------|
| A | F1–F5: Backend scaffolding, frontend scaffolding, DB schema, JSON:API layer, auth | ~3 weeks |
| B | F6–F13: Agent system (register, WS, metrics, logs, lifecycle) | ~4 weeks |

**Total:** ~7 weeks
**Definition of Done:**
- User can register and log in (email/password)
- User can generate agent token and install agent on a GPU server
- Agent appears in dashboard with live metrics (GPU util, VRAM, system resources)
- Agent logs stream to dashboard in real-time
- Agent handles disconnect/reconnect gracefully

**Risks:**
- WebSocket scaling at 10K connections — monitor early
- Docker GPU passthrough configuration — test on varied hardware

## Milestone 2: MVP (Phase C)
**Goal:** Usable GPU monitoring dashboard.

| Build Phase | Features | Estimated Effort |
|-------------|----------|------------------|
| C | F14–F17: Server overview, single server dashboard, WS broadcast, time range selector | ~3 weeks |

**Total:** ~10 weeks cumulative
**Definition of Done:**
- Dashboard shows all GPU servers with aggregate utilization
- Single server dashboard shows real-time charts, diagnostic cards, live logs
- Time range selector works for historical data
- Client-side batching prevents browser overload

## Milestone 3: Enhancement (Phases D+E)
**Goal:** Model deployment and benchmarking.

| Build Phase | Features | Estimated Effort |
|-------------|----------|------------------|
| D | F18–F23: HF Hub browser, deployment wizard, Docker deploy, model management, optimization rules | ~5 weeks |
| E | F24–F26: Benchmark runner, history, comparison | ~3 weeks |

**Total:** ~18 weeks cumulative
**Definition of Done:**
- User can browse HF Hub and deploy models with one click
- Deployment wizard shows live logs and GPU loading graph
- Running models can be stopped, restarted, deleted
- Benchmarking works end-to-end with comparison charts
- Optimization recommendations shown in dashboard

**Risks:**
- HF Hub download failures for large models — resumable download critical
- GPU memory estimation accuracy — mark as ±30%
- Docker GPU isolation on varied hardware configurations

## Milestone 4: Scale (Phases F+G)
**Goal:** Multi-tenant API proxy with workspace management.

| Build Phase | Features | Estimated Effort |
|-------------|----------|------------------|
| F | F27–F31: API key management, OpenAI proxy, token counting, rate limiting, routing | ~5 weeks |
| G | F32–F35: Workspace management, RBAC, data isolation, data retention config | ~3 weeks |

**Total:** ~26 weeks cumulative
**Definition of Done:**
- Users can create API keys scoped to models
- OpenAI-compatible proxy works with streaming and token counting
- Rate limiting prevents abuse
- Multiple workspaces with isolated data
- Role-based access works for all 4 roles
- Data retention configurable in settings

**Risks:**
- JSON:API adds complexity to all proxy-related endpoints
- Multi-tenant isolation regression risk — comprehensive test suite needed
- Streaming cost tracking accuracy under concurrent load

## Milestone 5: Growth (Phases H+I)
**Goal:** Billing and admin.

| Build Phase | Features | Estimated Effort |
|-------------|----------|------------------|
| H | F36–F39: Server hourly pricing, Stripe integration, billing dashboard, alerts | ~4 weeks |
| I | F40: Admin panel | ~2 weeks |

**Total:** ~32 weeks cumulative
**Definition of Done:**
- Server hourly pricing visible in settings and cost comparison charts
- Stripe metered billing works for cloud deployments
- Billing dashboard shows current spend and invoice history
- Billing alerts trigger at configurable thresholds
- Admin panel shows system-wide view

**Risks:**
- Stripe webhook idempotency bugs can double-charge users
- Open-source users may object to cloud-only billing code
- Self-hosted → cloud migration path must be documented

## Total Development Estimate: ~32 weeks (8 months) for full platform
- **Foundation (M1):** ~7 weeks
- **MVP (M2):** ~3 weeks (cumulative ~10)
- **Enhancement (M3):** ~8 weeks (cumulative ~18)
- **Scale (M4):** ~8 weeks (cumulative ~26)
- **Growth (M5):** ~6 weeks (cumulative ~32)
