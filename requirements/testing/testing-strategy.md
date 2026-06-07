# Testing Strategy — ModelPrism

> **Version:** 1.0  
> **Status:** Draft  
> **Last updated:** 2026-06-07

---

## Table of Contents

1. [Testing Philosophy & Pyramid](#1-testing-philosophy--pyramid)
2. [Project Structure for Tests](#2-project-structure-for-tests)
3. [Backend Testing (FastAPI + SQLAlchemy + Pydantic)](#3-backend-testing)
4. [Frontend Testing (Nuxt 4 + TypeScript + PrimeVue)](#4-frontend-testing)
5. [Agent Testing (Python 3.10+ GPU Agent)](#5-agent-testing)
6. [JSON:API Response Schema Validation](#6-jsonapi-response-schema-validation)
7. [WebSocket Testing Strategy](#7-websocket-testing-strategy)
8. [End-to-End Testing (Playwright)](#8-end-to-end-testing-playwright)
9. [Integration Test Environments](#9-integration-test-environments)
10. [CI Pipeline (GitHub Actions)](#10-ci-pipeline-github-actions)
11. [Coverage Targets & Enforcement](#11-coverage-targets--enforcement)
12. [Test Data & Fixtures](#12-test-data--fixtures)
13. [Performance & Load Testing](#13-performance--load-testing)
14. [Security Testing](#14-security-testing)
15. [Glossary](#15-glossary)

---

## 1. Testing Philosophy & Pyramid

### 1.1 Guiding Principles

- **Test behavior, not implementation.** Assert against observable outcomes (HTTP status, JSON structure, database state, UI rendering), not internal function calls or private methods.
- **Parity between environments.** The same fixture/data patterns work in CI, local dev, and review apps.
- **Deterministic by default.** No tests rely on wall-clock timing, random port assignment, or external network availability without explicit fixtures that control those variables.
- **Speed tiers.** Unit tests complete in seconds, integration tests in minutes, E2E tests run in CI only.
- **JSON:API compliance is a hard constraint.** Every backend test that touches a Dashboard REST endpoint validates the response against a JSON:API 1.0 schema contract.

### 1.2 Testing Pyramid

```
          ╱╲
         ╱  ╲
        ╱ E2E╲            Playwright (frontend + backend)
       ╱──────╲
      ╱Integration╲        Docker compose: backend + postgres + redis + agent
     ╱────────────╲        vLLM container integration (agent)
    ╱  API / Contract  ╲   httpx against FastAPI test client
   ╱────────────────────╲  JSON:API schema assertions
  ╱    Unit / Component   ╲  pytest (backend), vitest (frontend)
 ╱─────────────────────────╲ Mocked dependencies, fast feedback
╰───────────────────────────╯
```

| Layer | Technology | Speed Goal | Runs in | Target Coverage |
|---|---|---|---|---|
| **Unit (Backend)** | pytest + pytest-asyncio | < 5s | Every commit | 80%+ |
| **Unit (Frontend)** | vitest + vue-test-utils | < 10s | Every commit | 70%+ |
| **Unit (Agent)** | pytest + mocked nvidia-smi | < 5s | Every commit | 80%+ |
| **API / Contract** | httpx + FastAPI TestClient | < 30s | Every PR | Validates all endpoints |
| **Integration** | Docker Compose | < 3min | Every PR | Cross-component flows |
| **E2E** | Playwright | < 10min | main branch merge | Critical user journeys |
| **Load** | locust / k6 | > 10min | Scheduled / release | NFR validation |

### 1.3 Test Naming Convention

All test files and functions follow a consistent naming scheme:

```
tests/
├── unit/
│   └── test_{module}.py          →  test_{function_name}_{scenario}
├── integration/
│   └── test_{flow}.py            →  test_{flow}_{outcome}
├── api/
│   └── test_{resource}_api.py    →  test_{method}_{resource}_{variant}
└── e2e/
    └── test_{journey}.spec.ts    →  test_{journey}_{state}
```

---

## 2. Project Structure for Tests

### 2.1 Backend Test Layout

```
backend/
├── app/                              # Application code
└── tests/
    ├── conftest.py                   # Shared fixtures (app, db, client, auth headers)
    ├── factories.py                  # Model factories (build vs create strategies)
    ├── schemas/                      # JSON:API schema templates (see §6)
    │   ├── agent.json
    │   ├── model_deployment.json
    │   ├── benchmark.json
    │   ├── api_key.json
    │   ├── usage_record.json
    │   ├── workspace.json
    │   ├── user.json
    │   └── error.json
    ├── helpers/
    │   ├── jsonapi_asserts.py        # Assert helpers: assert_jsonapi_document, assert_errors
    │   └── auth_helpers.py           # Token generation helpers
    ├── unit/
    │   ├── test_config.py
    │   ├── services/
    │   │   ├── test_agent_manager.py
    │   │   ├── test_model_manager.py
    │   │   ├── test_usage_tracker.py
    │   │   ├── test_billing_service.py
    │   │   ├── test_log_service.py
    │   │   ├── test_retention_service.py
    │   │   └── test_proxy_service.py
    │   ├── schemas/
    │   │   ├── test_jsonapi_serializers.py
    │   │   ├── test_filters.py
    │   │   └── test_schema_validation.py
    │   ├── middleware/
    │   │   ├── test_auth_middleware.py
    │   │   └── test_rate_limit.py
    │   ├── ws/
    │   │   ├── test_agent_ws.py
    │   │   └── test_dashboard_ws.py
    │   └── utils/
    │       ├── test_crypto.py
    │       └── test_naming.py
    ├── api/
    │   ├── test_auth_api.py
    │   ├── test_agents_api.py
    │   ├── test_models_api.py
    │   ├── test_benchmarks_api.py
    │   ├── test_keys_api.py
    │   ├── test_usage_api.py
    │   ├── test_billing_api.py
    │   ├── test_workspace_api.py
    │   ├── test_proxy_api.py
    │   └── test_health_api.py
    └── integration/
        ├── test_agent_registration_flow.py
        ├── test_metric_ingestion_flow.py
        ├── test_model_deployment_flow.py
        ├── test_benchmark_flow.py
        ├── test_proxy_flow.py
        ├── test_workspace_isolation.py
        └── test_data_retention.py
```

### 2.2 Frontend Test Layout

```
frontend/
├── app/                              # Application code
└── tests/
    ├── setup.ts                      # Global test setup (PrimeVue mock, Pinia, router)
    ├── mocks/
    │   ├── server.ts                 # MSW (Mock Service Worker) handlers
    │   ├── websocket.ts             # WebSocket mock factory
    │   └── data/
    │       ├── agents.ts
    │       ├── metrics.ts
    │       ├── models.ts
    │       └── users.ts
    ├── unit/
    │   ├── components/
    │   │   ├── dashboard/
    │   │   │   ├── GpuMetricsChart.spec.ts
    │   │   │   ├── SystemResources.spec.ts
    │   │   │   ├── QueueDiagnostics.spec.ts
    │   │   │   ├── ModelList.spec.ts
    │   │   │   └── LiveLog.spec.ts
    │   │   ├── deployment/
    │   │   │   ├── DeploymentLogViewer.spec.ts
    │   │   │   └── GpuLoadingGraph.spec.ts
    │   │   ├── models/
    │   │   │   ├── DeployWizard.spec.ts
    │   │   │   ├── CapacityCalculator.spec.ts
    │   │   │   ├── ModelConfigForm.spec.ts
    │   │   │   └── ModelCard.spec.ts
    │   │   ├── benchmarks/
    │   │   │   ├── BenchmarkTable.spec.ts
    │   │   │   ├── BenchmarkComparison.spec.ts
    │   │   │   └── BenchmarkConfig.spec.ts
    │   │   ├── keys/
    │   │   │   └── ApiKeyList.spec.ts
    │   │   ├── users/
    │   │   │   └── MemberList.spec.ts
    │   │   └── common/
    │   │       ├── MetricCard.spec.ts
    │   │       ├── StatusBadge.spec.ts
    │   │       └── TimeRangeSelector.spec.ts
    │   ├── composables/
    │   │   ├── useAuth.spec.ts
    │   │   ├── useWebSocketMetrics.spec.ts
    │   │   ├── useAgents.spec.ts
    │   │   └── useModels.spec.ts
    │   └── stores/
    │       ├── auth.spec.ts
    │       ├── metrics.spec.ts
    │       ├── agents.spec.ts
    │       ├── models.spec.ts
    │       └── user.spec.ts
    ├── pages/
    │   ├── login.spec.ts
    │   ├── register.spec.ts
    │   ├── dashboard/
    │   │   ├── index.spec.ts
    │   │   ├── servers/
    │   │   │   └── [id].spec.ts
    │   │   ├── models/
    │   │   │   ├── index.spec.ts
    │   │   │   ├── deploy.spec.ts
    │   │   │   └── [id].spec.ts
    │   │   ├── benchmarks/
    │   │   │   ├── index.spec.ts
    │   │   │   ├── new.spec.ts
    │   │   │   └── [id].spec.ts
    │   │   ├── keys/
    │   │   │   └── index.spec.ts
    │   │   ├── usage/
    │   │   │   └── index.spec.ts
    │   │   ├── settings/
    │   │   │   ├── index.spec.ts
    │   │   │   ├── members.spec.ts
    │   │   │   └── billing.spec.ts
    │   │   └── admin/
    │   │       └── index.spec.ts
    │   └── index.spec.ts
    └── integration/
        ├── auth-flow.spec.ts
        ├── dashboard-metrics.spec.ts
        └── model-deployment-wizard.spec.ts
```

### 2.3 Agent Test Layout

```
modelprism-agent/
├── modelprism_agent/                 # Application code
└── tests/
    ├── conftest.py                   # Shared fixtures (mocked nvidia-smi, psutil, ws)
    ├── fixtures/
    │   ├── nvidia_smi_samples/       # Captured XML output from real GPUs
    │   │   ├── a100_single.xml
    │   │   ├── a100_dual.xml
    │   │   ├── h100_single.xml
    │   │   └── no_gpu.xml
    │   ├── vllm_metrics_samples/     # Captured Prometheus metric endpoints
    │   │   ├── single_model.txt
    │   │   └── dual_model.txt
    │   └── benchmark_results/
    │       └── sample_results.json
    ├── unit/
    │   ├── test_collector.py
    │   ├── metrics/
    │   │   ├── test_gpu.py
    │   │   ├── test_system.py
    │   │   └── test_vllm.py
    │   ├── manager/
    │   │   ├── test_docker_manager.py
    │   │   ├── test_vllm_manager.py
    │   │   └── test_model_downloader.py
    │   ├── test_connection.py
    │   ├── test_command_handler.py
    │   ├── test_log_streamer.py
    │   └── test_registration.py
    └── integration/
        ├── test_docker_compose_lifecycle.py    # Requires Docker socket
        └── test_vllm_integration.py            # Requires vLLM container
```

---

## 3. Backend Testing

### 3.1 Test Configuration

Backend tests use a dedicated `pytest` configuration with a `conftest.py` that provides all shared fixtures.

**Configuration file** `backend/pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
asyncio_mode = "auto"
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests that require external services (postgres, redis)",
    "docker: marks tests that require Docker (vLLM container)",
    "stripe: marks tests that hit Stripe API",
    "proxy: marks tests for the OpenAI proxy endpoints",
]
filterwarnings = ["ignore::DeprecationWarning"]
```

**`conftest.py` fixtures:**

| Fixture | Scope | Description |
|---|---|---|
| `app` | function | FastAPI `TestClient` instance |
| `db_session` | function | Isolated SQLAlchemy async session with rollback on teardown |
| `redis_client` | function | FakeRedis or isolated Redis DB 15 |
| `auth_headers` | function | JWT Bearer token for a test user |
| `agent_auth_headers` | function | `mp_` agent token header |
| `workspace` | function | Test workspace with owner |
| `user` | function | Test user with password |
| `agent` | function | Registered agent in a workspace |
| `model_deployment` | function | Deployed model on an agent |
| `api_key` | function | Test API key (sk-) in a workspace |

### 3.2 Unit Tests

**Backend unit tests mock all external I/O** (database session, Redis, HTTP calls, Stripe API, HuggingFace Hub API). They test business logic in isolation.

#### 3.2.1 Service Tests

##### `test_agent_manager.py`

```
test_register_agent_valid_token      → Agent registered, status = 'online'
test_register_agent_expired_token    → 401, token rejected
test_register_agent_duplicate_token  → 409, conflict
test_register_agent_two_phase_rollback → Token consumed but registration incomplete → cleanup after 5 min
test_deregister_agent                → Status changes to 'deregistered', connections terminated
test_pause_agent                     → Agent paused, metrics stop, containers untouched
test_stop_agent                      → Agent stopped, containers cleaned
test_update_agent_name               → Custom name persisted
test_update_agent_hourly_rate        → Hourly rate updated
test_list_agents_with_filters        → Filter by status, workspace, created_by
test_generate_agent_token            → Token generated with expiry
test_agent_heartbeat                 → last_seen_at updated
test_agent_offline_detection         → Agent marked offline after heartbeat timeout
```

##### `test_model_manager.py`

```
test_deploy_model_valid              → Deployment created, command sent to agent
test_deploy_model_insufficient_vram  → 422, capacity error
test_deploy_model_invalid_params     → 422, validation error
test_stop_model                      → Status → 'stopped', container stopped
test_restart_model                   → Model restarted, health check passes
test_delete_model                    → Model deleted, container removed
test_get_model_details               → Full deployment info returned
test_list_models_by_agent            → All models for an agent
test_list_models_by_status           → Filter by ready/stopped/failed
test_update_model_config_hotswap     → Hot-swappable params updated
test_update_model_config_restart     → Non-swappable params require restart
test_download_progress_updates       → download_progress field updates via WS
test_vram_estimation                 → VRAM estimate matches expected ranges
test_port_atomically_assigned        → No two deployments on the same agent share a port
test_port_released_on_delete         → Port freed after deployment deletion
```

##### `test_usage_tracker.py`

```
test_record_usage                    → Usage record created with correct tokens
test_record_usage_anonymous          → Works with NULL api_key_id
test_get_usage_by_key                → Aggregated usage for one API key
test_get_usage_by_model              → Aggregated usage per model
test_get_usage_by_workspace          → Workspace-scoped aggregation
test_get_usage_time_range            → Filter by date range
test_usage_export_csv                → CSV export contains correct headers and rows
test_usage_export_json               → JSON export valid
test_cost_calculation                → cost_cents = (input_tokens * input_rate + output_tokens * output_rate) / 1000
test_concurrent_record_insertion     → No race conditions on batch insert (test with trio tasks)
test_usage_batch_queue               → Batched writes processed in order
```

##### `test_billing_service.py`

```
test_create_checkout_session         → Stripe checkout URL returned
test_handle_stripe_webhook           → Invoice paid → billing_invoices updated
test_handle_stripe_webhook_idempotent → Same webhook processed once
test_stripe_failure_queue            → Failed Stripe calls queued, retried
test_metered_usage_report            → Usage batched and sent to Stripe Meter Events
test_get_current_spend               → Month-to-date total correct
test_get_invoice_history             → Paginated invoice list
test_billing_alert_threshold         → Alert fires at configured threshold
test_billing_alert_notification      → Email/webhook notification sent
test_self_hosted_billing_disabled    → Billing endpoints return 404 when MODELPRISM_CLOUD=false
```

##### `test_proxy_service.py`

```
test_chat_completion                 → Response matches OpenAI format
test_chat_completion_streaming       → SSE chunks match expected format, [DONE] terminates
test_completion_legacy               → Legacy completions endpoint works
test_list_models                     → Returns deployed models
test_route_to_vllm                   → Correct vLLM upstream selected by model name
test_route_round_robin               → Multiple agents with same model load-balanced
test_token_counting_intercept        → Input/output tokens counted via tiktoken
test_cost_accrual                    → Usage record created with cost
test_streaming_token_tracking        → Tokens tracked incrementally during SSE
test_key_authentication              → sk- key validated, user resolved
test_key_expired                     → Expired key returns 401
test_key_revoked                     → Revoked key returns 401
test_invalid_model                   → 404 for non-existent model
test_proxy_fallback                  → Primary agent down → fallback to next agent
test_proxy_all_agents_down           → 503 when no agents available
test_proxy_to_openai                 → Routes to upstream OpenAI if configured
test_proxy_to_anthropic              → Routes to upstream Anthropic if configured
```

##### `test_log_service.py`

```
test_ingest_log_entry                → Log stored in database
test_ingest_log_batch                → Batch of logs ingested
test_get_logs_by_agent               → Filtered by agent_id
test_get_logs_by_level               → Filtered by level (error, warning, etc.)
test_get_logs_time_range             → Filtered by timestamp
test_get_logs_limit                  → Results limited and paginated
test_retention_cleanup               → Logs beyond retention window deleted
test_websocket_broadcast_on_ingest   → New log entry broadcast to dashboard WS
```

##### `test_retention_service.py`

```
test_cleanup_raw_metrics             → Partitions older than retention dropped
test_cleanup_1m_metrics              → 1m rollup partitions cleaned
test_cleanup_5m_metrics              → 5m rollup partitions cleaned
test_cleanup_logs                    → Agent logs older than retention deleted
test_retention_respects_workspace_config → Each workspace retention policy honored
test_cleanup_dry_run                 → Dry-run mode reports without deleting
test_usage_records_not_deleted       → Usage records preserved (7 years)
```

##### `test_auth_middleware.py`

```
test_valid_jwt_access                → 200 for valid token
test_expired_jwt                     → 401, token expired
test_missing_token                   → 401, no authorization header
test_invalid_token                   → 401, malformed signature
test_revoked_session                 → 401, session revoked
test_access_token_expiry             → Access token expires at configured TTL
test_refresh_token_rotation          → Old refresh token invalidated on use
test_refresh_token_reuse_detection   → Reused refresh token → all sessions revoked
test_password_reset_token_expiry     → Reset token expires after 15 minutes
test_account_lockout                 → 5 failed attempts → locked 1 hour
test_account_lockout_reset           → Lockout clears after timeout
test_admin_required                  → Non-admin gets 403 on admin endpoints
test_role_based_access_owner         → Owner has full access
test_role_based_access_viewer        → Viewer restricted to read-only
test_role_based_access_member        → Member can create resources
```

##### `test_rate_limit.py`

```
test_dashboard_rate_limit            → 429 after 1001 requests in 1 minute
test_auth_rate_limit                 → 429 after 21 requests in 1 minute
test_proxy_rate_limit                → 429 per-key limit exceeded
test_rate_limit_reset                → Counter resets after window
test_rate_limit_bypass               → Admin role bypasses rate limits
test_redis_down_fail_open            → Requests allowed when Redis is unavailable
test_rate_limit_headers              → X-RateLimit-* headers present
test_sliding_window                  → Older requests expire from window
test_burst_handling                  → Burst of requests within limit accepted
```

##### `test_workspace_isolation.py`

```
test_cross_workspace_agent_invisible → Workspace A cannot see workspace B agents
test_cross_workspace_deployment_invisible → Workspace A cannot see workspace B deployments
test_cross_workspace_keys_invisible  → Workspace A cannot see workspace B API keys
test_cross_workspace_usage_invisible → Usage scoped to workspace
test_workspace_member_list           → Only workspace members listed
test_workspace_invite                → Invite creates pending membership
test_workspace_remove_member         → Member removed, access revoked
```

#### 3.2.2 Schema Tests

##### `test_jsonapi_serializers.py`

```
test_resource_object_structure        → type, id, attributes present
test_attributes_kebab_case            → All attribute keys in kebab-case
test_relationships_structure          → relationships.data has type and id
test_links_self_present               → links.self matches resource URL
test_document_with_included           → included array contains related resources
test_collection_document              → data is array, meta.has total/count, links present
test_pagination_links                 → self, next, prev, first, last URLs correct
test_error_document_structure         → errors array with status/code/title/detail
test_error_source_pointer             → source.pointer present for validation errors
test_sparse_fieldset                  → Only requested fields returned
test_filter_parsing                   → filter[field]=value parsed correctly
test_filter_range_parsing             → filter[field][gte]=val parsed correctly
test_sort_parsing                     → sort=-created-at,name parsed correctly
test_include_parsing                  → include=workspace,api-keys parsed correctly
test_null_attributes                  → Null attributes allowed per JSON:API spec
test_empty_relationships              → Empty relationships array allowed
test_meta_rate_limit                  → Rate limit metadata in 429 responses
test_204_no_content                   → DELETE returns 204, no body
test_201_created_location             → POST returns 201 with Location header
```

##### `test_filters.py`

```
test_filter_eq                        → Exact match filter
test_filter_neq                       → Not-equal filter
test_filter_gt_gte                    → Greater-than / greater-or-equal
test_filter_lt_lte                    → Less-than / less-or-equal
test_filter_like                      → Pattern match
test_filter_in                        → Set membership
test_filter_multiple                  → AND-combined filters
test_filter_invalid_field             → 400 for non-filterable field
test_filter_invalid_operator          → 400 for unknown operator
test_filter_unsafe_pattern            → SQL injection attempt rejected
test_sort_ascending                   → ASC sort
test_sort_descending                  → DESC sort (prefix with -)
test_sort_multiple                    → Multiple sort fields
test_sort_invalid_field               → 400 for non-sortable field
test_include_one_level               → Single relationship included
test_include_depth_limit              → Deep include rejected
test_include_invalid_relationship     → 400 for non-existent relationship
test_sparse_fieldset_invalid          → 400 for non-existent field
```

### 3.3 API / Contract Tests

API tests use the FastAPI `TestClient` (or `AsyncClient` for async endpoints) with a real database session that rolls back after each test. These tests validate:

1. HTTP status codes
2. JSON:API document structure (see §6)
3. kebab-case attribute naming
4. Pagination / filtering / sorting behavior
5. Error shapes for every failure mode

**Every endpoint group has a dedicated test file.** The pattern for each resource is:

```
test_list_{resource}                  → GET /api/v1/{resource} → 200, collection
test_list_{resource}_empty            → GET /api/v1/{resource} → 200, empty data array
test_list_{resource}_paginated        → GET with page[offset]=0&page[limit]=2 → 200, links present
test_list_{resource}_filtered         → GET with filter[status]=active → 200, filtered
test_list_{resource}_sorted           → GET with sort=-created-at → 200, sorted
test_get_{resource}                   → GET /api/v1/{resource}/{id} → 200, single resource
test_get_{resource}_not_found         → GET /api/v1/{resource}/nonexistent → 404
test_get_{resource}_included          → GET with ?include=relationship → 200, included array
test_get_{resource}_sparse_fields     → GET with ?fields[{resource}]=name,status → 200
test_create_{resource}                → POST /api/v1/{resource} → 201, resource created
test_create_{resource}_validation     → POST with missing fields → 422, errors
test_create_{resource}_unauthorized   → POST without auth → 401
test_update_{resource}                → PATCH /api/v1/{resource}/{id} → 200, updated
test_update_{resource}_not_found      → PATCH nonexistent → 404
test_update_{resource}_conflict       → PATCH duplicate name → 409
test_update_{resource}_read_only      → PATCH read-only field → 422
test_delete_{resource}                → DELETE /api/v1/{resource}/{id} → 204
test_delete_{resource}_not_found      → DELETE nonexistent → 404
test_delete_{resource}_unauthorized   → DELETE without auth → 401

# Auth endpoints (standard JSON, not JSON:API)
test_login_success                    → POST /api/auth/login → 200, JWT returned
test_login_invalid_password           → POST /api/auth/login → 401
test_login_locked_account             → POST /api/auth/login → 423
test_register_success                 → POST /api/auth/register → 201
test_register_duplicate_email         → POST /api/auth/register → 409
test_refresh_token                    → POST /api/auth/refresh → 200
test_refresh_token_expired            → POST /api/auth/refresh → 401
test_logout                           → POST /api/auth/logout → 200

# Public proxy endpoints (OpenAI format, not JSON:API)
test_proxy_chat_completion            → POST /v1/chat/completions → 200, OpenAI format
test_proxy_chat_completion_stream     → POST /v1/chat/completions?stream=true → SSE
test_proxy_models_list                → GET /v1/models → 200, OpenAI format
```

### 3.4 Integration Tests

Integration tests spin up real PostgreSQL and Redis containers via `testcontainers` or Docker Compose. They exercise flows that cross multiple components.

| Test | What it validates |
|---|---|
| `test_agent_registration_flow.py` | Full two-phase registration, token validation, hardware info storage, WebSocket connect |
| `test_metric_ingestion_flow.py` | Agent pushes metrics via WS → backend ingests → raw metrics stored → downsampled |
| `test_model_deployment_flow.py` | Deploy command → agent receives → Docker container created → health check → status=ready |
| `test_benchmark_flow.py` | Benchmark triggered → agent runs → results streamed → stored → comparable |
| `test_proxy_flow.py` | API key auth → proxy request → route to vLLM → response → usage recorded |
| `test_workspace_isolation.py` | Two workspaces with agents → cross-workspace access denied at every endpoint |
| `test_data_retention.py` | Ingest old metrics → run retention → partitions dropped → new data unaffected |

#### Integration Test Infrastructure

```python
# tests/integration/conftest.py pattern
import pytest
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:15") as pg:
        yield pg

@pytest.fixture(scope="session")
def redis_container():
    with RedisContainer("redis:7") as r:
        yield r

@pytest.fixture(scope="session")
def app(postgres_container, redis_container):
    """FastAPI app connected to real Postgres + Redis."""
    os.environ["DATABASE_URL"] = postgres_container.get_connection_url()
    os.environ["REDIS_URL"] = redis_container.get_connection_url()
    # Run Alembic migrations
    subprocess.run(["alembic", "upgrade", "head"], check=True)
    from app.main import create_app
    return TestClient(create_app())
```

### 3.5 Mocking Strategy for Backend

| Dependency | Mock Tool | Mock Strategy |
|---|---|---|
| Database session | `sqlmodel` / SQLAlchemy `create_async_engine` with `testing=True` | In-memory SQLite for fast unit tests; real PostgreSQL for integration tests |
| Redis | `fakeredis` | In-memory Redis mock for unit tests; real Redis container for integration tests |
| Stripe API | `respx` (httpx mock) | Mock HTTP calls to Stripe API |
| HuggingFace Hub API | `respx` | Mock HTTP calls to HF Hub search/model endpoints |
| vLLM HTTP API | `respx` | Mock vLLM /v1/models, /v1/chat/completions etc. |
| nvidia-smi | `unittest.mock` / `subprocess.MockPopen` | Capture real XML output as fixture strings |
| psutil | `unittest.mock` | Mock CPU, RAM, disk metrics |
| Docker socket | `docker.from_env()` mock | Mock Docker API responses for container operations |
| OpenAI API | `respx` | Mock HTTP calls to OpenAI for proxy fallback |
| Anthropic API | `respx` | Mock HTTP calls to Anthropic for proxy fallback |
| SMTP (password reset) | `aiosmtplib` mock | Capture emails, never send real ones |
| Time | `freezegun` / `time_machine` | Freeze time for TTL expiry tests, metric timestamps |

---

## 4. Frontend Testing

### 4.1 Test Configuration

**`frontend/vitest.config.ts`:**

```typescript
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'

export default defineConfig({
  plugins: [vue(), Components({ dts: false })],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.spec.ts'],
    coverage: {
      provider: 'v8',
      include: ['app/**/*.ts', 'app/**/*.vue', 'stores/**/*.ts', 'composables/**/*.ts'],
      exclude: ['app/**/*.d.ts', 'app/**/index.ts', 'app/pages/**/*.vue'],
      thresholds: {
        statements: 70,
        branches: 65,
        functions: 70,
        lines: 70,
      },
    },
  },
})
```

### 4.2 Global Setup (`tests/setup.ts`)

```typescript
import { config } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { vi, beforeEach } from 'vitest'

// PrimeVue stubs — all PrimeVue components auto-stubbed to avoid import complexity
config.global.stubs = {
  // PrimeVue components
  PrimeVue: true,
  Button: true,
  Card: true,
  Dialog: true,
  Dropdown: true,
  InputText: true,
  InputNumber: true,
  Select: true,
  MultiSelect: true,
  Slider: true,
  Stepper: true,
  Panel: true,
  DataTable: true,
  Column: true,
  Tag: true,
  Badge: true,
  ProgressBar: true,
  Toast: true,
  Message: true,
  InlineMessage: true,
  Chart: true,
  TabView: true,
  TabPanel: true,
  // Nuxt components
  NuxtLayout: true,
  NuxtPage: true,
  NuxtLink: true,
  ClientOnly: true,
}

// Pinia setup
beforeEach(() => {
  setActivePinia(createPinia())
})

// WebSocket mock (global for all tests)
class MockWebSocket {
  url: string
  onopen: (() => void) | null = null
  onclose: ((e: { code: number }) => void) | null = null
  onmessage: ((e: { data: string }) => void) | null = null
  onerror: ((e: Event) => void) | null = null
  readyState: number = 0
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3

  constructor(url: string) {
    this.url = url
    setTimeout(() => {
      this.readyState = 1
      this.onopen?.()
    }, 0)
  }
  send(data: string) { /* capture sent messages for assertion */ }
  close(code?: number) {
    this.readyState = 3
    this.onclose?.({ code: code ?? 1000 })
  }
}

vi.stubGlobal('WebSocket', MockWebSocket)

// ResizeObserver mock (not in jsdom)
vi.stubGlobal('ResizeObserver', vi.fn(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
})))
```

### 4.3 MSW (Mock Service Worker) Setup

All frontend API calls go through MSW handlers, giving deterministic responses without a backend:

```typescript
// tests/mocks/server.ts
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

const agentsData = [
  {
    type: 'agents',
    id: 'ag_001',
    attributes: {
      'friendly-name': 'cyan-koala-42',
      status: 'online',
      'gpu-model': 'NVIDIA A100-SXM4-80GB',
      'gpu-count': 4,
    },
  },
]

export const handlers = [
  // JSON:API resource endpoints
  http.get('*/api/v1/agents', () =>
    HttpResponse.json({
      data: agentsData,
      meta: { total: 1, count: 1 },
    })
  ),

  // Auth endpoints (standard JSON)
  http.post('*/api/auth/login', () =>
    HttpResponse.json({
      token_type: 'Bearer',
      access_token: 'eyJ...',
      refresh_token: 'eyJ...',
      expires_in: 3600,
      user: { id: 'usr_001', email: 'test@example.com', display_name: 'Test' },
    })
  ),

  // WebSocket mock for composable tests
  // ... additional handlers for all endpoints
]

export const server = setupServer(...handlers)

beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
```

### 4.4 Component Tests

Component tests use `vue-test-utils` with shallow-mounting by default. They verify:

1. **Render output** — component renders expected text, classes, data attributes
2. **Props** — component reacts to prop changes correctly
3. **Emits** — component emits events on interactions
4. **Slots** — slot content renders in the correct position
5. **State** — components with internal state display correct content

#### Key Component Test Examples

**`GpuMetricsChart.spec.ts`:**

```
test_renders_title_and_metric_name       → Title present, metric name displayed
test_renders_uplot_container             → uPlot mount point present
test_updates_on_prop_change              → New data prop triggers chart update
test_shows_loading_state                 → Loading skeleton shown when data is null
test_shows_empty_state                   → Empty state when data array is empty
test_applies_color_palette               → Colors match theme configuration
test_handles_time_range_prop             → Time range selector syncs with chart
test_emits_point_click                   → Click on data point emits event
test_does_not_render_before_mount        → Chart container empty before mount
```

**`LiveLog.spec.ts`:**

```
test_renders_log_entries                 → Log entries displayed in list
test_color_codes_by_level                → Error entries have red styling
test_auto_scrolls_to_bottom              → Scroll position at bottom on new entry
test_pause_auto_scroll_on_manual_scroll  → Manual scroll up pauses auto-scroll
test_resume_auto_scroll_on_button        → "Scroll to bottom" button resumes
test_filters_by_level                    → Only matching level entries shown
test_searches_within_logs                → Search filter narrows visible entries
test_shows_empty_state                   → "No logs" message when empty
test_limits_displayed_entries            → Max N entries shown, truncation notice
```

**`DeployWizard.spec.ts`:**

```
test_renders_five_steps                  → Five stepper steps visible
test_step_1_model_search                 → HF search works, results displayed
test_step_2_agent_selection              → Agents listed, selection works
test_step_3_config_form                  → vLLM params form renders
test_step_4_capacity_calculator          → VRAM estimate shown
test_step_5_review_and_deploy            → Summary shown, deploy button enabled
test_navigation_between_steps            → Next/prev buttons work
test_validation_per_step                 → Cannot proceed with invalid step
test_submit_deployment                   → API called with correct payload
test_shows_deployment_progress           → Progress bar updates after submit
test_shows_deployment_logs               → Log viewer appears after deploy
test_shows_gpu_monitoring                → GPU loading graph appears during deploy
test_handles_deployment_error            → Error state displayed on failure
test_handles_deployment_success          → Success state with model link
test_persists_form_state_on_back         → Previous step selections preserved
```

**`CapacityCalculator.spec.ts`:**

```
test_estimates_vram_requirements         → VRAM calculation correct
test_max_concurrent_requests             → Concurrency estimate based on VRAM budget
test_updates_on_param_change             → Sliders update estimates in real-time
test_shows_warning_on_overcapacity       → Red warning when VRAM exceeds available
test_shows_all_good_on_undercapacity     → Green indicator when within limits
test_displays_kv_cache_budget            → KV cache remaining shown
```

### 4.5 Composable Tests

**`useWebSocketMetrics.spec.ts`:**

```
test_connects_on_mount                   → WebSocket connection established
test_receives_metric_messages            → Metrics parsed and stored in reactive ref
test_batches_metrics_before_render       → 500ms batching window respected
test_disconnects_on_unmount              → WebSocket closed on component unmount
test_reconnects_on_disconnect            → Exponential backoff retry
test_handles_heartbeat                   → Heartbeat messages handled gracefully
test_handles_error_message               → Error type messages logged, state updated
test_provides_connection_status          → isConnected ref reactive
test_limits_stored_metrics               → Buffer capped at N data points
test_handles_auth_failure                → 4001 close code handled, token refresh attempted
test_multiple_agents                     → Can connect to multiple agent streams
test_time_range_switch                   → Resets buffer when time range changes
```

**`useAuth.spec.ts`:**

```
test_login_success                       → Tokens stored, user state populated
test_login_failure                       → Error state set, tokens not stored
test_register_success                    → User registered, auto-login
test_logout                              → Tokens cleared, state reset
test_refresh_token                       → New access token obtained
test_refresh_token_expired               → Force re-login
test_session_restore                     → Restore from persisted refresh token
test_protected_route_guard               → Redirect to login without auth
test_role_based_access                   → Role restricts route access
```

### 4.6 Store Tests

Pinia store tests verify state mutations and actions:

**`metrics.spec.ts`:**

```
test_initial_state                       → Empty metrics, connected=false
test_add_metric_point                    → Point added to correct agent's buffer
test_batch_update                        → Multiple points added in batch
test_clear_metrics                       → Buffer cleared
test_set_connection_status              → isConnected updated
test_set_time_range                     → Time range changed, buffer reset
test_getters_average_gpu_util           → Average computed from buffer
test_getters_latest_metric              → Most recent metric point returned
test_getters_metric_history_for_range   → Filtered by time range
test_actions_reconnect                   → WebSocket reconnection triggered
test_actions_disconnect                  → WebSocket closed
```

### 4.7 Page Tests

Page tests mount full page components with mocked stores and composables. They use shallow rendering for child components and verify page-level behavior:

```
test_page_renders_title                  → Page title displayed
test_page_renders_loading_skeleton       → Loading state shown during data fetch
test_page_renders_error_state            → Error state with retry button
test_page_renders_empty_state            → Empty state when no data
test_page_renders_data_fresh             → Normal state with all sections
test_page_navigation                     → Sidebar nav items highlight correctly
test_page_redirects_when_unauthorized    → Viewer role can access, guest redirected
test_page_redirects_when_forbidden       → Insufficient role → 403 page
```

### 4.8 WebSocket Mock for Frontend Tests

All composable and store tests that touch WebSocket functionality use the mock defined in `tests/setup.ts`. The mock supports:

- Simulated `onopen`, `onmessage`, `onclose`, `onerror` callbacks
- Capturing messages sent via `send()` for assertion
- Simulating server-initiated messages (push metrics, logs)
- Simulating disconnection and reconnection

**Simulating a metric push in a test:**

```typescript
// Inside a composable test
const ws = new MockWebSocket('wss://localhost/ws/metrics')
// Simulate server pushing a metric
ws.onmessage?.({
  data: JSON.stringify({
    type: 'metric',
    ts: '2026-06-07T12:00:00.000Z',
    payload: {
      agent_id: 'ag_001',
      gpu_util: 87.5,
      vram_used_gb: 42.1,
    },
  }),
})
// Assert that the composable's reactive state updated
expect(metricsStore.latestMetric('ag_001')?.gpu_util).toBe(87.5)
```

---

## 5. Agent Testing

### 5.1 Unit Tests with Mocked Hardware

The agent runs on GPU hardware that is unavailable in CI. All unit tests mock `nvidia-smi`, `psutil`, and Docker interactions using captured real-world output.

#### `test_gpu.py` — nvidia-smi parsing

```python
@pytest.fixture
def a100_single_output():
    """Captured nvidia-smi XML output from a single A100 GPU."""
    with open("tests/fixtures/nvidia_smi_samples/a100_single.xml") as f:
        return f.read()

@pytest.fixture
def a100_dual_output():
    """Captured nvidia-smi XML output from dual A100 GPUs."""
    with open("tests/fixtures/nvidia_smi_samples/a100_dual.xml") as f:
        return f.read()

@pytest.fixture
def no_gpu_output():
    """nvidia-smi output when no NVIDIA GPU is present."""
    with open("tests/fixtures/nvidia_smi_samples/no_gpu.xml") as f:
        return f.read()
```

Test cases:

```
test_parse_single_gpu                   → Returns list of 1 GPU dict
test_parse_dual_gpu                     → Returns list of 2 GPU dicts
test_parse_gpu_fields                   → All expected fields present (util_pct, mem_used_mb, temp_c, etc.)
test_parse_no_gpu                       → Returns empty list
test_parse_nvidia_smi_error             → Raises AgentError on subprocess failure (exit code != 0)
test_parse_non_xml_output               → Raises AgentError on parse failure
test_collect_gpu_metrics                → Full collection cycle returns correct data shape
test_collect_gpu_metrics_timing         → Collection completes in < 50ms (mocked)
test_gpu_temperature_limits             → Temperature values within valid range (0-100)
test_gpu_power_draw_range               → Power values non-negative
```

#### `test_system.py` — psutil-based metrics

```
test_collect_cpu                        → CPU percent, load averages returned
test_collect_ram                        → Used/total RAM in GB returned
test_collect_disk                       → Used/total/percent disk returned
test_collect_network                    → Network RX/TX bytes returned
test_collect_all_system                 → Combined system metrics returned
test_psutil_failure_graceful            → psutil error returns None for failing metric
```

#### `test_vllm.py` — vLLM Prometheus metrics parsing

```
test_parse_single_model                 → Token throughput, TTFT, KV cache parsed
test_parse_dual_model                   → Multiple model instances parsed
test_parse_empty_endpoint               → Empty response → empty result
test_parse_connection_error             → vLLM not reachable → graceful None
test_parse_partial_data                 → Partial metrics return partial result
test_ttft_p99_calculation               → P99 correctly computed from histogram buckets
test_gpu_cache_pct_parsing              → gpu_cache_usage_pct extracted correctly
```

#### `test_docker_manager.py`

```python
@pytest.fixture
def mock_docker_client():
    """Mock docker.from_env() client."""
    with patch("docker.from_env") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client
```

```
test_create_container                   → Docker container created with correct params
test_create_container_gpu_reservation   → --gpus flag set correctly
test_create_container_memory_limit      → Memory limits applied
test_create_container_port_mapping      → Port mapped correctly
test_stop_container                     → Container stopped gracefully
test_remove_container                   → Container removed
test_get_container_logs                 → Logs retrieved
test_container_health_check             → Health endpoint called and returns 200
test_container_health_timeout           → Health check times out → status = 'failed'
test_create_container_already_exists    → Port conflict → error raised
test_container_startup_logs             → Startup log lines captured
```

#### `test_model_downloader.py`

```
test_download_model                     → snapshot_download called with correct params
test_download_model_with_token          → HF token passed correctly
test_download_resumable                 → Partial download resumes from checkpoint
test_download_progress                  → Progress callback invoked with percentages
test_download_cancellation              → Cancel mid-download raises CancelledError
test_download_checksum_verification     → Checksums verified after download
test_download_hub_error                 → HF Hub error propagated as AgentError
test_download_invalid_model_id          → Invalid model ID → error
test_get_model_info                     → Model info retrieved from HF Hub
```

#### `test_connection.py`

```
test_connect_to_backend                 → WebSocket connection established
test_send_metrics                       → Metrics serialized and sent
test_receive_command                    → Command messages parsed correctly
test_heartbeat_send                     → Heartbeat sent every 15 seconds
test_heartbeat_receive                  → Heartbeat ack received
test_reconnect_exponential_backoff      → Reconnects with 1s, 2s, 4s, ... up to 60s
test_reconnect_on_backend_restart       → Reconnects after WebSocket close
test_buffer_metrics_during_disconnect   → Metrics buffered up to 60s
test_replay_buffered_metrics            → Buffered metrics sent on reconnect
test_connection_auth_failure            → Invalid token → connection rejected
test_connection_reconnect_signal        → Backend reconnect signal handled
test_send_batched_metrics               → Metrics batched at correct interval
test_connection_close_cleanup           → Clean teardown on close
```

#### `test_command_handler.py`

```
test_handle_deploy_model                → deploy_model command triggers deployment flow
test_handle_stop_model                  → stop_model command stops container
test_handle_restart_model               → restart_model command restarts container
test_handle_run_benchmark               → run_benchmark command triggers benchmark
test_handle_pause                       → pause command stops metric collection
test_handle_resume                      → resume command restarts metric collection
test_handle_unknown_command             → Unknown command → error result sent
test_command_progress_reporting         → Progress messages sent during execution
test_command_result_success             → Success result with result data
test_command_result_failure             → Failure result with error details
test_concurrent_commands                → Commands queued, executed sequentially
test_command_cancellation               → Cancel command stops execution
```

#### `test_log_streamer.py`

```
test_send_log_entry                     → Log entry POSTed to correct endpoint
test_send_log_batch                     → Multiple entries batched in one POST
test_log_level_filtering                → Backend filters by level correctly
test_log_retry_on_failure               → Retry with backoff on HTTP 5xx
test_log_discard_on_queue_full          → Queue capped, oldest dropped
test_log_context_included               → Source module and stack trace included
test_http_error_handling                → 4xx errors not retried (permanent)
```

### 5.2 Agent Integration Tests

#### Docker Compose vLLM Integration

```python
# tests/integration/test_vllm_integration.py
@pytest.fixture(scope="module")
def vllm_container():
    """Start a real vLLM Docker container with a small test model."""
    client = docker.from_env()
    container = client.containers.run(
        "vllm/vllm-openai:latest",
        command=["--model", "Qwen/Qwen2.5-0.5B-Instruct", "--max-model-len", "2048"],
        environment={"CUDA_VISIBLE_DEVICES": "0"},
        devices=["/dev/nvidia0:/dev/nvidia0"],
        ports={"8000/tcp": 8001},
        detach=True,
        remove=True,
    )
    # Wait for health check
    wait_for_health("http://localhost:8001/v1/models", timeout=120)
    yield container
    container.stop()
```

```
test_agent_metrics_vllm_integration     → Agent collects metrics from real vLLM instance
test_agent_chat_completion              → Agent proxies chat completion through vLLM
test_agent_benchmark_vllm               → Agent runs benchmark against real vLLM
test_vllm_metrics_endpoint              → /metrics endpoint returns Prometheus data
test_multiple_vllm_instances            → Two vLLM containers, metrics from both
test_vllm_container_health_check        → Health check passes when vLLM is ready
test_vllm_container_health_failure      → Health check fails when vLLM not ready
```

---

## 6. JSON:API Response Schema Validation

### 6.1 Why Schema Validation Matters

ModelPrism's Dashboard REST API is contract-bound to JSON:API 1.0. Every response must conform to the specification — a malformed response breaks every client. Schema validation is built into the test suite as a **reusable assertion layer**, not a one-time check.

### 6.2 Schema Template Files

Each resource type has a JSON Schema template in `backend/tests/schemas/`. These are derived from the [JSON:API 1.0 specification](https://jsonapi.org/format/) and the resource attribute definitions in the data models.

**`backend/tests/schemas/agent.json`:**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Agent Resource (JSON:API)",
  "type": "object",
  "properties": {
    "data": {
      "type": "object",
      "properties": {
        "type": { "const": "agents" },
        "id": { "type": "string", "pattern": "^ag_[A-Za-z0-9]{20,}$" },
        "attributes": {
          "type": "object",
          "properties": {
            "friendly-name": { "type": "string" },
            "custom-name": { "type": ["string", "null"] },
            "status": {
              "type": "string",
              "enum": ["online", "offline", "degraded", "provisioning", "deregistered"]
            },
            "agent-version": { "type": "string" },
            "last-seen-at": { "type": ["string", "null"], "format": "date-time" },
            "registered-at": { "type": "string", "format": "date-time" },
            "hardware-info": { "type": "object" },
            "hourly-rate-cents": { "type": "integer", "minimum": 0 },
            "created-at": { "type": "string", "format": "date-time" },
            "updated-at": { "type": "string", "format": "date-time" }
          },
          "required": [
            "friendly-name", "status", "agent-version",
            "registered-at", "hourly-rate-cents", "created-at"
          ],
          "additionalProperties": false
        },
        "relationships": {
          "type": "object",
          "properties": {
            "workspace": {
              "type": "object",
              "properties": {
                "data": {
                  "type": "object",
                  "properties": {
                    "type": { "const": "workspaces" },
                    "id": { "type": "string" }
                  },
                  "required": ["type", "id"]
                }
              }
            },
            "model-deployments": {
              "type": "object",
              "properties": {
                "data": {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "properties": {
                      "type": { "const": "model-deployments" },
                      "id": { "type": "string" }
                    },
                    "required": ["type", "id"]
                  }
                }
              }
            }
          },
          "additionalProperties": false
        },
        "links": {
          "type": "object",
          "properties": {
            "self": { "type": "string", "pattern": "^/api/v1/agents/" }
          },
          "required": ["self"]
        }
      },
      "required": ["type", "id", "attributes"],
      "additionalProperties": false
    },
    "included": {
      "type": "array",
      "items": { "$ref": "#/$defs/resource-identifier" }
    },
    "meta": {
      "type": "object",
      "properties": {
        "total": { "type": "integer" },
        "count": { "type": "integer" }
      }
    },
    "links": {
      "type": "object",
      "properties": {
        "self": { "type": "string" },
        "next": { "type": ["string", "null"] },
        "prev": { "type": ["string", "null"] },
        "first": { "type": "string" },
        "last": { "type": "string" }
      }
    }
  },
  "required": ["data"],
  "additionalProperties": false,
  "$defs": {
    "resource-identifier": {
      "type": "object",
      "properties": {
        "type": { "type": "string" },
        "id": { "type": "string" }
      },
      "required": ["type", "id"]
    }
  }
}
```

Schema template files exist for every resource: `model_deployment.json`, `benchmark.json`, `api_key.json`, `usage_record.json`, `workspace.json`, `user.json`, and `error.json`.

### 6.3 Assertion Helpers

**`backend/tests/helpers/jsonapi_asserts.py`:**

```python
import json
import os
from typing import Any
import jsonschema
from jsonschema import validate, ValidationError


_SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "..", "schemas")


def _load_schema(resource_type: str) -> dict:
    """Load a JSON Schema template by resource type name."""
    path = os.path.join(_SCHEMA_DIR, f"{resource_type}.json")
    with open(path) as f:
        return json.load(f)


def assert_jsonapi_document(response: dict, resource_type: str):
    """
    Assert that a response dict conforms to the JSON:API schema
    for the given resource type.

    - Single resource: response["data"] is a dict
    - Collection: response["data"] is a list
    - Validates attributes, relationships, links, meta
    - Enforces kebab-case for all attribute keys
    """
    schema = _load_schema(resource_type)
    try:
        validate(instance=response, schema=schema)
    except ValidationError as e:
        raise AssertionError(
            f"JSON:API validation failed for '{resource_type}': {e.message}\n"
            f"Path: {' -> '.join(str(p) for p in e.absolute_path)}\n"
            f"Response: {json.dumps(response, indent=2)[:500]}"
        )


def assert_jsonapi_collection(response: dict, resource_type: str):
    """Assert a JSON:API collection response with pagination meta."""
    assert isinstance(response.get("data"), list), "Collection must have data as a list"
    assert "meta" in response, "Collection must include meta"
    assert "total" in response["meta"], "meta must include total"
    assert "count" in response["meta"], "meta must include count"
    assert_jsonapi_document(response, resource_type)


def assert_jsonapi_error(response: dict, expected_status: str = None):
    """Assert a JSON:API error response structure."""
    assert "errors" in response, "Error response must have 'errors' key"
    assert isinstance(response["errors"], list), "errors must be a list"
    for error in response["errors"]:
        assert "status" in error, "Each error must have 'status'"
        assert "code" in error, "Each error must have 'code'"
        assert "title" in error, "Each error must have 'title'"
        if expected_status:
            assert error["status"] == expected_status, (
                f"Expected status {expected_status}, got {error['status']}"
            )


def assert_kebab_case(obj: dict, path: str = ""):
    """
    Recursively assert that all keys in an object use kebab-case.
    Skips top-level JSON:API keys (data, meta, links, errors, included).
    """
    excluded_keys = {"data", "meta", "links", "errors", "included", "type", "id"}
    for key, value in obj.items():
        if key in excluded_keys:
            if isinstance(value, dict):
                assert_kebab_case(value, path)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        assert_kebab_case(item, path)
            continue
        assert "-" in key or "_" not in key, (
            f"Key '{key}' at {path} must be kebab-case (use hyphens, not underscores)"
        )
        if isinstance(value, dict):
            assert_kebab_case(value, f"{path}.{key}")
```

### 6.4 Using Schema Validation in Tests

```python
# Example: test_agents_api.py
from helpers.jsonapi_asserts import assert_jsonapi_document, assert_jsonapi_error

class TestAgentsAPI:
    async def test_list_agents(self, client, auth_headers):
        response = await client.get("/api/v1/agents", headers=auth_headers)
        assert response.status_code == 200
        assert_jsonapi_document(response.json(), "agent")

    async def test_get_agent_not_found(self, client, auth_headers):
        response = await client.get("/api/v1/agents/nonexistent", headers=auth_headers)
        assert response.status_code == 404
        assert_jsonapi_error(response.json(), "404")

    async def test_create_agent(self, client, auth_headers):
        payload = {
            "data": {
                "type": "agents",
                "attributes": {
                    "friendly-name": "test-agent",
                    "hourly-rate-cents": 250,
                },
                "relationships": {
                    "workspace": {
                        "data": {"type": "workspaces", "id": "ws_001"}
                    }
                },
            }
        }
        response = await client.post(
            "/api/v1/agents",
            headers=auth_headers,
            json=payload,
        )
        assert response.status_code == 201
        body = response.json()
        assert_jsonapi_document(body, "agent")
        assert body["data"]["attributes"]["friendly-name"] == "test-agent"
```

### 6.5 CI Validation

A dedicated CI job runs all schema validation tests and also performs a **static schema audit** on the schema files themselves:

```yaml
- name: Validate JSON:API schemas
  run: |
    for schema in backend/tests/schemas/*.json; do
      python -m jsonschema -i "$schema" "$schema"  # Self-validating
    done
```

---

## 7. WebSocket Testing Strategy

### 7.1 Backend WebSocket Tests

Backend WebSocket tests use FastAPI's `TestClient` in WebSocket mode with `pytest-asyncio`:

```python
# tests/unit/ws/test_agent_ws.py
@pytest.mark.asyncio
async def test_agent_ws_connect(app, agent_auth_headers):
    """Agent can connect and receives ack."""
    async with app.websocket_connect(
        f"/ws/agents/{AGENT_ID}",
        headers=agent_auth_headers,
    ) as ws:
        data = ws.receive_json()
        assert data["type"] == "ack"
        assert data["payload"]["status"] == "connected"


@pytest.mark.asyncio
async def test_agent_ws_metrics(app, agent_auth_headers, sample_metrics):
    """Agent pushes metrics, backend acknowledges."""
    async with app.websocket_connect(
        f"/ws/agents/{AGENT_ID}",
        headers=agent_auth_headers,
    ) as ws:
        # Agent sends metrics
        await ws.send_json(sample_metrics)
        ack = ws.receive_json()
        assert ack["type"] == "ack"

        # Dashboard client should receive broadcast
        # (tested in dashboard_ws tests)


@pytest.mark.asyncio
async def test_agent_ws_heartbeat(app, agent_auth_headers):
    """Heartbeat keeps connection alive."""
    async with app.websocket_connect(
        f"/ws/agents/{AGENT_ID}",
        headers=agent_auth_headers,
    ) as ws:
        ws.send_json({"type": "heartbeat", "ts": "2026-06-07T12:00:00Z", "payload": {}})
        response = ws.receive_json()
        assert response["type"] == "heartbeat"


@pytest.mark.asyncio
async def test_agent_ws_auth_failure(app):
    """Invalid token rejected with 4001."""
    with pytest.raises(WebSocketDisconnect) as exc:
        async with app.websocket_connect(
            f"/ws/agents/{AGENT_ID}",
            headers={"Authorization": "Bearer invalid"},
        ):
            pass
    assert exc.value.code == 4001


@pytest.mark.asyncio
async def test_dashboard_ws_broadcast(app, auth_headers, agent_auth_headers, sample_metrics):
    """Dashboard client receives metrics broadcast."""
    async with (
        app.websocket_connect("/ws/dashboard", headers=auth_headers) as dashboard_ws,
        app.websocket_connect(
            f"/ws/agents/{AGENT_ID}", headers=agent_auth_headers
        ) as agent_ws,
    ):
        # Agent pushes metric
        await agent_ws.send_json(sample_metrics)
        # Dashboard receives it
        broadcast = dashboard_ws.receive_json()
        assert broadcast["type"] == "metric"
        assert broadcast["payload"]["agent_id"] == AGENT_ID


@pytest.mark.asyncio
async def test_ws_disconnect_cleanup(app, agent_auth_headers):
    """Disconnected agent cleaned up, status set to offline."""
    async with app.websocket_connect(
        f"/ws/agents/{AGENT_ID}", headers=agent_auth_headers
    ) as ws:
        pass  # Context manager closes connection
    # Verify agent status changed to offline
    agent = await get_agent(AGENT_ID)
    assert agent.status == "offline"
```

### 7.2 WebSocket Test Matrix

| Scenario | Agent WS | Dashboard WS | Expected Behavior |
|---|---|---|---|
| Agent connects with valid auth | ✅ | — | 101 switching, ack received |
| Agent connects with expired auth | ✅ | — | 4001 close, agent marked offline |
| Agent sends metrics | ✅ | — | Metrics ingested, ack sent |
| Agent sends metrics during dashboard subscription | ✅ | ✅ | Metrics broadcast to dashboard |
| Dashboard subscribes mid-stream | — | ✅ | Starts receiving from next metric |
| Heartbeat timeout (60s) | ✅ | — | Connection closed by server |
| Multiple dashboards same agent | — | ✅ (×2) | Both receive broadcasts |
| Agent disconnects ungracefully | ✅ | — | Timeout → status=offline |
| Command sent to agent | — | — | Queued, delivered on next heartbeat |
| Massive metric payload (100+ GPUs) | ✅ | ✅ | Payload handled, truncated if too large |

### 7.3 WebSocket Load Testing

Load tests (see §13) include a dedicated WebSocket scenario:

```python
# backend/tests/load/test_websocket_load.py
class WebSocketLoadTest:
    """
    Simulate 100 agents simultaneously pushing metrics.
    Measure:
    - Backend CPU/memory under load
    - Broadcast latency p50/p95/p99
    - Connection stability over 5 minutes
    - Memory growth (leak detection)
    """
```

---

## 8. End-to-End Testing (Playwright)

### 8.1 E2E Test Infrastructure

E2E tests run against a full stack deployed via Docker Compose:

```yaml
# deploy/docker-compose.test.yml
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: modelprism_test
      POSTGRES_USER: test
      POSTGRES_PASSWORD: test
    ports: ["5432:5432"]

  redis:
    image: redis:7
    ports: ["6379:6379"]

  backend:
    build: ../backend
    environment:
      DATABASE_URL: postgresql+asyncpg://test:test@postgres:5432/modelprism_test
      REDIS_URL: redis://redis:6379/1
      MODELPRISM_CLOUD: "false"
    ports: ["8000:8000"]
    depends_on: [postgres, redis]

  frontend:
    build: ../frontend
    environment:
      NUXT_PUBLIC_API_BASE: http://backend:8000
    ports: ["3000:3000"]
    depends_on: [backend]
```

### 8.2 Playwright Configuration

**`frontend/playwright.config.ts`:**

```typescript
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  workers: 1, // Sequential to avoid shared-state conflicts
  timeout: 60000,
  expect: { timeout: 15000 },
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
  ],
})
```

### 8.3 Critical User Journeys

#### Journey 1: User Registration & Login

```typescript
// tests/e2e/auth.spec.ts
test('user registers, logs in, and sees empty dashboard', async ({ page }) => {
  await page.goto('/register')
  await page.fill('[data-testid="email"]', 'test@example.com')
  await page.fill('[data-testid="password"]', 'password123')
  await page.fill('[data-testid="display-name"]', 'Test User')
  await page.click('[data-testid="register-submit"]')
  await expect(page).toHaveURL(/\/dashboard/)
  await expect(page.locator('[data-testid="welcome-message"]')).toContainText('Test User')
})

test('login with invalid password shows error', async ({ page }) => {
  await page.goto('/login')
  await page.fill('[data-testid="email"]', 'test@example.com')
  await page.fill('[data-testid="password"]', 'wrong-password')
  await page.click('[data-testid="login-submit"]')
  await expect(page.locator('[data-testid="error-message"]')).toBeVisible()
})
```

#### Journey 2: GPU Server Dashboard

```typescript
// tests/e2e/dashboard.spec.ts
test('dashboard shows GPU servers and live metrics', async ({ page }) => {
  // Login
  await page.goto('/login')
  await page.fill('[data-testid="email"]', 'test@example.com')
  await page.fill('[data-testid="password"]', 'password123')
  await page.click('[data-testid="login-submit"]')

  // Overview page should show agent list
  await expect(page.locator('[data-testid="agent-list"]')).toBeVisible()
  await expect(page.locator('[data-testid="agent-card"]')).toHaveCount(1)

  // Click into a server
  await page.click('[data-testid="agent-card"] >> nth=0')
  await expect(page).toHaveURL(/\/dashboard\/servers\/ag_/)

  // Real-time charts should render
  await expect(page.locator('[data-testid="gpu-metrics-chart"]')).toBeVisible()
  await expect(page.locator('[data-testid="system-resources"]')).toBeVisible()

  // System resource cards should show data
  await expect(page.locator('[data-testid="gpu-util"]')).toBeVisible()
  await expect(page.locator('[data-testid="vram-bar"]')).toBeVisible()
})

test('time range selector changes chart data', async ({ page }) => {
  // ... login, navigate to server dashboard
  await page.click('[data-testid="time-range-1h"]')
  await expect(page.locator('[data-testid="time-range-1h"]')).toHaveClass(/active/)
  await page.click('[data-testid="time-range-24h"]')
  await expect(page.locator('[data-testid="time-range-24h"]')).toHaveClass(/active/)
})

test('live log viewer streams and filters', async ({ page }) => {
  // ... login, navigate to server dashboard
  await expect(page.locator('[data-testid="live-log"]')).toBeVisible()
  await page.click('[data-testid="log-filter-error"]')
  // Only error-level entries visible
  await expect(page.locator('[data-testid="log-entry"]')).toHaveCount(0) // or filtered count
})
```

#### Journey 3: Model Deployment

```typescript
// tests/e2e/deployment.spec.ts
test('user completes full model deployment wizard', async ({ page }) => {
  // Login
  await page.goto('/login')
  await page.fill('[data-testid="email"]', 'test@example.com')
  await page.fill('[data-testid="password"]', 'password123')
  await page.click('[data-testid="login-submit"]')

  // Navigate to deploy
  await page.goto('/dashboard/models/deploy')

  // Step 1: Search model
  await page.fill('[data-testid="model-search"]', 'Qwen/Qwen2.5-0.5B')
  await page.waitForSelector('[data-testid="model-result"]')
  await page.click('[data-testid="model-result"] >> nth=0')

  // Step 2: Select agent
  await page.click('[data-testid="agent-option"] >> nth=0')

  // Step 3: Configure params
  await page.fill('[data-testid="max-model-len"]', '4096')
  await page.selectOption('[data-testid="quantization"]', 'fp8')

  // Step 4: Capacity calculator shows estimate
  await expect(page.locator('[data-testid="vram-estimate"]')).toBeVisible()
  await expect(page.locator('[data-testid="capacity-ok"]')).toBeVisible()

  // Step 5: Review and deploy
  await expect(page.locator('[data-testid="deploy-summary"]')).toBeVisible()
  await page.click('[data-testid="deploy-submit"]')

  // Deployment progress
  await expect(page.locator('[data-testid="deployment-progress"]')).toBeVisible()
  await expect(page.locator('[data-testid="deployment-log-viewer"]')).toBeVisible()
  await expect(page.locator('[data-testid="gpu-loading-graph"]')).toBeVisible()
})

test('deployment with insufficient VRAM shows warning', async ({ page }) => {
  // ... fill wizard with parameters that exceed VRAM
  await expect(page.locator('[data-testid="capacity-warning"]')).toBeVisible()
  await expect(page.locator('[data-testid="deploy-submit"]')).toBeDisabled()
})
```

#### Journey 4: API Key Management

```typescript
// tests/e2e/api-keys.spec.ts
test('user creates, copies, and revokes API key', async ({ page }) => {
  // Login
  await page.goto('/login')
  await page.fill('[data-testid="email"]', 'test@example.com')
  await page.fill('[data-testid="password"]', 'password123')
  await page.click('[data-testid="login-submit"]')

  // Navigate to API keys
  await page.goto('/dashboard/keys')
  await page.click('[data-testid="create-key"]')

  // Fill key details
  await page.fill('[data-testid="key-name"]', 'Test Key')
  await page.click('[data-testid="key-create-submit"]')

  // Key is shown once
  await expect(page.locator('[data-testid="key-display"]')).toBeVisible()
  await expect(page.locator('[data-testid="key-prefix"]')).toContainText('sk-')

  // Revoke key
  await page.click('[data-testid="key-revoke"]')
  await page.click('[data-testid="confirm-revoke"]')
  await expect(page.locator('[data-testid="key-status"]')).toContainText('Revoked')
})
```

#### Journey 5: Benchmark Flow

```typescript
// tests/e2e/benchmark.spec.ts
test('user runs benchmark and sees results', async ({ page }) => {
  // Login
  await page.goto('/login')
  await page.fill('[data-testid="email"]', 'test@example.com')
  await page.fill('[data-testid="password"]', 'password123')
  await page.click('[data-testid="login-submit"]')

  // Navigate to benchmarks
  await page.goto('/dashboard/benchmarks/new')

  // Select model and configure
  await page.selectOption('[data-testid="benchmark-model"]', 'model_001')
  await page.fill('[data-testid="num-requests"]', '100')
  await page.fill('[data-testid="concurrency"]', '5')
  await page.click('[data-testid="start-benchmark"]')

  // Wait for completion
  await expect(page.locator('[data-testid="benchmark-progress"]')).toBeVisible()
  await expect(page.locator('[data-testid="benchmark-results"]')).toBeVisible({ timeout: 60000 })

  // Results displayed
  await expect(page.locator('[data-testid="ttft-p50"]')).toBeVisible()
  await expect(page.locator('[data-testid="throughput-tps"]')).toBeVisible()
})
```

#### Journey 6: Workspace Settings & Data Retention

```typescript
// tests/e2e/settings.spec.ts
test('user configures data retention settings', async ({ page }) => {
  // Login
  await page.goto('/login')
  await page.fill('[data-testid="email"]', 'test@example.com')
  await page.fill('[data-testid="password"]', 'password123')
  await page.click('[data-testid="login-submit"]')

  // Navigate to settings
  await page.goto('/dashboard/settings')

  // Adjust retention slider
  await page.locator('[data-testid="retention-raw"]').fill('48')
  await page.click('[data-testid="save-settings"]')

  // Confirmation toast
  await expect(page.locator('[data-testid="success-toast"]')).toBeVisible()
})
```

### 8.4 E2E Test Data Setup

All E2E tests use a dedicated test data fixture. Before each test suite:

1. Docker Compose starts all services
2. Alembic runs migrations against the test database
3. A seed script populates test data (1 user, 1 workspace, 1 agent, sample metrics)
4. The agent WebSocket is simulated (the test backend has a mock agent that pushes metrics)
5. Tests run against the full stack
6. After the suite, containers are stopped and volumes removed

---

## 9. Integration Test Environments

### 9.1 Environment Matrix

| Environment | PostgreSQL | Redis | Docker (vLLM) | Stripe | HF Hub |
|---|---|---|---|---|---|
| **Unit tests** | Mock (in-memory) | Mock (fakeredis) | Mock | Mock (respx) | Mock (respx) |
| **API tests** | TestContainer | TestContainer | Mock | Mock | Mock |
| **Integration** | TestContainer | TestContainer | Real (optional) | Mock | Mock |
| **E2E** | Docker Compose | Docker Compose | N/A | Mock | Mock |
| **Load tests** | Docker Compose | Docker Compose | N/A | Mock | Mock |

### 9.2 Test Containers Configuration

```python
# backend/tests/integration/conftest.py
import pytest
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

@pytest.fixture(scope="session")
def postgres():
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg

@pytest.fixture(scope="session")
def redis():
    with RedisContainer("redis:7-alpine") as r:
        yield r
```

### 9.3 Stripe Mocking

All Stripe interactions use `respx` to mock the Stripe API:

```python
@pytest.fixture(autouse=True)
def mock_stripe_api():
    """Mock all Stripe HTTP calls."""
    with respx.mock(base_url="https://api.stripe.com") as respx_mock:
        # POST /v1/checkout/sessions
        respx_mock.post("/v1/checkout/sessions").respond(
            status_code=200,
            json={
                "id": "cs_test_123",
                "url": "https://checkout.stripe.com/cs_test_123",
                "status": "open",
            },
        )
        # POST /v1/billing/meter_events
        respx_mock.post("/v1/billing/meter_events").respond(status_code=200, json={"id": "me_123"})
        yield respx_mock
```

---

## 10. CI Pipeline (GitHub Actions)

### 10.1 Workflow Structure

```
.github/workflows/
├── backend-ci.yml              # Backend lint, type-check, test, coverage
├── frontend-ci.yml             # Frontend lint, type-check, test, coverage
├── agent-ci.yml                # Agent lint, type-check, test, coverage
├── integration-ci.yml          # Docker Compose integration tests
├── e2e-ci.yml                  # Playwright E2E tests
├── release.yml                 # Build, tag, publish
└── security-audit.yml          # Weekly dependency + code security scan
```

### 10.2 Backend CI

```yaml
# .github/workflows/backend-ci.yml
name: Backend CI

on:
  pull_request:
    paths: ['backend/**', 'common/**']
  push:
    branches: [main, develop]
    paths: ['backend/**', 'common/**']

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install ruff mypy
      - run: ruff check backend/ common/
      - run: mypy backend/ common/

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_DB: modelprism_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports: ['5432:5432']
      redis:
        image: redis:7-alpine
        ports: ['6379:6379']

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -e backend/ -e common/
      - run: pip install pytest pytest-asyncio pytest-cov httpx fakeredis respx

      - name: Run unit + API tests
        run: |
          pytest backend/tests/unit/ backend/tests/api/ \
            --cov=backend/app \
            --cov-report=term \
            --cov-report=xml \
            --junitxml=test-results.xml
        env:
          DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/modelprism_test
          REDIS_URL: redis://localhost:6379/1

      - name: Enforce coverage threshold
        run: |
          coverage report --fail-under=80

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: backend-test-results
          path: test-results.xml
```

### 10.3 Frontend CI

```yaml
# .github/workflows/frontend-ci.yml
name: Frontend CI

on:
  pull_request:
    paths: ['frontend/**']
  push:
    branches: [main, develop]
    paths: ['frontend/**']

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '22' }
      - run: npm install -g pnpm
      - run: pnpm install
        working-directory: frontend
      - run: pnpm run lint
        working-directory: frontend
      - run: pnpm run typecheck
        working-directory: frontend

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '22' }
      - run: npm install -g pnpm
      - run: pnpm install
        working-directory: frontend
      - run: pnpm vitest run --coverage
        working-directory: frontend
      - name: Check coverage
        run: |
          # Coverage threshold enforced by vitest config (70%)
          # Fail if vitest coverage check fails
          pnpm vitest run --coverage --coverage.thresholds.statements=70
        working-directory: frontend
```

### 10.4 Agent CI

```yaml
# .github/workflows/agent-ci.yml
name: Agent CI

on:
  pull_request:
    paths: ['modelprism-agent/**', 'common/**']
  push:
    branches: [main, develop]
    paths: ['modelprism-agent/**', 'common/**']

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.10' }
      - run: pip install -e modelprism-agent/ -e common/
      - run: pip install pytest pytest-asyncio pytest-cov
      - run: |
          pytest modelprism-agent/tests/unit/ \
            --cov=modelprism_agent \
            --cov-report=term \
            --cov-report=xml
      - name: Coverage
        run: coverage report --fail-under=80
```

### 10.5 Integration CI

```yaml
# .github/workflows/integration-ci.yml
name: Integration Tests

on:
  pull_request:
    branches: [main, develop]

jobs:
  integration:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: |
          docker compose -f deploy/docker-compose.test.yml up -d
          sleep 15  # Wait for services to be ready
      - run: pip install -e backend/ -e common/
      - run: pip install pytest pytest-asyncio pytest-cov testcontainers
      - run: |
          pytest backend/tests/integration/ -m "not docker" \
            --timeout=120 \
            --junitxml=integration-results.xml
      - run: docker compose -f deploy/docker-compose.test.yml down -v
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: integration-results
          path: integration-results.xml
```

### 10.6 E2E CI

```yaml
# .github/workflows/e2e-ci.yml
name: E2E Tests

on:
  push:
    branches: [main]

jobs:
  e2e:
    timeout-minutes: 30
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Start test stack
        run: docker compose -f deploy/docker-compose.test.yml up -d --wait

      - uses: actions/setup-node@v4
        with: { node-version: '22' }

      - run: npm install -g pnpm
      - run: pnpm install
        working-directory: frontend
      - run: pnpm playwright install --with-deps
        working-directory: frontend

      - name: Run Playwright tests
        run: pnpm playwright test
        working-directory: frontend

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: playwright-report
          path: frontend/playwright-report/

      - name: Cleanup
        if: always()
        run: docker compose -f deploy/docker-compose.test.yml down -v
```

### 10.7 Release Workflow

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags: ['v*']

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # Run all tests before publishing
      - name: Run full test suite
        run: |
          docker compose -f deploy/docker-compose.test.yml up -d --wait
          # Run backend tests
          pip install -e backend/ -e common/
          pytest backend/tests/ backend/tests/api/ backend/tests/integration/
          # Run frontend tests
          pnpm vitest run --coverage
          docker compose -f deploy/docker-compose.test.yml down -v

      # Build and publish Docker images
      - name: Build & push backend
        uses: docker/build-push-action@v5
        with:
          context: backend
          push: true
          tags: modelprism/backend:${{ github.ref_name }}

      - name: Build & push frontend
        uses: docker/build-push-action@v5
        with:
          context: frontend
          push: true
          tags: modelprism/frontend:${{ github.ref_name }}

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v1
        with:
          generate_release_notes: true
```

---

## 11. Coverage Targets & Enforcement

### 11.1 Coverage Thresholds

| Component | Statements | Branches | Functions | Lines | Enforcement |
|---|---|---|---|---|---|
| **Backend — unit + API** | 80% | 75% | 80% | 80% | CI fail < threshold |
| **Backend — integration** | 50% | 40% | 50% | 50% | Monitored (info) |
| **Frontend — unit** | 70% | 65% | 70% | 70% | CI fail < threshold |
| **Frontend — pages** | 65% | 60% | 65% | 65% | CI fail < threshold |
| **Agent — unit** | 80% | 75% | 80% | 80% | CI fail < threshold |
| **Agent — integration** | 50% | 40% | 50% | 50% | Monitored (info) |

### 11.2 Coverage Configuration

**Backend** (`backend/pyproject.toml`):

```toml
[tool.coverage.run]
source = ["app"]
omit = ["app/main.py", "app/database.py", "**/migrations/**"]

[tool.coverage.report]
fail_under = 80
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if __name__ == .__main__.:",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]
```

**Frontend** (`frontend/vitest.config.ts`):

```typescript
coverage: {
  provider: 'v8',
  thresholds: {
    statements: 70,
    branches: 65,
    functions: 70,
    lines: 70,
  },
  exclude: [
    '**/*.d.ts',
    '**/types/**',
    'app/app.vue',
    'nuxt.config.ts',
    '**/*.config.*',
  ],
}
```

### 11.3 Coverage Exclusions (Explicit)

The following areas are explicitly excluded from coverage requirements with documented justification:

| Exclusion | Component | Justification |
|---|---|---|
| Alembic migration scripts | Backend | Generated, one-time use |
| Type definitions / interfaces | Frontend | No runtime logic |
| Error handler registry patterns | Backend | Boilerplate, tested via integration |
| Config loading (pydantic-settings) | Backend | Tested implicitly via `test_config.py` |
| `main.py` / `app.vue` | Both | Entry points, tested via E2E |

---

## 12. Test Data & Fixtures

### 12.1 Factory Pattern (Backend)

Backend tests use a factory pattern for creating test data:

```python
# backend/tests/factories.py
import uuid
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel

class AgentFactory:
    """Builder for agent test data. Supports build (dict) and create (DB) strategies."""

    @staticmethod
    def build(
        workspace_id: Optional[str] = None,
        status: str = "online",
        friendly_name: str = "test-agent",
        **overrides,
    ) -> dict:
        return {
            "id": str(uuid.uuid4()),
            "workspace_id": workspace_id or str(uuid.uuid4()),
            "friendly_name": friendly_name,
            "custom_name": None,
            "status": status,
            "agent_version": "0.1.0",
            "last_seen_at": datetime.now(timezone.utc).isoformat(),
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "hardware_info": {
                "gpu_model": "NVIDIA A100-SXM4-80GB",
                "gpu_count": 4,
                "vram_per_gpu_mb": 81200,
                "cpu_cores": 64,
                "ram_gb": 512,
                "disk_gb": 2048,
                "os": "Ubuntu 22.04",
                "driver_version": "550.54.15",
                "cuda_version": "12.4",
            },
            "hourly_rate_cents": 0,
            **overrides,
        }

    @staticmethod
    async def create(db_session, **overrides) -> "Agent":
        """Persist an agent to the test database."""
        data = AgentFactory.build(**overrides)
        agent = Agent(**data)
        db_session.add(agent)
        await db_session.commit()
        await db_session.refresh(agent)
        return agent
```

### 12.2 Seed Data

For integration and E2E tests, a seed script populates known test data:

```python
# backend/tests/seed.py
"""Seed known test data for integration and E2E tests."""

TEST_USER = {
    "email": "test@modelprism.io",
    "password": "test-password-123",
    "display_name": "Test User",
}

TEST_WORKSPACE = {
    "name": "Test Workspace",
    "slug": "test-workspace",
}

TEST_AGENT = {
    "friendly_name": "cyan-koala-42",
    "status": "online",
    "agent_version": "0.1.0",
    "hardware_info": {
        "gpu_model": "NVIDIA A100-SXM4-80GB",
        "gpu_count": 4,
        "vram_per_gpu_mb": 81200,
    },
}

TEST_METRICS_BATCH = [
    {
        "ts": datetime.now(timezone.utc) - timedelta(seconds=i * 2),
        "gpu_util": 50.0 + (i % 50),
        "vram_used_gb": 40.0,
        "vram_total_gb": 81.2,
    }
    for i in range(150)  # 5 minutes of 2s metrics
]
```

### 12.3 Fixture Guidelines

| Rule | Rationale |
|---|---|
| Always use `build` over `create` in unit tests | Faster — no DB round-trip |
| Use `create` in API tests | Need real DB persistence for endpoint testing |
| Use `conftest.py` for shared fixtures only | Reduces duplication across test files |
| One fixture factory per data model | `AgentFactory`, `UserFactory`, `WorkspaceFactory`, etc. |
| Factories produce valid defaults | Tests override only what's relevant to the scenario |
| Override via `**overrides` dict | Clean, explicit test setup |

---

## 13. Performance & Load Testing

### 13.1 Load Testing Strategy

Load tests target NFR1 (Performance) and NFR2 (Reliability) requirements. They run in a dedicated CI environment or on-demand.

| Test | Tool | Target | Threshold |
|---|---|---|---|
| Backend REST throughput | locust | 1000 req/s | P99 < 200ms |
| WebSocket connections | Custom script | 5000 concurrent | P99 broadcast < 500ms |
| Agent metric ingestion | locust | 100 agents × 2s | 500 metrics/s ingested |
| OpenAI proxy throughput | locust | 500 concurrent proxy reqs | P99 TTFT < original + 50ms |
| API key rate limiting | locust | Burst of 200 reqs | Correct 429 after limit hit |
| Database query performance | pgbench / custom | All query patterns | P99 < 100ms |
| Frontend page render | Lighthouse CI | All dashboard pages | LCP < 2s |

### 13.2 Locust Test Structure

```python
# backend/tests/load/locustfile.py
from locust import HttpUser, task, between, WebSocketUser
import json
import uuid

class DashboardApiUser(HttpUser):
    """Simulates a dashboard user browsing the platform."""
    wait_time = between(1, 5)

    def on_start(self):
        self.token = self.login()

    def login(self):
        resp = self.client.post("/api/auth/login", json={
            "email": "loadtest@modelprism.io",
            "password": "loadtest",
        })
        return resp.json()["access_token"]

    @task(5)
    def list_agents(self):
        self.client.get("/api/v1/agents", headers={"Authorization": f"Bearer {self.token}"})

    @task(3)
    def get_agent_details(self):
        self.client.get("/api/v1/agents/ag_001", headers={"Authorization": f"Bearer {self.token}"})

    @task(2)
    def list_models(self):
        self.client.get("/api/v1/models", headers={"Authorization": f"Bearer {self.token}"})

    @task(1)
    def list_benchmarks(self):
        self.client.get("/api/v1/benchmarks", headers={"Authorization": f"Bearer {self.token}"})


class ProxyUser(HttpUser):
    """Simulates an API proxy consumer."""
    wait_time = between(0.5, 2)

    def on_start(self):
        self.api_key = "sk_loadtest_key"

    @task(10)
    def chat_completion(self):
        self.client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 50,
            },
        )

    @task(5)
    def chat_completion_stream(self):
        self.client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 50,
                "stream": True,
            },
        )
```

### 13.3 WebSocket Load Testing

```python
# backend/tests/load/ws_load_test.py
"""Test WebSocket scalability with 100+ simulated agents."""
import asyncio
import websockets
import json
import time

async def simulate_agent(agent_id: str, backend_url: str):
    """Simulate one agent pushing metrics every 2 seconds."""
    async with websockets.connect(
        f"{backend_url}/ws/agents/{agent_id}"
    ) as ws:
        for _ in range(150):  # 5 minutes
            await ws.send(json.dumps({
                "type": "metrics",
                "ts": time.time(),
                "gpu": [{"index": 0, "util_pct": 50, "mem_used_mb": 40000}],
            }))
            await asyncio.sleep(2)

async def main():
    backend_url = "ws://localhost:8000"
    agents = [simulate_agent(f"ag_{i:03d}", backend_url) for i in range(100)]
    await asyncio.gather(*agents)

asyncio.run(main())
```

---

## 14. Security Testing

### 14.1 Security Test Categories

| Category | Tool | Frequency |
|---|---|---|
| Dependency scanning | `pip-audit` / `npm audit` / Dependabot | Weekly (automated) |
| SAST (Static Analysis) | `bandit` (Python) / `eslint-plugin-security` | Every PR |
| Secret scanning | `trufflehog` / GitHub secret scanning | Every push |
| API fuzzing | Custom pytest fuzz tests | Per release |
| SQL injection | Custom test matrix | Per release |
| XSS in frontend | `vue-eslint-plugin` (no-unsafe-*) | Every PR |

### 14.2 Security Test Scenarios

```python
# backend/tests/api/test_security.py
class TestSecurity:

    async def test_sql_injection_agent_list(self, client):
        """SQL injection in filter parameter is rejected."""
        response = await client.get(
            "/api/v1/agents?filter[name]=' OR 1=1; --"
        )
        assert response.status_code == 400

    async def test_sql_injection_sort(self, client):
        """SQL injection in sort parameter is rejected."""
        response = await client.get(
            '/api/v1/agents?sort=created-at; DROP TABLE agents; --'
        )
        assert response.status_code == 400

    async def test_no_plaintext_passwords(self, db_session):
        """All stored passwords are bcrypt hashes."""
        users = await db_session.execute("SELECT password_hash FROM users")
        for (hash_,) in users:
            assert hash_.startswith("$2b$") or hash_.startswith("$2a$")

    async def test_no_plaintext_api_keys(self, db_session):
        """All API keys are stored as SHA-256 hashes."""
        keys = await db_session.execute("SELECT key_hash FROM api_keys")
        for (hash_,) in keys:
            assert len(hash_) == 64  # SHA-256 hex digest

    async def test_no_plaintext_tokens(self, db_session):
        """Agent tokens are stored as SHA-256 hashes."""
        agents = await db_session.execute("SELECT token_hash FROM agents")
        for (hash_,) in agents:
            assert len(hash_) == 64

    async def test_cors_headers(self, client):
        """CORS headers are correct."""
        response = await client.options("/api/v1/agents")
        assert response.headers["access-control-allow-origin"] == "*"

    async def test_rate_limit_brute_force(self, client):
        """Repeated failed logins trigger lockout."""
        for _ in range(5):
            resp = await client.post("/api/auth/login", json={
                "email": "test@example.com",
                "password": "wrong",
            })
        resp = await client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "correct",
        })
        assert resp.status_code == 423  # Locked

    async def test_jwt_tampering(self, client):
        """Tampered JWT is rejected."""
        tampered_token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiJ9.tampered"
        response = await client.get(
            "/api/v1/agents",
            headers={"Authorization": f"Bearer {tampered_token}"},
        )
        assert response.status_code == 401

    async def test_password_reset_token_brute_force(self, client):
        """Password reset tokens are rate-limited."""
        for _ in range(10):
            resp = await client.post("/api/auth/reset-password/confirm", json={
                "token": "brute-force-attempt",
                "password": "newpassword",
            })
        # Last attempt should be rate-limited
        assert resp.status_code == 429

    async def test_workspace_data_isolation(self, client):
        """User from workspace A cannot access workspace B data."""
        # See test_workspace_isolation.py for detailed tests
        pass
```

### 14.3 Security Audit Workflow

```yaml
# .github/workflows/security-audit.yml
name: Security Audit

on:
  schedule:
    - cron: '0 6 * * 1'  # Every Monday
  workflow_dispatch:

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install bandit pip-audit
      - run: bandit -r backend/ -f json -o bandit-report.json
      - run: pip-audit -r backend/requirements.txt
      - run: npm audit --prefix frontend
      - uses: actions/upload-artifact@v4
        with:
          name: security-reports
          path: |
            bandit-report.json
            npm-audit-report.json
```

---

## 15. Glossary

| Term | Definition |
|---|---|
| **JSON:API** | A specification for building APIs in JSON. ModelPrism uses it for all Dashboard REST endpoints. |
| **TestClient** | FastAPI's built-in HTTP client for testing, based on httpx. |
| **MSW** | Mock Service Worker — intercepts HTTP requests in the browser/test environment. |
| **TestContainer** | Python library that runs Docker containers for integration testing. |
| **respx** | HTTP mock library for Python, designed for httpx. |
| **fakeredis** | In-memory Redis implementation for testing without a real Redis server. |
| **uPlot** | Fast, lightweight (22KB) charting library used for real-time GPU metrics. |
| **ECharts** | Feature-rich charting library used for benchmark comparisons and billing. |
| **locust** | Python-based load testing framework. |
| **Playwright** | Microsoft's browser automation framework for E2E testing. |
| **LCP** | Largest Contentful Paint — a Core Web Vitals metric for page load performance. |
| **TTFT** | Time to First Token — latency metric for LLM inference. |
| **TPOT** | Time per Output Token — per-token generation latency. |
| **SAST** | Static Application Security Testing — analyzing source code for vulnerabilities. |
