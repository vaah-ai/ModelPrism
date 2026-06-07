# Repository Structure

```
modelprism/
│
├── frontend/                      # Nuxt 4 application
│   ├── app/
│   │   ├── app.vue
│   │   ├── layouts/
│   │   │   ├── default.vue
│   │   │   └── dashboard.vue      # Authenticated dashboard layout
│   │   ├── pages/
│   │   │   ├── index.vue           # Landing / marketing
│   │   │   ├── login.vue
│   │   │   ├── register.vue
│   │   │   ├── pricing.vue
│   │   │   └── dashboard/
│   │   │       ├── index.vue       # GPU server overview
│   │   │       ├── servers/
│   │   │       │   └── [id].vue    # Single GPU server dashboard
│   │   │       ├── models/
│   │   │       │   ├── index.vue   # All models
│   │   │       │   ├── deploy.vue  # Deploy wizard
│   │   │       │   └── [id].vue    # Model details
│   │   │       ├── benchmarks/
│   │   │       │   ├── index.vue   # Benchmark history
│   │   │       │   ├── new.vue     # New benchmark
│   │   │       │   └── [id].vue    # Benchmark results + comparison
│   │   │       ├── keys/
│   │   │       │   └── index.vue   # API key management
│   │   │       ├── usage/
│   │   │       │   └── index.vue   # Usage tracking + billing
│   │   │       ├── settings/
│   │   │       │   ├── index.vue   # Workspace settings
│   │   │       │   ├── members.vue # Team management
│   │   │       │   └── billing.vue # Billing settings
│   │   │       └── admin/
│   │   │           └── index.vue   # Admin panel (owner only)
│   │   ├── components/
│   │   │   ├── dashboard/
│   │   │   │   ├── GpuMetricsChart.vue
│   │   │   │   ├── SystemResources.vue
│   │   │   │   ├── QueueDiagnostics.vue
│   │   │   │   ├── ModelList.vue
│   │   │   │   └── LiveLog.vue
│   │   │   ├── models/
│   │   │   │   ├── DeployWizard.vue
│   │   │   │   ├── CapacityCalculator.vue
│   │   │   │   ├── ModelConfigForm.vue
│   │   │   │   └── ModelCard.vue
│   │   │   ├── benchmarks/
│   │   │   │   ├── BenchmarkTable.vue
│   │   │   │   ├── BenchmarkComparison.vue
│   │   │   │   └── BenchmarkConfig.vue
│   │   │   ├── keys/
│   │   │   │   └── ApiKeyList.vue
│   │   │   ├── users/
│   │   │   │   └── MemberList.vue
│   │   │   └── common/
│   │   │       ├── MetricCard.vue
│   │   │       ├── StatusBadge.vue
│   │   │       └── TimeRangeSelector.vue
│   │   └── composables/
│   │       ├── useWebSocketMetrics.ts
│   │       ├── useAgents.ts
│   │       └── useModels.ts
│   ├── server/
│   │   └── api/                    # Nitro API routes (thin — auth session only)
│   │       └── auth/
│   │           └── session.get.ts
│   ├── stores/
│   │   ├── metrics.ts              # Pinia store for live metrics
│   │   ├── agents.ts               # Agent list store
│   │   ├── models.ts               # Deployed models store
│   │   └── user.ts                 # Auth/user store
│   ├── nuxt.config.ts
│   ├── package.json
│   └── tsconfig.json
│
├── backend/                        # FastAPI backend
│   ├── app/
│   │   ├── main.py                 # FastAPI app entry, lifespan events
│   │   ├── config.py               # Settings (pydantic-settings)
│   │   ├── database.py             # SQLAlchemy engine + session
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   │   ├── user.py
│   │   │   ├── workspace.py
│   │   │   ├── agent.py
│   │   │   ├── model_deployment.py
│   │   │   ├── api_key.py
│   │   │   ├── usage_record.py
│   │   │   ├── benchmark.py
│   │   │   └── billing.py
│   │   ├── schemas/                # Pydantic request/response schemas
│   │   │   ├── agent.py
│   │   │   ├── model.py
│   │   │   ├── benchmark.py
│   │   │   ├── user.py
│   │   │   ├── key.py
│   │   │   └── usage.py
│   │   ├── api/                    # Route handlers
│   │   │   ├── auth.py
│   │   │   ├── agents.py
│   │   │   ├── metrics.py
│   │   │   ├── models.py
│   │   │   ├── benchmarks.py
│   │   │   ├── keys.py
│   │   │   ├── usage.py
│   │   │   ├── billing.py
│   │   │   ├── users.py
│   │   │   └── proxy.py            # OpenAI/Anthropic proxy
│   │   ├── services/               # Business logic
│   │   │   ├── agent_manager.py
│   │   │   ├── model_manager.py
│   │   │   ├── benchmark_runner.py
│   │   │   ├── usage_tracker.py
│   │   │   ├── billing_service.py
│   │   │   └── proxy_service.py
│   │   ├── ws/                     # WebSocket handlers
│   │   │   ├── agent_ws.py         # Agent connection handler
│   │   │   └── dashboard_ws.py     # Dashboard broadcast handler
│   │   ├── middleware/
│   │   │   ├── auth.py             # JWT/auth middleware
│   │   │   └── rate_limit.py       # Redis rate limiting
│   │   └── utils/
│   │       ├── crypto.py           # Hashing, token generation
│   │       └── naming.py           # Random name generator
│   ├── alembic/                    # Database migrations
│   ├── tests/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── pyproject.toml
│
├── agent/                          # modelprism-agent (runs on GPU servers)
│   ├── modelprism_agent/
│   │   ├── __init__.py
│   │   ├── main.py                 # Entry point
│   │   ├── config.py               # Agent settings
│   │   ├── registration.py         # Register with backend
│   │   ├── metrics/
│   │   │   ├── collector.py        # Main metric collection orchestrator
│   │   │   ├── gpu.py              # nvidia-smi parsing
│   │   │   ├── system.py           # CPU, RAM, disk (psutil)
│   │   │   └── vllm.py             # vLLM Prometheus metrics parser
│   │   ├── manager/
│   │   │   ├── vllm_manager.py     # Spawn/kill vLLM processes
│   │   │   └── model_downloader.py # HF Hub model download with progress
│   │   ├── benchmark/
│   │   │   ├── runner.py           # Run benchmarks against local vLLM
│   │   │   └── scenarios.py        # Predefined benchmark scenarios
│   │   ├── connection.py           # WebSocket client to backend
│   │   ├── command_handler.py      # Process commands from backend
│   │   └── utils/
│   │       ├── prometheus_parser.py
│   │       └── hf_utils.py
│   ├── tests/
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── Dockerfile
│
├── common/                         # Shared code between backend + agent
│   ├── pyproject.toml
│   └── modelprism_common/
│       ├── schemas/                # Shared Pydantic models
│       │   ├── metrics.py
│       │   ├── commands.py
│       │   └── events.py
│       └── __init__.py
│
├── deploy/
│   ├── docker-compose.yml          # Full self-hosted stack
│   ├── nginx/
│   │   └── modelprism.conf
│   └── install.sh                  # Quick self-hosted install script
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── INSTALL.md
│   ├── AGENT_SETUP.md
│   ├── API.md
│   └── CONTRIBUTING.md
│
├── .github/
│   ├── workflows/
│   │   ├── backend-ci.yml
│   │   ├── frontend-ci.yml
│   │   ├── agent-ci.yml
│   │   └── release.yml
│   └── ISSUE_TEMPLATE/
│
├── requirements/                   # This folder — product requirements
├── README.md
└── LICENSE
```
