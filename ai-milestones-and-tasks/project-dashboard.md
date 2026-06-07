# ModelPrism — Milestone & Task Dashboard

> **Project:** ModelPrism — Open Source GPU Inference Platform
> **Current Phase:** MVP (Foundation)
> **Last Updated:** 2026-06-07

## Milestones

| ID | Title | Status | Priority | Tasks | Dependencies |
|----|-------|--------|----------|-------|--------------|
| M1 | Foundation — Backend + Agent + Dashboard | 🔵 In Progress | Critical | 5/9 🟢 Complete | None |

### M1 Task Status

| ID | Title | Status | Priority | Effort | Dependencies |
|----|-------|--------|----------|--------|--------------|
| M1-T1 | Backend Scaffolding | 🟢 Complete | Critical | 2 days | None |
| M1-T2 | Database Schema | 🟢 Complete | Critical | 3 days | M1-T1 |
| M1-T3 | Agent Registration API | 🟢 Complete | Critical | 2 days | M1-T1, M1-T2 |
| M1-T4 | Agent WebSocket Handler | 🟢 Complete | Critical | 3 days | M1-T3 |
| M1-T5 | Agent Package | 🟢 Complete | Critical | 4 days | M1-T4 |
| M1-T6 | Metric Storage + API | ⚪ Not Started | High | 3 days | M1-T1, M1-T2, M1-T4 |
| M1-T7 | Dashboard WS Broadcast | ⚪ Not Started | High | 2 days | M1-T4, M1-T6 |
| M1-T8 | Nuxt Dashboard Scaffold | ⚪ Not Started | Critical | 2 days | None |
| M1-T9 | Dashboard Pages | ⚪ Not Started | High | 4 days | M1-T7, M1-T8 |

## Backlog

> _No backlog items yet._

## Notes

- **Architecture:** Agent → WebSocket/REST → FastAPI Backend → Nuxt Dashboard
- **MVP Goal:** A simple agent installed on a GPU server, a simple FastAPI backend to register GPU servers and store server metrics, a simple Nuxt dashboard consuming the FastAPI directly (no Nitro API).
- **Requirements:** `/Users/pk/Projects/ModelPrism/requirements/`
- **Dashboard app:** `/Users/pk/Projects/ai-models-hosting/dashboard-gpu-server/`
- **Agent submodule:** `/Users/pk/Projects/ModelPrism/modelprism-agent/`
- **Planner prompt:** `/Users/pk/Projects/ModelPrism/ai-prompts/prompt-ai-milestones-tasks-planner.md`
- **Milestone M1 folder:** `/Users/pk/Projects/ModelPrism/ai-milestones-and-tasks/milestone-01-foundation/`
- **M1 tasks:** 9 tasks total, estimated ~3-4 weeks effort
- **Architecture decision:** Dashboard consumes FastAPI directly (`nitro: false` in Nuxt config)
