# F1: Backend Scaffolding

## Metadata
- **ID:** F1
- **Phase:** Foundation
- **Effort:** Medium
- **Dependencies:** None
- **Acceptance Criteria Count:** 5

## Description
Set up the FastAPI backend skeleton including application entry point, Pydantic-settings configuration, SQLAlchemy async engine with PostgreSQL, Redis connection pool, async lifespan management, structured logging, and a health-check endpoint. This is the foundation all other backend features build on.

## Concrete Examples (Specification by Example)

### Example 1: Application Startup with Health Check
- **Input:** Server starts via `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **Action:** The async lifespan handler initializes the SQLAlchemy async engine (connects to PostgreSQL), establishes a Redis connection pool, sets up the root logger, and declares the application ready.
- **Expected Output:** `GET /api/health` returns `{"status": "ok", "database": "connected", "redis": "connected", "version": "0.1.0"}` with HTTP 200.

### Example 2: Database Connection Failure on Startup
- **Input:** PostgreSQL is unreachable (e.g., wrong host/port or service not running) when the server starts.
- **Action:** The lifespan handler attempts to connect to PostgreSQL, fails, logs the error with full traceback to stderr, and shuts down gracefully without leaving a zombie process.
- **Expected Output:** The server process exits with a non-zero exit code within 10 seconds. The startup log shows `ERROR` — `"Failed to connect to database: could not connect to server"`. No half-initialized server serves traffic.

### Example 3: Redis Connection Failure (Non-Blocking)
- **Input:** Redis is unreachable (e.g., wrong port or Redis not running) but PostgreSQL is available.
- **Action:** The lifespan handler successfully connects to PostgreSQL, logs a `WARNING` about the Redis failure, and continues startup in reduced-functionality mode (rate-limiting and pub/sub features are disabled).
- **Expected Output:** Health check returns `{"status": "degraded", "database": "connected", "redis": "disconnected", "version": "0.1.0"}` with HTTP 200. The server runs and serves API endpoints that don't depend on Redis.

### Example 4: Graceful Shutdown
- **Input:** The server receives SIGTERM (e.g., `kill <pid>` or Docker `stop`).
- **Action:** The lifespan handler catches the shutdown signal, drains active HTTP connections (max 30s grace period), closes the database engine, closes the Redis connection pool, and exits.
- **Expected Output:** In-flight requests complete or time out with 503 within the grace period. No new requests are accepted after shutdown begins. All database connections are released. Server exits with code 0.

### Example 5: Configuration from Environment Variables
- **Input:** A `.env` file containing `DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/modelprism`, `REDIS_URL=redis://localhost:6379/0`, `SECRET_KEY=dev-secret-key-change-in-production`, and `MODELPRISM_CLOUD=false`
- **Action:** The `Settings` class (using `pydantic-settings`) reads and validates all values on import. Invalid URLs or missing required keys cause a `ValidationError` with a descriptive message.
- **Expected Output:** `Settings().database_url` resolves to the async PostgreSQL URL. `Settings().redis_url` resolves to the Redis URL. `Settings().cloud_mode` is `False`. If `SECRET_KEY` is missing, a `ValidationError` is raised at import time: `"Field required [type=missing, input_value={...}, input_type=dict]"`.

## Acceptance Criteria

- **ACF1-1: Health endpoint reports correct status** — `GET /api/health` returns `{"status": "ok"}` and `{"database": "connected"}` when all services are reachable, `"degraded"` when Redis is down, and never returns `"ok"` when the database connection failed during startup.
- **ACF1-2: All required env vars fail fast** — Starting the app without `DATABASE_URL`, `SECRET_KEY`, or `REDIS_URL` causes a `ValidationError` at import time with a clear message identifying which variable is missing.
- **ACF1-3: Database engine is async-ready** — The SQLAlchemy engine is configured with `AsyncSession` (`async_sessionmaker`), uses `asyncpg` as the driver, and exposes a `get_db` dependency that yields an `AsyncSession` per request with proper `commit`/`rollback`/`close` lifecycle.
- **ACF1-4: Graceful shutdown releases all connections** — On SIGTERM/SIGINT, the lifespan handler closes the database engine and Redis pool, and the server exits within 30 seconds without orphaned connections or zombie processes.
- **ACF1-5: Structured logging is configured** — Log output uses JSON format (timestamp, level, module, message) via a logging configuration that can be toggled to plain-text in development. Each HTTP request is logged with method, path, status code, and duration (ms).

## Technical Notes

- **Lifespan pattern:** Use FastAPI's `lifespan` context manager (not the deprecated `on_event` decorators). The lifespan yields after successful initialization; on exit it performs cleanup.
- **Database engine:** Use `create_async_engine` with `pool_size=20`, `max_overflow=10`, and `pool_pre_ping=True`. Configure `async_sessionmaker(engine, expire_on_commit=False)`.
- **Settings:** Use `pydantic-settings` with `SettingsConfigDict(env_file=".env")`. Group settings into nested models: `DatabaseSettings`, `RedisSettings`, `AuthSettings`, `AppSettings`. The top-level `Settings` class composes them. Validate `DATABASE_URL` scheme must be `postgresql+asyncpg`.
- **Redis:** Use `redis.asyncio.Redis` with `connection_pool` for connection pooling. Expose a `get_redis` dependency that returns the shared connection. Initialize in lifespan, close on shutdown.
- **CORS:** Configure `CORSMiddleware` to allow the frontend origin (configured via `CORS_ORIGINS` env var, default `http://localhost:3000`). Allow credentials and all common methods/headers.
- **Redis health check:** Run `PING` during startup health verification. If Redis is unavailable, log warning and continue — the app operates in degraded mode (no rate-limiting, no pub/sub).
- **Structured logging:** Use Python's `logging` with a custom JSON formatter for production and a standard `StreamHandler` for development. Correlate request logs using a `correlation_id` middleware that reads/generates a UUID per request and adds it to the log record.
- **Integration point — F3 (Database schema):** This scaffolding provides the engine and session factory. F3 will define the actual ORM models and Alembic migrations, using the engine configured here.
- **Integration point — F5 (Auth):** The JWT secret and token settings configured here will be consumed by the auth routes in F5.
- **Error handling:** Register a global exception handler for `HTTPException` and `ValidationError` that returns JSON:API error format (`application/vnd.api+json`). The health endpoint is an exception — it returns standard `application/json`.
- **Startup banner:** On successful startup, log a banner showing the version, environment (cloud/self-hosted), database URL host, and Redis URL host (sanitized — no credentials in logs).
