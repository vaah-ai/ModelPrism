# Architecture Overview

## System Architecture

```
+----------------------------------------------------------------+
|                   ModelPrism Platform                             |
|                    (hosted anywhere)                              |
|                                                                  |
|  +------------------------+   +-------------------------------+  |
|  |   Nuxt 4 Frontend      |   |    FastAPI Backend             |  |
|  |                        |   |                                |  |
|  |  - Dashboard SPA       |   |  - REST API (JSON:API)        |  |
|  |  - Model management    |   |  - WebSocket for live data    |  |
|  |  - Benchmark viewer    |   |  - PostgreSQL (primary DB)    |  |
|  |  - API key admin       |   |  - Redis (cache/rate-limit)   |  |
|  |  - User management     |   |  - Stripe (billing, cloud)    |  |
|  |  - Billing UI (cloud)  |   |  - OpenAI API proxy          |  |
|  +------------------------+   +---------------+--------------+  |
+----------------------------------------------------+-----------+
                                                     |
           Agent registration + WebSocket metrics    |
           push + log streaming (outbound from agent)|
                                                     |
     +-----------------------------------------------+-----------+
     |                    GPU Server 1                           |
     |                                                          |
     |  +----------------------------------------------------+  |
     |  |     modelprism-agent                                |  |
     |  |                                                     |  |
     |  |  - Registers with backend (REST)                    |  |
     |  |  - Collects GPU metrics (nvidia-smi)                |  |
     |  |  - Collects system metrics (psutil)                 |  |
     |  |  - Pushes metrics over WebSocket (every 2s)         |  |
     |  |  - Manages vLLM via Docker containers               |  |
     |  |  - Downloads HF Hub models (resumable)              |  |
     |  |  - Streams logs to backend (HTTP POST)              |  |
     |  |  - Runs benchmarks                                 |  |
     |  +----------------------------------------------------+  |
     |                                                          |
     |  +----------------------------------------------------+  |
     |  |     vLLM Container(s)                                |  |
     |  |     (one per deployed model, Docker isolated)        |  |
     |  |     - GPU device reservation                        |  |
     |  |     - Memory limits                                 |  |
     |  |     - Port mapping                                  |  |
     |  |     - Health checking                               |  |
     |  +----------------------------------------------------+  |
     +----------------------------------------------------------+

     +----------------------------------------------------------+
     |                    GPU Server 2                            |
     |                    (same pattern)                         |
     +----------------------------------------------------------+

     +----------------------------------------------------------+
     |                    GPU Server N                            |
     |                    (same pattern)                         |
     +----------------------------------------------------------+
```

## Deployment Models

### Option A: ModelPrism Cloud (SaaS)

- Frontend + Backend hosted by us (not on Vercel — dedicated VPS or cloud provider)
- Users install agents on their own GPU servers
- Agents connect back to our backend outbound
- User logs into dashboard and sees all their GPU servers
- Full feature set including API proxy, multi-tenancy, billing

### Option B: Self-Hosted (Docker Compose)

- User deploys frontend + backend on their own infrastructure
- Separate docker-compose.yml for the platform itself
- Agents install on each GPU server and point to the self-hosted backend URL
- Full data sovereignty
- Billing features disabled/hidden

### Option C: Hybrid (most common)

- Frontend + Backend hosted on a cheap VPS or one of the GPU servers
- Agents on all GPU servers
- Cheapest way to start with self-hosted control

## API Standards

### REST API (Dashboard + Agent Registration)
- **JSON:API 1.0** format (`application/vnd.api+json`)
- All dashboard resource endpoints: agents, models, deployments, benchmarks, users, workspaces, keys, usage
- Agent registration endpoint follows JSON:API
- Auth endpoints (login, register, refresh) use standard `application/json` (JSON:API exception)

### Agent WebSocket Protocol
- **Lightweight custom format** (not JSON:API)
- Type-discriminated messages: `metrics`, `vllm_metrics`, `heartbeat`, `command`, `command_progress`, `command_result`
- Flat JSON payload — no envelope overhead
- MessagePack or CBOR encoding considered for production at scale

### Agent Log Streaming
- Agent pushes log entries via HTTP POST to FastAPI endpoint
- Endpoint: `POST /api/agents/{agent_id}/logs`
- Log levels: `debug`, `info`, `warning`, `error`
- Streamed to dashboard in real-time via WebSocket broadcast

### Public API Proxy
- OpenAI-compatible format (`/v1/chat/completions`, `/v1/completions`, `/v1/models`)
- Standard JSON — NOT JSON:API
- Bearer auth with `sk-` prefixed API keys

## Agent Registration Flow

1. User signs up on ModelPrism frontend (email/password auth)
2. User generates an agent token from the dashboard
3. Frontend shows install command:
   ```bash
   curl -fsSL https://github.com/modelprism/agent/install.sh | \
     bash -s -- --server https://api.modelprism.io --token mp_abc123...
   ```
4. User runs command on any GPU server with NVIDIA GPUs
5. Agent downloads itself from GitHub releases (precompiled binary or Python package)
6. Agent calls backend: `POST /api/agents/register` with the token
7. Backend validates token (two-phase: Claim → Complete, 5-min timeout rollback)
8. Backend creates agent record with auto-generated name (e.g., `cyan-koala-42`)
9. Agent collects hardware info (GPU model, VRAM, CPU, RAM, disk, OS) and sends it
10. Agent opens persistent WebSocket connection for live metric streaming
11. GPU server appears in user's dashboard — ready for management

## Data Flow

### Real-Time Metrics

```
Agent (GPU Server)                  Backend                    Browser
     |                                |                          |
     |-- WebSocket (connected) ------>|                          |
     |                                |                          |
     |-- { gpu_util: 87,             |                          |
     |     vram_used: 42.5,           |                          |
     |     running: 3,                |                          |
     |     ttft_p99: 450,             |                          |
     |     ... } (every 2s) -------->|                          |
     |                                |-- WebSocket ----------->|
     |                                |   (broadcast to browser) |
     |                                |                          |
     |<-- { command: "deploy",       |                          |
     |      model: "...",             |                          |
     |      params: {...} } ----------|<---- user clicks         |
     |                                |       "Deploy Model"     |
     |                                |                          |
     |-- POST /api/agents/{id}/logs  |                          |
     |    { level: "error",          |-- broadcast to browser ->|
     |      msg: "OOM detected" } --->|                          |
```

### Model Deployment Flow

```
User clicks "Deploy Model"
     |
     v
Frontend --> POST /api/models/deploy { model_id, params, target_agent }
     |
     v
Backend validates params, checks capacity per GPU server
     |
     v
Backend --> WebSocket command to agent: { command: "deploy_model", ... }
     |
     v
Agent:
  1. Pulls model from HuggingFace Hub (resumable, with progress streamed)
  2. Logs each step (visible in deployment log viewer)
  3. Starts nvtop/gpu monitoring (graph visible in UI)
  4. Launches Docker container: vLLM + model
  5. Waits for health check (200 from /v1/models)
  6. Reports status: "running", endpoint port, container ID
     |
     v
Frontend updates: model is live, metrics start flowing
```

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Backend language** | Python (FastAPI) | Shares ecosystem with agent. One language for control plane. |
| **Frontend** | Nuxt 4 + PrimeVue | Rich component library, auto-imports, excellent DX for dashboards. |
| **Agent language** | Python | HuggingFace Hub, nvidia-smi, vLLM APIs are Python-native. |
| **API format (dashboard)** | JSON:API 1.0 | Standardized, self-documenting REST. |
| **API format (agent WS)** | Lightweight custom format | No JSON:API overhead on 2s metric pushes. |
| **Auth** | Email/password + JWT | Simple, no external dependencies. Custom Pinia composable. |
| **Model runner** | vLLM in Docker (mandatory) | Process isolation, GPU device reservation, resource limits. |
| **Deployment** | Dedicated VPS or bare metal (NOT Vercel) | WebSocket persistence, full server control. |
| **Primary DB** | PostgreSQL | Migration-capable, supports JSON for flexible metric storage. |
| **Cache / rate-limit** | Redis | Standard. WebSocket pub/sub for broadcasting metrics. |
| **Agent-backend connection** | WebSocket (outbound from agent) | Agents behind NAT/firewalls; no inbound ports needed. |
| **Metric collection** | Agent polls nvidia-smi + vLLM /metrics locally | No external scraping needed. Agent bundles and pushes. |
| **Log streaming** | Agent -> HTTP POST -> DB -> WS broadcast | Real-time logs visible in deployment view and dashboard. |
| **Charts (real-time)** | uPlot (22KB) | Blazing fast for 2s update intervals on thousands of data points. |
| **Charts (comparison)** | ECharts | Richer chart types for benchmark comparisons and billing analytics. |
| **Monetization** | Open core | Core OSS, cloud-only paid features separate. |
| **Self-hosted detection** | `MODELPRISM_CLOUD` env var | Single config toggle. |
