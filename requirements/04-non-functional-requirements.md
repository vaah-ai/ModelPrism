# Non-Functional Requirements

## NFR1 — Performance

### NFR1.1 Real-Time Metrics
- Dashboard metrics refresh every 2 seconds
- WebSocket latency from agent → backend → browser: < 500ms (p99)
- Agent metric collection overhead: < 50ms per poll cycle (non-blocking)

### NFR1.2 Dashboard Loading
- Initial page load (SPA): < 2 seconds on reasonable connection
- Chart rendering: < 50ms for 150 data points (live view)
- Chart rendering: < 200ms for 10,000 data points (historical view)
- Time range switching: < 1 second to fetch and render
- Live dashboard: client accumulates incoming WebSocket metrics for 500ms, then batch-renders in a single cycle
- uPlot used for high-frequency real-time charts; ECharts for comparison/billing views

### NFR1.3 Agent Overhead
- Agent CPU usage on GPU server: < 1% of a single core
- Agent memory usage: < 150MB (excluding model weights)
- Agent disk usage: < 100MB for agent binary + logs
- Zero interference with vLLM inference performance

### NFR1.4 Backend Scalability
- Support 100+ GPU servers from a single backend instance
- Support 10,000+ concurrent WebSocket connections
- PostgreSQL handles 1M+ usage records per month
- Redis handles 10,000+ rate limit checks per second

## NFR2 — Reliability

### NFR2.1 Agent Resiliency
- Agent auto-reconnects to backend on network failure (exponential backoff: 1s, 2s, 4s, 8s, max 60s)
- Agent buffers up to 60 seconds of metrics during disconnection and replays on reconnect
- Agent survives backend restarts (reconnects automatically)
- Agent process is supervised (systemd or PM2) — restarts on crash
- Agent startup is idempotent — safe to restart

### NFR2.2 Backend Resiliency
- Graceful degradation if PostgreSQL is unavailable (cache recent metrics in Redis)
- Rate limiter failure mode: allow requests if Redis is down (fail-open for self-hosted)
- WebSocket server handles partial disconnections without leaking connections
- All API endpoints return consistent error shapes

### NFR2.3 Data Durability
- Metric data downsampled and persisted to PostgreSQL
- Raw metrics retained for short window (5 minutes in memory), sampled for longer retention
- No data loss on agent crash (buffered metrics may lose last 2 seconds)
- Database backups supported via standard PostgreSQL tooling
- Data retention policies enforced by background cleanup job (daily)
- Retention periods configurable per workspace in dashboard Settings UI

## NFR3 — Security

### NFR3.1 API Key Security
- Agent registration tokens are single-use, expire after 24 hours
- API keys stored as bcrypt/SHA-256 hashes — never in plaintext
- Only first 8 characters of API key stored for lookup prefix
- All API traffic over TLS/HTTPS in production
- Rate limiting prevents brute-force key guessing

### NFR3.2 Authentication
- Passwords hashed with bcrypt (cost factor 12)
- JWT tokens with 24-hour expiry, refresh tokens with 30-day expiry
- CSRF protection for browser-based requests
- Session invalidation on password change

### NFR3.3 Multi-Tenant Isolation
- Workspace-scoped data access — no cross-workspace data leakage
- All database queries scoped by workspace_id
- API keys are workspace-scoped — cannot access other workspace's models
- Audit log for sensitive operations (key creation, model deployment, user role changes)

### NFR3.4 Network Security
- Agent initiates outbound connection only (no inbound ports required)
- Backend-to-agent communication over TLS WebSocket (WSS)
- Optional mTLS for self-hosted deployments
- No agent-to-agent communication (all traffic through backend)

## NFR4 — Maintainability

### NFR4.1 Code Quality
- Python backend: type-annotated, Pydantic-validated, test coverage > 80%
- Nuxt frontend: TypeScript throughout, Pinia stores for state
- Shared type definitions between agent and backend in a common package
- Documentation: README, ARCHITECTURE.md, API docs (OpenAPI/Swagger)

### NFR4.2 Deployment
- Backend: single Docker image, or uvicorn behind systemd
- Frontend: static files served via nginx, or Docker image with Nuxt SSR
- Agent: single binary or pip-installable Python package
- Docker Compose for full self-hosted deployment (PostgreSQL, Redis, Backend, Frontend)
- Environment-based configuration (no hardcoded secrets)

### NFR4.3 Monitoring & Observability
- Backend health check endpoint: `GET /api/health`
- Prometheus metrics endpoint for backend itself
- Structured logging (JSON format) for log aggregation
- Agent logs: local file + optional remote log shipping
- Agent health: systemd service status, watchdog timer

## NFR5 — Portability

### NFR5.1 GPU Server Requirements
- Linux (Ubuntu 22.04+, Debian 12+, RHEL 9+)
- NVIDIA GPU with CUDA 12.0+
- NVIDIA Container Toolkit (for Docker-based vLLM)
- Python 3.10+ for agent
- Docker (optional, for containerized vLLM)
- vLLM installed (or installed by agent)

### NFR5.2 Frontend Requirements
- Modern browser (Chrome, Firefox, Safari, Edge — last 2 major versions)
- JavaScript enabled
- WebSocket support
- No Flash or plugins required

### NFR5.3 Backend Requirements
- Linux or macOS (production: Linux)
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- 2GB RAM minimum, 4GB recommended
- 10GB disk for application + logs

## NFR6 — Open Source

### NFR6.1 Licensing
- Apache 2.0 or MIT license
- Standard CLA for contributors (optional, evaluate need)
- Third-party dependencies compatible with chosen license

### NFR6.2 Community
- GitHub repository with clear CONTRIBUTING.md
- Issue templates (bug report, feature request, question)
- Discussion forum or Discord server for community
- Release workflow: semantic versioning, changelog, GitHub releases
- CI/CD: lint, type-check, test on PR; publish Docker images on tag

### NFR6.3 Documentation
- README: what it is, quick start, screenshot
- Installation guide: self-hosted Docker Compose, manual
- User guide: all dashboard features explained
- Agent installation guide: supported OS, GPU requirements
- API reference: OpenAPI spec for all endpoints
- Contributing guide: dev environment setup, code style, PR process
