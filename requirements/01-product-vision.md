# Product Vision

## ModelPrism — Open Source GPU Inference Platform

**Tagline:** Your models, refracted.

### One-Sentence Description

ModelPrism is an open-source platform that lets you deploy, monitor, manage, and monetize LLM inference across your GPU cluster — with model deployment, real-time dashboards, benchmarking, an OpenAI-compatible API proxy, user management, and usage-based billing.

### Core Problem

Organizations running self-hosted LLM inference (vLLM on private GPUs) face a fragmented toolchain:

- No unified dashboard across multiple GPU servers
- Manual model deployment — SSH into each server, configure vLLM flags by hand
- No built-in benchmarking or capacity planning
- No API key management or usage tracking for internal teams/customers
- No easy way to proxy and bill OpenAI/Anthropic alongside self-hosted models

Each team reinvents the same glue code. ModelPrism replaces this with a single open-source platform.

### Scope

- **Phase 1 (current):** vLLM GPU monitoring dashboard (existing codebase)
- **Phase 2 (in development):** Full platform with model deployment, agent-based GPU management, benchmarking, optimization
- **Phase 3 (future):** Multi-tenant API proxy with key management, user invites, usage-based billing

### Open Source Commitment

ModelPrism follows an **open core** model:
- **Core platform** (agent, dashboard, model management, benchmarking, monitoring) — fully open source (Apache 2.0)
- **Cloud features** (multi-tenant API proxy, usage analytics, billing) — available in the hosted SaaS version
- Users can self-host the entire core stack (frontend + backend + agents) on their own infrastructure
- A hosted cloud version is available for users who want a managed experience with full feature access

### Target Audience

1. **ML teams** running vLLM on private GPU servers who need a management UI
2. **DevOps/platform engineers** managing GPU clusters for internal AI products
3. **Startups/SMBs** offering LLM inference to their own customers via API
4. **Hobbyists** with one or more GPUs running models at home
