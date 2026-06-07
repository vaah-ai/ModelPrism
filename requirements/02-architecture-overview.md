# Architecture Overview

## System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                   ModelPrism Platform                         │
│                    (hosted anywhere)                          │
│                                                              │
│  ┌──────────────────────┐   ┌─────────────────────────────┐  │
│  │   Nuxt 4 Frontend    │   │    FastAPI Backend           │  │
│  │                      │   │                              │  │
│  │  - Dashboard SPA     │   │  - REST API for frontend    │  │
│  │  - Model management  │   │  - WebSocket for live data  │  │
│  │  - Benchmark viewer  │   │  - PostgreSQL (primary DB)  │  │
│  │  - API key admin     │   │  - Redis (cache/rate-limit) │  │
│  │  - User management   │   │  - Stripe (billing)         │  │
│  │  - Billing UI        │   │  - OpenAI/Anthropic proxy   │  │
│  └──────────────────────┘   └──────────────┬──────────────┘  │
└────────────────────────────────────────────┼──────────────────┘
                                             │
                    Agent registration +     │
                    WebSocket metrics push   │
                    (outbound from agent)    │
                                             │
        ┌────────────────────────────────────┼──────────────┐
        │            GPU Server 1            │              │
        │                                    │              │
        │  ┌──────────────────────────────┐  │              │
        │  │     modelprism-agent          │  │              │
        │  │                               │  │              │
        │  │  - Registers with backend     │  │              │
        │  │  - Collects GPU metrics       │  │              │
        │  │  - Manages vLLM processes     │  │              │
        │  │  - Downloads HF models        │  │              │
        │  │  - Runs benchmarks            │  │              │
        │  └──────────────────────────────┘  │              │
        │                                    │              │
        │  ┌──────────────────────────────┐  │              │
        │  │     vLLM Instance(s)          │  │              │
        │  │     (one per deployed model)  │  │              │
        │  └──────────────────────────────┘  │              │
        └────────────────────────────────────┘              │
                                                            │
        ┌────────────────────────────────────┐               │
        │            GPU Server 2            │               │
        │            (same pattern)          │               │
        └────────────────────────────────────┘               │
                                                            │
        ┌────────────────────────────────────┐               │
        │            GPU Server N            │               │
        │            (same pattern)          │               │
        └────────────────────────────────────┘               │
```

## Deployment Models

### Option A: ModelPrism Cloud (SaaS)

- Frontend + Backend hosted by us
- Users install agents on their own GPU servers
- Agents connect back to our backend outbound
- User logs into dashboard and sees all their GPU servers

### Option B: Self-Hosted (Docker Compose)

- User deploys frontend + backend on their own infrastructure
- Separate docker-compose.yml for the platform itself
- Agents install on each GPU server and point to the self-hosted backend URL
- Full data sovereignty

### Option C: Hybrid (most common)

- Frontend hosted on Vercel/Cloudflare Pages (free)
- Backend hosted on a cheap VPS or one of the GPU servers
- Agents on all GPU servers
- Cheapest way to start

## Agent Registration Flow

1. User signs up on ModelPrism frontend
2. User generates an agent token from the dashboard
3. Frontend shows install command:
   ```bash
   curl -fsSL https://github.com/modelprism/agent/install.sh | \
     bash -s -- --server https://api.modelprism.io --token mp_abc123...
   ```
4. User runs command on any GPU server with NVIDIA GPUs
5. Agent downloads itself from GitHub releases (precompiled binary or Python package)
6. Agent calls backend: `POST /api/agents/register` with the token
7. Backend validates token, creates agent record with auto-generated name (e.g., `cyan-koala-42`)
8. Agent collects hardware info (GPU model, VRAM, CPU, RAM, disk, OS) and sends it
9. Agent opens persistent WebSocket connection for live metric streaming
10. GPU server appears in user's dashboard — ready for management

## Data Flow

### Real-Time Metrics

```
Agent (GPU Server)                  Backend                    Browser
     │                                │                          │
     │── WebSocket (connected) ──────►│                          │
     │                                │                          │
     │── { gpu_util: 87,             │                          │
     │     vram_used: 42.5,           │                          │
     │     running: 3,                │                          │
     │     ttft_p99: 450,             │                          │
     │     ... } (every 2s) ────────►│                          │
     │                                │── WebSocket ─────────────►│
     │                                │   (broadcast to browser)  │
     │                                │                          │
     │◄── { command: "deploy",       │                          │
     │      model: "...",             │                          │
     │      params: {...} } ──────────┤◄──── user clicks         │
     │                                │       "Deploy Model"     │
```

### Model Deployment Flow

```
User clicks "Deploy Model"
     │
     ▼
Frontend → POST /api/models/deploy { model_id, params, target_agent }
     │
     ▼
Backend validates params, checks capacity
     │
     ▼
Backend → WebSocket command to agent: { command: "deploy", ... }
     │
     ▼
Agent:
  1. Pulls model from HuggingFace Hub (with progress streamed back)
  2. Starts vLLM process with specified params
  3. Waits for health check (200 from /v1/models)
  4. Reports status back: "running", endpoint port
     │
     ▼
Frontend updates: model is live, metrics start flowing
```

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Backend language** | Python (FastAPI) | Shares ecosystem with agent. One language for control plane. |
| **Frontend** | Nuxt 4 + PrimeVue | Rich component library, auto-imports, excellent DX for dashboards. |
| **Agent language** | Python (compiled binary option future) | HuggingFace Hub, nvidia-smi, vLLM APIs are Python-native. |
| **Primary DB** | PostgreSQL | Migration-capable, supports JSON for flexible metric storage. |
| **Cache / rate-limit** | Redis | Standard. WebSocket pub/sub for broadcasting metrics. |
| **Agent-backend connection** | WebSocket (outbound from agent) | Agents behind NAT/firewalls; no inbound ports needed. |
| **Model runner** | vLLM (Docker or direct process) | Per-model container isolation or lightweight subprocess. |
| **Metric collection** | Agent polls nvidia-smi + vLLM /metrics locally | No external scraping needed. Agent bundles and pushes. |
| **Charts (real-time)** | uPlot (22KB) | Blazing fast for 2s update intervals on thousands of data points. |
| **Charts (comparison)** | ECharts | Richer chart types for benchmark comparisons and billing analytics. |
