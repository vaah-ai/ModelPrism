# ModelPrism — Milestone & Task Dashboard

> **Project:** ModelPrism — Open Source GPU Inference Platform
> **Current Phase:** MVP (Foundation)
> **Last Updated:** 2026-06-07

## Milestones

| ID | Title | Status | Priority | Tasks | Dependencies |
|----|-------|--------|----------|-------|--------------|
| M1 | Foundation — Backend + Agent + Dashboard | 🔵 In Progress | Critical | 7/9 tasks 🟢 (6 sub-tasks ⚪) | None |

### M1 Task Status

| ID | Title | Status | Priority | Effort | Dependencies |
|----|-------|--------|----------|--------|--------------|
| M1-T1 | Backend Scaffolding | 🟢 Complete | Critical | 2 days | None |
| M1-T2 | Database Schema | 🟢 Complete | Critical | 3 days | M1-T1 |
| M1-T3 | Agent Registration API | 🟢 Complete | Critical | 2 days | M1-T1, M1-T2 |
| M1-T4 | Agent WebSocket Handler | 🟢 Complete | Critical | 3 days | M1-T3 |
| M1-T5 | Agent Package | 🟢 Complete | Critical | 4 days | M1-T4 |
| M1-T6 | Metric Storage + API | 🟢 Complete | High | 3 days | M1-T1, M1-T2, M1-T4 |
| M1-T7 | Dashboard WS Broadcast | 🟢 Complete | High | 2 days | M1-T4, M1-T6 |
| M1-T8 | Nuxt Dashboard Scaffold | 🟢 Complete | Critical | 2 days | None |
| M1-T9 | Dashboard Pages | 🟢 Complete | High | 6 days | M1-T7, M1-T8 |

#### M1-T9 Sub-Tasks

| ID | Title | Status | Effort | Dependencies | Priority |
|----|-------|--------|--------|--------------|----------|
| M1-T9-01 | Shared Types, Utils & Common Components (MetricCard, StatusBadge, GpuBar) | 🟢 Complete | 0.5d | None | Critical |
| M1-T9-02 | Dashboard Components (SystemResources, QueueDiagnostics, ModelList) | 🟢 Complete | 1d | M1-T9-01 | High |
| M1-T9-03 | uPlot Real-Time Charts (GpuMetricsChart) | 🟢 Complete | 1.5d | M1-T9-01 | High |
| M1-T9-04 | Live Log Viewer (LiveLog) | 🟢 Complete | 1d | M1-T9-01 | Medium |
| M1-T9-05 | Store Wiring + Overview Page | 🟢 Complete | 1d | M1-T9-01, M1-T9-02 | High |
| M1-T9-06 | Detail Page Assembly | 🟢 Complete | 1d | M1-T9-01 through M1-T9-05 | High |

## Backlog

> _No backlog items yet._

## Notes

- **Architecture:** Agent → WebSocket/REST → FastAPI Backend → Nuxt Dashboard
- **MVP Goal:** A simple agent installed on a GPU server, a simple FastAPI backend to register GPU servers and store server metrics, a simple Nuxt dashboard consuming the FastAPI directly (no Nitro API).
- **Requirements:** `/Users/pk/Projects/ModelPrism/requirements/`
- **Dashboard app:** `/Users/pk/Projects/ModelPrism/frontend/`
- **Agent submodule:** `/Users/pk/Projects/ModelPrism/modelprism-agent/`
- **Planner prompt:** `/Users/pk/Projects/ModelPrism/ai-prompts/prompt-ai-milestones-tasks-planner.md`
- **Milestone M1 folder:** `/Users/pk/Projects/ModelPrism/ai-milestones-and-tasks/milestone-01-foundation/`
- **M1 tasks:** 9 tasks total, estimated ~3-4 weeks effort
- **Architecture decision:** Dashboard consumes FastAPI directly (`nitro: false` in Nuxt config)

### M1-T8 Sub-Tasks (Pending Improvements)

| ID | Title | Status | Priority | Dependencies |
|----|-------|--------|----------|--------------|
| M1-T8-P1 | UI/UX Polish (ui-ux-pro-max + frontend-design) | 🟢 Complete | Medium | M1-T8 |
| M1-T8-P2 | Light & Dark Mode Toggle | 🟢 Complete | Medium | M1-T8-P1 |
| M1-T8-P3/P4 | PrimeVue Icons Fix + Responsive Verification | 🟢 Complete | High | M1-T8 |

> **Note:** M1-T8-P3 and M1-T8-P4 were merged into a single combined task. See `milestone-01-foundation/task-M1-T8-P3-P4-primevue-icons-and-responsive.md`.
