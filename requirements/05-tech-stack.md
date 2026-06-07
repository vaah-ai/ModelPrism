# Tech Stack

## Frontend

| Technology | Purpose | Rationale |
|------------|---------|-----------|
| **Nuxt 4** | Full-stack framework | SSR for landing pages, SPA for dashboard, file-based routing, auto-imports |
| **PrimeVue 4** | UI component library | 90+ components, auto-import with Nuxt, Sakai admin template |
| **Tailwind CSS v4** | Styling | Utility-first, works seamlessly with Nuxt and PrimeVue |
| **uPlot** | Real-time GPU charts | 22KB gzip, renders 150 points in ~5ms, built for 2s interval updates |
| **ECharts** | Benchmark/billing charts | Candlestick, radar, heatmap, comparison views |
| **Pinia** | State management | Vue 3 native, WebSocket-connected stores for real-time data |
| **VueUse** | Composable utilities | `useWebSocket`, `useIntervalFn`, `useStorage`, `useRefHistory` |
| **Nuxt Auth** | Authentication | Custom Pinia composable calling FastAPI JWT directly (no sidebase/nuxt-auth) |
| **VeeValidate + Zod** | Form validation | Type-safe model deployment form wizard validation |
| **JSON:API** | API format | `application/vnd.api+json` for all dashboard REST endpoints |
| **TypeScript** | Type safety | Full type coverage across frontend |

## Backend

| Technology | Purpose | Rationale |
|------------|---------|-----------|
| **FastAPI** | Web framework | Async, Pydantic validation, auto OpenAPI docs, WebSocket support |
| **SQLAlchemy 2.0 + Alembic** | ORM + migrations | Async-ready, type-safe, mature ecosystem |
| **PostgreSQL** | Primary database | JSON columns for metric data, reliable, migration-capable |
| **Redis** | Cache, rate limiting, pub/sub | WebSocket broadcast, session cache, rate limit counters |
| **Pydantic v2** | Data validation | Shared schemas between backend and agent |
| **httpx** | Async HTTP client | OpenAI/Anthropic proxy with streaming |
| **stripe** | Billing | Usage-based metering, checkout, webhooks |
| **uvicorn** | ASGI server | Production-grade async server. gunicorn with uvicorn workers for multi-process |
| **python-jose** | JWT tokens | Auth token generation and validation |

## Agent (modelprism-agent)

| Technology | Purpose | Rationale |
|------------|---------|-----------|
| **Python 3.10+** | Runtime | ML ecosystem native language |
| **httpx** | Async HTTP + WebSocket client | Connect back to backend, stream metrics |
| **huggingface_hub** | Model download | `snapshot_download()`, `model_info()`, `list_models()` with progress |
| **websockets** or **httpx-ws** | WebSocket client | Persistent connection to backend |
| **nvidia-smi (subprocess)** | GPU metrics | Parse XML/CSV output for GPU stats |
| **psutil** | System metrics | CPU, RAM, disk, network |
| **vLLM** | Inference engine | Launched as subprocess or Docker container per model |
| **subprocess** | Process management | Spawn/kill vLLM processes, run benchmarks |
| **PyInstaller** or **Nuitka** (optional) | Binary packaging | Bundle agent into single executable for curl-to-bash install |

## Optional / Future

| Technology | Purpose | When |
|------------|---------|------|
| **Go** | Agent rewrite | If agent needs to be a single ~10MB binary with no Python dependency |
| **Grafana** | Advanced dashboards | Power users who want Grafana's richer panels alongside ModelPrism |
| **Prometheus** | Scrape vLLM /metrics directly | Alternative metric collection path, complementary to agent push |
| **TimescaleDB** | Time-series extension for PostgreSQL | If metric retention at high fidelity becomes a concern |
| **MinIO / S3** | Model weight storage | For caching/downloaded model storage across GPU servers |
| **Kubernetes** | Orchestration | If managing at very large scale (100+ GPU servers) |
| **Docker** | vLLM container isolation | Recommended: one container per model for isolation |

## Development Tooling

| Tool | Purpose |
|------|---------|
| **uv/pip** | Python dependency management |
| **pnpm** | Node.js dependency management |
| **ruff** | Python linter + formatter |
| **prettier** | TypeScript/CSS formatter |
| **pytest** | Python test runner |
| **vitest** | Vue component test runner |
| **mypy** | Python type checking |
| **Docker Compose** | Local development environment (PostgreSQL, Redis) |
| **GitHub Actions** | CI/CD, Docker image publishing, release automation |
