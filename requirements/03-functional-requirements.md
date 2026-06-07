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

### F1.4 Agent Log Streaming
- Agent pushes log entries to backend via HTTP POST: `POST /api/agents/{agent_id}/logs`
- Log levels: `debug`, `info`, `warning`, `error`
- Log entries include: timestamp, level, module, message, optional stack trace
- Backend stores logs in PostgreSQL (configurable retention per workspace)
- Backend broadcasts logs to dashboard via WebSocket in real-time
- Dashboard shows live log viewer per agent with level filtering
- Logs visible during model deployment to track progress
- Special focus on `error` and `warning` level logs for debugging

### F1.5 Agent Auto-Discovery (Future)
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
- Live log viewer: streaming log entries from agent with real-time filtering
  - Severity filter (debug/info/warning/error)
  - Search within logs
  - Auto-scroll with pause capability

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
- **Live deployment log viewer** — real-time streaming of agent logs during deployment
  - Shows download progress, Docker container startup, vLLM initialization
  - Color-coded by log level (error=red, warning=yellow, info=white, debug=gray)
- **nvtop GPU monitoring graph** during model loading
  - Real-time GPU utilization, VRAM usage, temperature
  - Visible in deployment progress panel alongside log viewer
  - Helps user see model loading onto GPU in real-time
- Health check after deployment (confirm /v1/models responds)
- Model appears in running models list once healthy

### F3.3 Running Model Management
- All vLLM instances run in **Docker containers** (mandatory, not optional)
  - Each model gets its own container
  - GPU device reservation via `--gpus` flag
  - Memory limits enforced via Docker
  - Port mapping via atomic port allocation table
  - Container health checking via /v1/models endpoint (every 10s)
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
- **Email/password** registration and login (simple, no OAuth)
- Password hashed with bcrypt (cost factor 12)
- Minimum password length: 8 characters (no complexity rules)
- JWT-based sessions: access token (15 min expiry), refresh token (7 day expiry)
- Refresh token rotation (old token invalidated on use)
- Password reset flow: email with time-limited token (15 min expiry)
- Account lockout: 5 failed attempts → 1 hour lock
- Session management (view active sessions, revoke)
- Auth frontend: custom Pinia composable calling FastAPI JWT endpoints directly (no sidebase/nuxt-auth)

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
- User profile (name, email, preferences)
- Notification settings (email alerts for key events)
- API tokens for programmatic access to the management API
- Theme (dark/light mode)

### F6.5 Workspace Settings — Data Retention
- Configurable per workspace in Settings UI
- Retention periods for each data tier:
  - **Raw metrics** (2s resolution): configurable 1h to 48h (default: 24h)
  - **Aggregated metrics** (1m): configurable 7d to 90d (default: 30d)
  - **Historical metrics** (5m): configurable 30d to 365d (default: 1y)
  - **Logs**: configurable 7d to 90d (default: 30d)
  - **Usage records**: fixed 7 years (tax/compliance)
- User-friendly slider/dropdown per retention category
- Warning shown when reducing retention (data will be permanently deleted)
- Background cleanup job runs daily to enforce retention policies

## F7 — Billing

### F7.1 Server Hourly Pricing Configuration
- Per-GPU-server hourly pricing configuration (flat rate per server)
- User sets per-server hourly rate in the agent settings panel
  - Used for internal cost calculations and "cost comparison" dashboard metrics
  - Example: user sets "$2.50/hr" for a server with 4xA100 GPUs
- Cost comparison chart: self-hosted cost (hours × hourly rate) vs cloud API costs
- Pricing configurable per workspace in Settings UI
- This is a utility/monitoring feature — NOT connected to Stripe

### F7.2 Usage-Based Billing (Cloud — open-core exclusive)
- Stripe integration for metered billing
- Pricing model: per-token (input tokens + output tokens counted separately)
  - Default: $0.10/1M input tokens, $0.40/1M output tokens (configurable)
- Stripe Meter Events for token usage reporting
- Metering reported to Stripe every hour in batches
- On Stripe failure: queue locally, retry with backoff, continue serving inference
- Automatic invoice generation at end of billing period
- Payment method management (Stripe customer portal)
- In-app billing dashboard: current month usage, estimated cost, invoice history

### F7.3 Self-Hosted (No Billing)
- Billing features are disabled/hidden when `MODELPRISM_CLOUD=false`
- All other features are fully functional
- Server hourly pricing still visible (used for cost comparison charts)
- Clear documentation on what features require cloud vs self-hosted

### F7.4 Billing Alerts
- Usage threshold alerts (email when spend exceeds $X)
- Monthly spend cap per workspace (email alert at 50%, 80%, 100% of cap)
- Budget caps (optional hard stop on API proxy usage)
- Invoice payment failure handling
- In-app notification bar at 90%+ threshold
