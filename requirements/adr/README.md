# Architecture Decision Records (ADRs)

This directory documents key architectural decisions made during requirements analysis.

| ADR | Decision | Context |
|-----|----------|---------|
| [ADR-001: JSON:API Scope](./ADR-001-jsonapi-scope.md) | JSON:API for dashboard REST only; lightweight format for agent WS + proxy | Reduces implementation cost while maintaining standardized dashboard API |
| [ADR-002: Docker for vLLM](./ADR-002-docker-vllm.md) | Docker mandatory for vLLM isolation | Prevents orphan GPU processes, enables resource limits, port management |
| [ADR-003: Auth Approach](./ADR-003-auth-approach.md) | Custom Pinia composable + FastAPI JWT (no sidebase/nuxt-auth) | Avoids framework lock-in, simpler integration with FastAPI backend |
| [ADR-004: Monetization Model](./ADR-004-monetization.md) | Open core — core OSS, cloud-only features separate | Maximizes adoption while enabling sustainable monetization |
| [ADR-005: Data Retention](./ADR-005-data-retention.md) | Configurable per-workspace with downsampled PostgreSQL tables | Gives users control, avoids infinite storage growth |
