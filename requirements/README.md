# ModelPrism Requirements

This directory contains the product requirements for **ModelPrism** — the open-source GPU inference management platform.

## Documents

| File | Description |
|------|-------------|
| [01-product-vision.md](./01-product-vision.md) | Product vision, scope, target audience |
| [02-architecture-overview.md](./02-architecture-overview.md) | System architecture, deployment models, data flow |
| [03-functional-requirements.md](./03-functional-requirements.md) | Detailed functional requirements by feature area |
| [04-non-functional-requirements.md](./04-non-functional-requirements.md) | Performance, security, reliability, portability requirements |
| [05-tech-stack.md](./05-tech-stack.md) | Technology choices with rationale |
| [06-api-surface.md](./06-api-surface.md) | API endpoints overview |
| [07-directory-structure.md](./07-directory-structure.md) | Repository directory structure |

## Current Focus

Phase 2 — Agent-based architecture with:
- modelprism-agent installable on any GPU server via `curl | bash`
- Central FastAPI backend receiving metrics from agents
- Nuxt 4 frontend hosted anywhere (Vercel, self-hosted, static)
- Real-time WebSocket metrics from agent → backend → browser
- Model deployment and management from the dashboard
