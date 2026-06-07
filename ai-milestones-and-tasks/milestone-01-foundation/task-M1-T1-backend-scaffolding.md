# Task M1-T1 — Backend Scaffolding

> **Milestone:** M1 (Foundation)
> **Priority:** Critical
> **Status:** ⚪ Not Started
> **Estimated Effort:** 2 days

## Description

Create the FastAPI backend project structure under `ModelPrism/backend/`. This includes the ASGI application entry point, Pydantic-based configuration via `pydantic-settings`, SQLAlchemy async engine setup with PostgreSQL, Redis connection for caching and pub/sub, CORS middleware, health check endpoint, and the full project directory scaffold.

## Task Goals

- Create `backend/` directory with the full project structure matching `requirements/07-directory-structure.md`
- Set up FastAPI app with lifespan events for PostgreSQL and Redis connection management
- Implement `pydantic-settings` configuration (`.env` support, typed settings)
- Configure async SQLAlchemy engine with PostgreSQL session factory
- Create Redis connection manager (used for pub/sub and caching)
- Add CORS middleware (allow dashboard origin)
- Add health check endpoint: `GET /api/health`
- Add Prometheus metrics endpoint for the backend itself

## Implementation Plan

> ⚠️ Analyze this plan thoroughly before implementing. Invoke relevant skills and MCP servers as needed.

### Pre-Implementation Analysis

- Review `requirements/05-tech-stack.md` for exact version requirements (Python 3.11+, FastAPI, SQLAlchemy 2.0+, Pydantic v2)
- Review `requirements/07-directory-structure.md` for the exact `backend/` directory layout
- Review `requirements/02-architecture-overview.md` for deployment model context
- Review `requirements/04-non-functional-requirements.md` for NFR4.2 (deployment) and NFR4.3 (monitoring)
- Invoke `fastapi-expert` skill for FastAPI async patterns and SQLAlchemy async setup

### Steps

1. Create `backend/` directory structure: `app/`, `app/models/`, `app/schemas/`, `app/api/`, `app/services/`, `app/ws/`, `app/middleware/`, `app/utils/`, `alembic/`, `tests/`
2. Create `backend/pyproject.toml` with dependencies: fastapi, uvicorn[standard], sqlalchemy[asyncio], asyncpg, pydantic-settings, redis[hiredis], prometheus-client, python-jose, bcrypt, httpx, alembic
3. Implement `backend/app/__init__.py` and `backend/app/config.py` with `Settings` class using `pydantic-settings`:
   - `DATABASE_URL` (PostgreSQL)
   - `REDIS_URL`
   - `JWT_SECRET`
   - `CORS_ORIGINS`
   - `MODELPRISM_CLOUD` boolean
4. Implement `backend/app/database.py`: async SQLAlchemy `create_async_engine`, `async_sessionmaker`, `AsyncSession` dependency
5. Implement `backend/app/redis.py`: Redis connection pool, `get_redis` dependency, pub/sub helper
6. Implement `backend/app/main.py`: FastAPI app with lifespan, CORS middleware, health endpoint at `/api/health`, include all API routers (initially empty)
7. Add Prometheus metrics middleware at `/metrics`
8. Create `requirements.txt` and `pyproject.toml` with Python 3.11+ constraint
9. Create `backend/Dockerfile` for the backend service
10. Create `backend/.env.example` with placeholder values

### Skills & MCP Servers

| Resource              | Purpose                      | When to Invoke                   |
| --------------------- | ---------------------------- | -------------------------------- |
| `fastapi-expert`      | FastAPI async setup          | Steps 2-7 — backend scaffolding  |
| `filesystem` (MCP)    | File creation                | Creating all project files       |

## Acceptance Criteria

- [ ] `uvicorn backend.app.main:app` starts successfully
- [ ] `GET /api/health` returns `{"status": "ok", "database": "connected", "redis": "connected"}`
- [ ] PostgreSQL connection works via async SQLAlchemy
- [ ] Redis connection works (ping succeeds)
- [ ] CORS headers allow requests from configured origins
- [ ] All settings load from `.env` file with defaults
- [ ] Dockerfile builds without errors

## Completion Criteria

- [ ] All acceptance criteria above pass
- [ ] Python type check passes (`mypy`)
- [ ] Code passes linting (`ruff`)
- [ ] Basic startup test passes (app starts, health responds)

## Testing Checklist

- [ ] Unit test for config loading from environment
- [ ] Unit test for database engine creation
- [ ] Unit test for health endpoint response
- [ ] Integration test: startup → health check → shutdown

## Dependencies

- **Requires:** None (first task)
- **Blocks:** M1-T2 (Database Schema), M1-T3 (Agent Registration), M1-T6 (Metric Storage)

## Documentation References

- `requirements/05-tech-stack.md` — technology versions
- `requirements/07-directory-structure.md` — directory layout
- `requirements/02-architecture-overview.md` — architecture context
- `requirements/04-non-functional-requirements.md` — NFR4.2, NFR4.3

## Notes

- Use async SQLAlchemy throughout (not sync)
- Redis connection should use `redis.asyncio` client
- Keep the app modular — routers will be added in subsequent tasks
- Use environment-based configuration — no hardcoded secrets
- The Dockerfile should use multi-stage build for smaller image size
