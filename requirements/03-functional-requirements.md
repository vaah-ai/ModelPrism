# Functional Requirements

## F1 — Agent Management

### F1.1 Agent Registration
- User generates an agent token from the dashboard
- Token is a single-use registration credential
- Agent calls `POST /api/agents/register` with the token
- Backend validates token and assigns a random friendly name (e.g., `cyan-koala-42`)
- Agent collects and reports hardware specs:
  - GPU model(s), count, VRAM per GPU
  - CPU model, core count
  - RAM total and available
  - Disk total, used, and available
  - OS type and version
  - NVIDIA driver version
  - CUDA version
  - vLLM version (if installed)
- Backend stores hardware info and returns a persistent agent ID + WebSocket URL

### F1.2 Agent Connection
- Agent maintains persistent WebSocket to backend
- Reconnects with exponential backoff on disconnection
- Heartbeat/ping every 15 seconds
- Reports connection status to dashboard (online/offline/last-seen)
- Agent can be assigned a custom name by the user

### F1.3 Agent Lifecycle
- Agent can be paused (stop metric collection, keep vLLM running)
- Agent can be stopped (terminate agent process)
- Agent can be removed from the dashboard (deregister)
- Backend tracks agent uptime and version

### F1.4 Agent Auto-Discovery (Future)
- Scan local network for other GPU servers without agents
- Suggest installing the agent on discovered servers

## F2 — Real-Time Dashboard

### F2.1 GPU Server Overview
- List all registered GPU servers with:
  - Name, status (online/offline), GPU model, GPU count
  - Aggregate GPU utilization % across all GPUs
  - Total VRAM used / total VRAM available
  - Number of running models
  - Last seen timestamp

### F2.2 Single GPU Server Dashboard
- Header: server name, status indicator, GPU model, specs summary, uptime
- Charts (updated every 2 seconds via WebSocket):
  - Throughput (tok/s over time)
  - Tokens in/out (cumulative over time)
  - Requests (running vs waiting over time)
  - Total tokens (cumulative over time)
  - Cost comparison (self-hosted vs Claude API)
- Diagnostic cards:
  - Queue depth (running/waiting/total requests)
  - KV cache utilization
  - Bottleneck indicator (idle/seqcap/scheduler/GPU-bound)
  - TTFT p50 and p99
  - Running models list
  - Error rate and truncation rate
- System resources:
  - GPU utilization %
  - VRAM used / total + bar
  - RAM used / total + bar
  - CPU utilization + load averages
  - Disk used / total + bar
  - HF cache size
  - GPU temperature and power draw
- Live log: recent events (deployments, errors, queue changes)

### F2.3 Time Range Selector
- Live (2s intervals, last 5 minutes)
- 5 minutes, 1 hour, 6 hours, 12 hours
- 1 day, 1 week, 1 month, 3 months, 6 months, 1 year, all time
- Data downsampled automatically for longer ranges

### F2.4 Multi-Instance Support
- Track multiple vLLM instances on the same GPU server
- Each instance gets its own metric stream
- Tab-based switching between instances
- Port scan for discovering untracked vLLM instances

## F3 — Model Management

### F3.1 HuggingFace Hub Browser
- Search models from HuggingFace Hub
- Filter by task (text-generation, image-generation, etc.)
- Filter by library (transformers, diffusers, etc.)
- Filter by parameter count range
- Sort by downloads, likes, trending
- View model details: description, architecture, parameter count, license, required VRAM estimate
- One-click "Deploy" action from search results

### F3.2 Model Deployment
- Deployment wizard (stepper UI):
  - Step 1: Select model (or search/paste HF ID)
  - Step 2: Select target GPU server
  - Step 3: Configure vLLM parameters:
    - Tensor parallel size
    - Pipeline parallel size
    - Quantization (none, AWQ, GPTQ, FP8, etc.)
    - Max model length / context window
    - Max number of sequences
    - GPU memory utilization
    - KV cache dtype
    - Enable prefix caching
    - Enforce eager mode
    - Served model name (API alias)
  - Step 4: Capacity calculator shows estimated:
    - VRAM required
    - Max concurrent requests at full context
    - Max concurrent requests at estimated average context
    - KV cache budget remaining
  - Step 5: Review and deploy
- Model download progress bar streamed from agent
- Health check after deployment (confirm /v1/models responds)
- Model appears in running models list once healthy

### F3.3 Running Model Management
- List all deployed models across all GPU servers
- Per-model details:
  - Current request count (running/waiting)
  - Token throughput (tok/s)
  - GPU utilization
  - KV cache utilization
  - TTFT stats
  - Uptime
  - Configuration snapshot (all vLLM params used)
- Controls:
  - Stop model (graceful shutdown)
  - Restart model
  - View logs
  - Update config (some params hot-swappable, some require restart)
  - Delete model (stop + remove)

### F3.4 Model Optimization Recommendations
- Smart analysis based on observed metrics:
  - "Your average context length is 8K but max_model_len is 128K → reduce to save VRAM"
  - "KV cache headroom is 80% → consider deploying a second model on this GPU"
  - "Prefix cache hit rate is low → enable --enable-prefix-caching for your workload"
  - "GPU utilization < 30% → reduce tensor-parallel size or increase batch concurrency"
  - "Queue depth is consistently high → increase max_num_seqs or add another GPU"
  - "Error rate is non-zero → check model compatibility or increase swap space"
- Each recommendation includes expected impact and one-click apply

## F4 — Benchmarking

### F4.1 Benchmark Runner
- Trigger benchmark on a deployed model
- Configuration options:
  - Number of requests (100, 500, 1000, 5000)
  - Concurrency level (1, 5, 10, 50, 100)
  - Request rate (fixed rate or max throughput)
  - Input length distribution (fixed, ShareGPT, synthetic)
  - Output token count (fixed or random range)
  - Dataset (ShareGPT, sonnet, custom JSONL upload)
- Benchmark runs on the GPU server agent
- Results streamed in real-time to dashboard
- Metrics collected:
  - TTFT (mean, median, P50, P95, P99)
  - TPOT (mean, median, P50, P95, P99)
  - ITL (inter-token latency)
  - End-to-end latency (mean, median, P99)
  - Throughput (requests/sec, tokens/sec)
  - Total tokens processed
  - Error count and rate

### F4.2 Benchmark History and Comparison
- Save every benchmark run with full config and results
- View benchmark history as a table
- Compare two or more benchmark runs side-by-side
  - Same model, different configs
  - Different models on same hardware
  - Same model, different hardware
- Visual comparison charts:
  - Bar chart: TTFT P50 and P99 across runs
  - Bar chart: Throughput (tok/s) across runs
  - Scatter: latency vs throughput tradeoff
  - Radar chart: multi-metric comparison

### F4.3 Scheduled Benchmarks (Future)
- Schedule recurring benchmarks
- Automatically benchmark after model config changes
- Regression detection: alert if performance drops below threshold

## F5 — API Proxy (Multi-Tenant)

### F5.1 API Key Management
- Generate OpenAI-compatible API keys (`sk-...` format)
- Keys are hashed in storage (only prefix stored in plaintext for lookup)
- Key scoping:
  - Per-model or all models
  - Per-team or per-user
  - Rate limit per key (requests/min, tokens/min)
- Key revocation (instant, soft-delete in DB)
- Key rotation support

### F5.2 OpenAI-Compatible Proxy
- `POST /v1/chat/completions` — proxy to self-hosted vLLM or OpenAI
- `POST /v1/completions` — proxy to self-hosted vLLM or OpenAI
- `GET /v1/models` — list available models
- Authentication: `Authorization: Bearer sk-...`
- Rate limiting: sliding window per key + per IP (Redis)
- Token counting: intercept request/response, count with tiktoken
- Streaming support: pass SSE chunks through with usage tracking
- Route to correct upstream (self-hosted vLLM vs OpenAI vs Anthropic)

### F5.3 Anthropic-Compatible Proxy (Future)
- Additional endpoint for Anthropic API format
- Unified key management across providers

### F5.4 Usage Tracking
- Per-key: token counts (prompt + completion), request count, cost accrued
- Per-model: aggregate usage, popular models, peak concurrency
- Per-user/team: aggregate across all keys
- Time range filtering (today, 7 days, 30 days, custom)
- Usage export (CSV, JSON)
- Usage alerts (threshold-based email/webhook notifications)
- Cost breakdown: self-hosted costs vs cloud API costs

## F6 — User Management

### F6.1 Authentication
- Email/password registration and login
- OAuth (Google, GitHub) for frictionless onboarding
- JWT-based sessions with refresh tokens
- Session management (view active sessions, revoke)

### F6.2 User Roles
- **Owner:** Full access, billing, team management, delete platform
- **Admin:** Manage models, API keys, invite users, view all usage
- **Member:** Deploy models, create API keys, view own usage
- **Viewer:** Read-only dashboard access

### F6.3 Team/Workspace Multi-Tenancy
- Users belong to one or more workspaces
- Each workspace has isolated: GPU servers, models, API keys, billing
- Workspace owner can invite members by email (magic link)
- Invite code option for open-source self-hosted instances
- Role assignment per user within workspace

### F6.4 Profile and Settings
- User profile (name, email, avatar, preferences)
- Notification settings (email alerts for key events)
- API tokens for programmatic access to the management API
- Theme (dark/light mode)

## F7 — Billing

### F7.1 Usage-Based Billing (Cloud)
- Stripe integration for metered billing
- Pricing model options:
  - Per-token (input tokens @ $X/MTok, output tokens @ $Y/MTok)
  - Per-second GPU compute
  - Tiered pricing (volume discounts)
  - Monthly credit packages
- Stripe Meter Events for token usage reporting
- Automatic invoice generation at end of billing period
- Payment method management (Stripe customer portal)
- In-app billing dashboard: current month usage, estimated cost, invoice history

### F7.2 Self-Hosted (No Billing)
- Billing features are disabled/hidden in self-hosted mode
- All other features are fully functional
- Clear documentation on what features require cloud vs self-hosted

### F7.3 Billing Alerts
- Usage threshold alerts (email when spend exceeds $X)
- Budget caps (optional hard stop on API proxy usage)
- Invoice payment failure handling
