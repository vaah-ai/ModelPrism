---
title: Codebase Structure Reference
purpose: Directory tree for ModelPrism
---

# Codebase Structure

```
{{PROJECT_ROOT}}/
├── backend/                          # FastAPI backend
│   ├── app/
│   │   ├── main.py                   # FastAPI app entry, lifespan events
│   │   ├── config.py                 # Settings (pydantic-settings)
│   │   ├── database.py               # SQLAlchemy engine + session
│   │   ├── models/                   # SQLAlchemy ORM models
│   │   ├── schemas/                  # Pydantic request/response schemas
│   │   │   ├── jsonapi.py            # JSON:API base serializers
│   │   │   └── filters.py            # JSON:API filter/sort parser
│   │   ├── api/                      # Route handlers
│   │   ├── services/                 # Business logic
│   │   ├── ws/                       # WebSocket handlers
│   │   ├── middleware/               # Auth, rate limiting
│   │   └── utils/                    # Crypto, naming helpers
│   ├── alembic/                      # Database migrations
│   ├── tests/
│   └── requirements.txt
│
├── frontend/                         # Nuxt 4 application
│   ├── app/
│   │   ├── app.vue
│   │   ├── layouts/
│   │   ├── pages/
│   │   ├── components/
│   │   └── composables/
│   ├── server/api/                   # Nitro API routes (thin)
│   ├── stores/                       # Pinia stores
│   ├── nuxt.config.ts
│   └── package.json
│
├── modelprism-agent/                 # Agent Python package (on GPU servers)
│   ├── modelprism_agent/
│   │   ├── main.py                   # Entry point
│   │   ├── config.py
│   │   ├── registration.py           # Register with backend
│   │   ├── metrics/                  # Collector, GPU, system, vLLM parsers
│   │   ├── manager/                  # Docker, vLLM, model downloader
│   │   ├── benchmark/
│   │   ├── connection.py             # WebSocket client
│   │   ├── command_handler.py
│   │   └── log_streamer.py
│   └── requirements.txt
│
├── common/                           # Shared code backend + agent
│   └── modelprism_common/schemas/    # Shared Pydantic models
│
├── deploy/                           # Docker Compose, nginx, install script
├── docs/                             # Developer guides
├── requirements/                     # Product requirements ({{REQUIREMENTS_DIR}})
├── ai-milestones-and-tasks/          # Milestone and task tracking ({{MILESTONES_DIR}})
├── ai-prompts/                       # Generated AI prompts
└── ai-base-prompts/                  # Base prompt templates (submodule)
```
