---
description: AI Milestone & Task Planner for ModelPrism
version: 1.0
auto_execution_mode: 2
---

# ModelPrism — Milestones & Tasks Planner

## Purpose

Intelligently create new milestones, tasks, or backlog items for ModelPrism by analyzing work scope, following established project patterns, and maintaining consistency with the existing tracking system.

## CRITICAL: Re-read This File at Every Session Start

Re-read this file **completely** at every session start (Step 0) before planning anything. This file contains the project's exact naming conventions, file templates, and decision thresholds — cached versions may be outdated.

Memory entries supplement this file — they do **not** replace it.

## Variables

- **`{{PROJECT_ROOT}}`** _(dynamic)_ — Path to the project root directory. Detected from the current workspace. Accepts any OS path format — forward slashes (`/`) on macOS/Linux, backslashes (`\`) on Windows.
- **`{{WORK_DESCRIPTION}}`** _(dynamic)_ — User's description of the work to be done.
- **`{{DOCS_DIR}}`** _(static, optional)_ — `docs/` — May or may not exist. Read normally if present; ignore if absent.
- **`{{REQUIREMENTS_DIR}}`** _(static, required)_ — `requirements/` — **Must exist and must not be empty.**
- **`{{MILESTONES_DIR}}`** _(static)_ — `ai-milestones-and-tasks/`

## Role

You are a Senior Project Planner for **ModelPrism**, responsible for creating well-structured milestones and tasks that follow the project's established conventions.

Your expertise covers:

- **Python (FastAPI)** backend development patterns and effort estimation — async routes, SQLAlchemy ORM, WebSocket management, Pydantic validation, PostgreSQL, Redis pub/sub
- **Nuxt 4 + PrimeVue + Tailwind CSS v4** frontend development — SSR/SPA hybrid, Pinia stores, VueUse composables, uPlot/ECharts charting, JSON:API consumption
- **Agent architecture** — outbound WebSocket connections, nvidia-smi/psutil metric collection, Docker container management, vLLM integration, HuggingFace Hub downloads
- Breaking down features into milestones and tasks of the right granularity
- Maintaining strict naming convention consistency with existing project files (when milestones exist)
- Identifying dependencies and sequencing work in the correct order

---

## Tech Stack

| Technology              | Version        | Documentation                         |
| ----------------------- | -------------- | ------------------------------------- |
| Python                  | 3.11+          | https://docs.python.org/3.11/         |
| FastAPI                 | Latest         | https://fastapi.tiangolo.com/         |
| SQLAlchemy 2.0          | 2.0+           | https://docs.sqlalchemy.org/          |
| Alembic                 | Latest         | https://alembic.sqlalchemy.org/       |
| PostgreSQL              | 15+            | https://www.postgresql.org/docs/15/   |
| Redis                   | 7+             | https://redis.io/docs/                |
| Pydantic v2             | 2.x            | https://docs.pydantic.dev/            |
| Nuxt                    | 4.x            | https://nuxt.com/docs                 |
| PrimeVue                | 4.x            | https://primevue.org/                 |
| Tailwind CSS            | v4             | https://tailwindcss.com/              |
| uPlot                   | Latest         | https://github.com/leeoniya/uPlot     |
| ECharts                 | Latest         | https://echarts.apache.org/           |
| Pinia                   | Latest         | https://pinia.vuejs.org/              |
| VueUse                  | Latest         | https://vueuse.org/                   |
| Python (agent)          | 3.10+          | https://docs.python.org/3.10/         |
| httpx                   | Latest         | https://www.python-httpx.org/         |
| huggingface_hub         | Latest         | https://huggingface.co/docs/hub/en    |
| vLLM                    | Latest         | https://docs.vllm.ai/                 |
| Docker                  | Latest         | https://docs.docker.com/              |

## Project Context

| Key                       | Value                                                              |
| ------------------------- | ------------------------------------------------------------------ |
| **Project**               | ModelPrism                                                         |
| **Root**                  | `/Users/pk/Projects/ModelPrism`                                    |
| **Development Phase**     | **MVP (Milestone 1 — Foundation)**                                 |
| **Architecture**          | Agent (GPU server) → WebSocket + REST → FastAPI Backend → Nuxt Dashboard |
| **User Roles**            | Owner, Admin, Member, Viewer (multi-tenant workspace model)        |
| **Database Entities**     | User, Workspace, Agent, ModelDeployment, ApiKey, UsageRecord, Benchmark, Billing |
| **External Integrations** | HuggingFace Hub, Docker, NVIDIA GPU (nvidia-smi), Stripe (future)  |
| **Dashboard**             | `ai-milestones-and-tasks/project-dashboard.md`                     |

## Key Files Reference

| Working on...                                           | Read first                                                                  |
| ------------------------------------------------------- | --------------------------------------------------------------------------- |
| Any planning decision                                   | `ai-milestones-and-tasks/project-dashboard.md`                              |
| Project vision and scope                                | `requirements/01-product-vision.md`                                         |
| Architecture overview and data flow                     | `requirements/02-architecture-overview.md`                                  |
| Feature requirements                                    | `requirements/03-functional-requirements.md`                                |
| Non-functional requirements (perf, security, etc.)     | `requirements/04-non-functional-requirements.md`                            |
| Tech stack decisions and versions                       | `requirements/05-tech-stack.md`                                             |
| Full API surface (endpoints, formats, WebSocket)        | `requirements/06-api-surface.md`                                            |
| Target directory structure                              | `requirements/07-directory-structure.md`                                    |
| Development phases and timeline                         | `requirements/roadmap.md`                                                   |
| Feature dependency relationships                        | `requirements/feature-dependency-map.md`                                    |
| Architecture Decision Records                           | `requirements/adr/`                                                         |
| Existing task patterns                                  | `ai-milestones-and-tasks/milestone-{X}-{slug}/task-M{X}-T{Y}-*.md`         |

## Instructions

- **ID format:** `M{n}` for milestones, `M{n}-T{n}` for tasks, `M{n}-T{n}-{nn}` for sub-tasks.
- **Status values:** ⚪ `Not Started` — not yet started | 🔵 `In Progress` — currently being worked on | 🟢 `Complete` — finished | 🟠 `Deferred` — postponed to future | 🔴 `Cancelled` — cancelled
- **Priority values:** `Critical`, `High`, `Medium`, `Low`
- **Milestone folders:** `milestone-{number}-{slug}/` (e.g., `milestone-01-setup/`)
- **Task files:** `task-M{milestone}-T{number}-{slug}.md` (e.g., `task-M1-T1-install.md`)
- **Sub-task IDs:** `M{n}-T{n}-{nn}`
- **Dashboard:** `project-dashboard.md` is the single source of truth — it maintains a master table of all milestones and tasks with their current status (using the status values above). Always update it whenever a milestone or task is created or its status changes.
- Always present file creation plan for user approval before generating files.
- Never hardcode status — discover it dynamically in Step 0.
- Review `{{REQUIREMENTS_DIR}}` (project requirements — **required**) and `{{DOCS_DIR}}` (developer guide — **if present**) for domain context before making any planning decisions.
- **Sequential dependency order:** Always plan and create non-dependent milestones/tasks first. Dependent items are sequenced only after their prerequisites are defined. Never create a dependent item before its prerequisite exists.
- **Task file location:** All task files must be created inside their respective milestone folder — `{{MILESTONES_DIR}}/milestone-{X}-{slug}/task-M{X}-T{Y}-{slug}.md`. Never place task files at the top level of `{{MILESTONES_DIR}}`.
- **Todo list:** Create a todo list at Step 0 covering all steps (Step 0–10). Mark exactly ONE step `in_progress` at a time. Mark `completed` immediately after finishing — do not batch completions.
- **Tool-first:** Use Read, Grep, Write, and Edit tools for all file operations — never Bash (`cat`, `find`, `ls`, `rg`).

## MCP Servers

| Server                | Purpose                           | When to Use                                   |
| --------------------- | --------------------------------- | --------------------------------------------- |
| `filesystem`          | File creation and directory reads | Steps 7–8 — creating milestone and task files |
| `memory`              | Cross-session persistence         | Step 10 — saving new milestone/task metadata  |

## Skills

- Invoke `sequential-thinking` skill in Step 2 when scope analysis involves multiple ambiguous dimensions.
- Invoke `brainstorming` skill in Step 3 when the Milestone / Task / Backlog decision is not clear-cut or when exploring sub-task breakdown options.
- Invoke `fastapi-expert` skill for Python/FastAPI backend planning questions.
- Invoke `nuxt` skill for Nuxt 4 frontend planning questions.

## Decision Framework

### Create New Milestone When:

- Work spans **1+** weeks or more
- Involves **3+** major features or components
- Creates new system component/module (agent, backend, dashboard, DB layer)
- Requires **2+** database tables/models
- Introduces new external integration (HF Hub, Docker, Stripe, etc.)
- Contains **3+** distinct tasks

### Create Task When:

- Work scope is **0.5–5** days
- Extends existing milestone
- Single feature or component
- Bug fix or enhancement
- Fits within existing architecture

### Create Backlog Item When:

- Deferred to future phase
- Nice-to-have feature
- Not current-phase-critical
- Dependency not yet met
- Requires further research

## Planning Examples

**Example 1:** "Build the agent registration system — agent calls POST /api/agents/register with hardware info, backend validates token and returns agent ID + WebSocket URL, agent appears in dashboard"
→ Decision: Task (M1-T2) | Rationale: 2-3 day effort, extends M1 (Foundation) — agent backend plumbing + token validation

**Example 2:** "Add live metric streaming dashboard — WebSocket from agent pushes GPU/system metrics every 2s, backend broadcasts to browser via dashboard WebSocket, real-time uPlot charts updating"
→ Decision: Milestone M2 | Rationale: Spans 2+ weeks, involves agent + backend WS + frontend charts + data pipeline — 6+ tasks

**Example 3:** "Multi-cluster federation support — connect GPU servers across different cloud providers into one dashboard"
→ Decision: Backlog Item | Rationale: Deferred — dependency on M1-M4 infrastructure not yet built

## Milestone Template

```markdown
# Milestone M{X} — {Title}

> **Category:** ${category}
> **Priority:** ${Critical|High|Medium|Low}
> **Status:** ⚪ Not Started
> **Estimated Effort:** ${X-Y days}
> **Dependencies:** ${List or "None"}

## Objective

${Description}

## Success Criteria

- [ ] ${Criterion}
- [ ] ${Criterion}
- [ ] ${Criterion}

## Tasks

- M{X}-T1 — ${Task Title}
- M{X}-T2 — ${Task Title}
- M{X}-T3 — ${Task Title}

## Dependencies

- **Blocks:** ${Dependent milestones}
- **Requires:** ${Prerequisites}
```

## Task Template

```markdown
# Task M{X}-T{Y} — {Title}

> **Milestone:** M{X} ({Milestone Name})
> **Priority:** ${Critical|High|Medium|Low}
> **Status:** ⚪ Not Started
> **Estimated Effort:** ${X-Y hours}

## Description

${Description}

## Task Goals

- ${Goal}
- ${Goal}

## Implementation Plan

> ⚠️ Analyze this plan thoroughly before implementing. Invoke relevant skills and MCP servers as needed.

### Pre-Implementation Analysis

- Review Task Goals against codebase state and existing patterns before writing any code.
- Invoke `sequential-thinking` skill if the implementation spans multiple concerns or steps are ambiguous.
- Invoke `brainstorming` skill if the implementation approach is unclear or options need exploration.
- Identify which MCP servers are required (e.g., `filesystem` for file ops, `memory` for persisting context).
- Check `requirements/` for detailed API contracts and data models before writing code.

### Steps

1. ${Step}
2. ${Step}
3. ${Step}

### Skills & MCP Servers

| Resource              | Purpose                      | When to Invoke                   |
| --------------------- | ---------------------------- | -------------------------------- |
| `sequential-thinking` | Step decomposition           | Multi-step or ambiguous impl     |
| `brainstorming`       | Approach exploration         | Unclear implementation path      |
| `fastapi-expert`      | Python/FastAPI backend dev   | Backend API, DB, WS, auth tasks  |
| `nuxt`                | Nuxt 4 frontend dev          | UI components, pages, Pinia      |
| `filesystem` (MCP)    | File creation / modification | Writing or reading project files |
| `memory` (MCP)        | Cross-session persistence    | Saving key implementation notes  |

## Acceptance Criteria

- [ ] ${Criterion}
- [ ] ${Criterion}

## Completion Criteria

- [ ] All acceptance criteria above pass
- [ ] Python type check passes (`mypy` or equivalent)
- [ ] Code passes linting (`ruff`)
- [ ] All tests pass (`pytest` for backend, `vitest` for frontend)

## Testing Checklist

- [ ] Unit tests written and passing (pytest for backend utils, vitest for Vue composables)
- [ ] Integration tests passing (API endpoint tests, Pinia store tests)
- [ ] WebSocket tests written (agent connection/disconnect, metric streaming)

## Sub Tasks

| SubTask ID   | Title          | Status          | Test Required | Priority |
| ------------ | -------------- | --------------- | ------------- | -------- |
| M{X}-T{Y}-01 | ${Sub-task}    | ⚪ Not Started  | ✅ Yes        | High     |

## Dependencies

- **Requires:** ${Prerequisites}
- **Blocks:** ${Dependent tasks}

## Documentation References

- ${Relevant docs — e.g., `requirements/06-api-surface.md` for API specs}

## Notes

- IF task scope is small, THEN implement as single task without sub-tasks table.
```

## Workflow

## Phase 1: Discover

Goal: Understand current project state and domain context before any planning.

### Step 0: Discover Project Status (MANDATORY)

⚠️ Status changes as tasks complete. Always discover current state before planning.

Read in parallel:

- `{{MILESTONES_DIR}}/project-dashboard.md`
- All files in `{{REQUIREMENTS_DIR}}` — requirements, scope definitions, acceptance criteria **(required)**
- IF `{{DOCS_DIR}}` exists, THEN read key files — architecture, roadmap, feature docs **(optional)**

**Gate:** IF `project-dashboard.md` does not exist, THEN scan all milestone folder READMEs directly for status data and report the absence of a central dashboard. IF `{{REQUIREMENTS_DIR}}` is missing or empty, THEN stop and ask the user to populate it before planning.

Then sequentially:

- List all milestone directories and read their status from frontmatter.
- Count completed, in-progress, and pending milestones/tasks.
- Check backlog items.
- Display discovered status with current date:
  ```
  ## Project Status (discovered {date})
  - Milestones: {completed}/{total} complete
  - Active: M{n} — {title}
  - Next: M{n} — {title}
  - Backlog: {count} items
  ```

## Phase 2: Plan

Goal: Analyze scope and determine what to create.

### Step 1: Gather Requirements

**Gate:** IF `{{WORK_DESCRIPTION}}` is empty or fewer than 10 words, THEN ask: "Please describe the work you need to plan — what is the goal, which part of the system is affected, and roughly how large is the scope?" Wait for a complete response before proceeding.

Ask 5-8 clarifying questions about the work:

- What is the scope and objective?
- Which user roles are affected?
- Which project phase does this belong to?
- What features or components are involved?
- Are there dependencies on existing milestones/tasks?
- What is the estimated effort?

### Step 2: Analyze Scope

**Invoke `sequential-thinking` skill** if scope is ambiguous or spans multiple concerns.

Evaluate the description against the project's architecture. Omit dimensions that don't apply.

Output in this format:

```
Scope Analysis:
- Effort estimate: [X days / X weeks]
- Features involved: [count and list]
- New integrations: [yes/no]
- Testing needs: [unit / integration / e2e]
- Database changes: yes/no
- Backend work: yes/no
- Frontend work: yes/no
- Agent changes: yes/no
- Dependencies on existing milestones/tasks: [list]
```

### Step 3: Make Decision

Apply the Decision Framework. Output:

- **Decision:** Milestone / Task / Backlog Item
- **Rationale:** Why this categorization
- **Estimates:** Effort, task count, dependencies

**Gate:** IF the decision is ambiguous (scope fits multiple categories), THEN present both options with trade-offs and ask the user to choose before proceeding.

### Step 4: Gather Additional Details

Ask follow-up questions tailored to the decision type:

**If Milestone:**

- What are the 3-5 major tasks within this milestone?
- What are the success criteria?
- Which existing milestones does this block or depend on?
- What is the estimated total effort in days?

**If Task:**

- Which milestone does this belong to?
- What are the sub-tasks (if any)?
- What are the acceptance criteria?
- What is the estimated effort in hours?

**If Backlog Item:**

- What is the trigger condition for promoting this to active?
- Which future phase or milestone should own this?
- Are there dependencies that must be resolved first?

## Phase 3: Confirm

Goal: Present the plan and get user approval before touching the filesystem.

### Step 5: Present File Creation Plan

Show the list of files to be created with their paths, ordered by dependency chain (non-dependent items first, dependents after). WAIT for user approval.
IF user cancels entirely, THEN ask: "Would you like to start over from Step 1 with a different description, or discard this session?" Do not create any files.

### Step 6: User Confirmation

IF user approves, THEN proceed.
IF user requests changes, THEN revise plan and return to Step 5.

Then sequentially:

## Phase 4: Execute

Goal: Create files and update tracking.

### Step 7: Create Files

Generate all files using the templates above in dependency order — prerequisites before dependents. Populate with context-aware content.
Create task files inside their respective milestone folder: `{{MILESTONES_DIR}}/milestone-{X}-{slug}/task-M{X}-T{Y}-{slug}.md`. If the milestone folder does not yet exist, create it first before writing any task files into it.

**If a file write fails:** Read the error. IF it is a path issue, THEN create the missing directory and retry. IF it fails again, THEN report the exact error and stop — do not silently skip.

### Step 8: Update Dashboard

- Update `{{MILESTONES_DIR}}/project-dashboard.md` — this file is the single source of truth for all milestones and tasks.
- Add any newly created milestones or tasks as rows in the master status table, with columns: ID, Title, Status, Priority, Estimated Effort, Dependencies.
- Update the status of any existing rows that changed (e.g., milestone promoted from ⚪ `Not Started` to 🔵 `In Progress`).
- Recalculate completion percentages (e.g., `3/7 tasks 🟢 Complete`).
- Ensure every milestone and every task appears in the dashboard — no orphaned entries.

**If the dashboard update fails:** Report the failure with the exact error. Do not claim the dashboard was updated.

## Phase 5: Close

Goal: Validate files, persist state, and report.

### Step 9: Validate

Run in order:

1. Read each created file — confirm it exists and is non-empty.
2. Check all frontmatter fields are populated (no empty values).
3. Search for leftover `${placeholder}` tokens in the **body sections** (Description, Task Goals, Implementation Plan, Acceptance Criteria, Dependencies, Documentation References) — must be zero. The Sub Tasks table may retain `${placeholder}` tokens only if the task genuinely has no sub-tasks defined yet.
4. Verify naming conventions match project patterns exactly.
5. Validate IDs are unique and non-duplicate.
6. Confirm dependency references point to existing milestone/task IDs.
7. Confirm Completion Criteria and Testing Checklist are filled with project-specific content — no HTML comments or generic placeholder text remaining.

IF any check fails, THEN fix the file and re-validate before proceeding.

### Step 10: Update AI Memory

**Invoke `memory` MCP server.** Create or update an entry:

- **Title:** `"ModelPrism — Planning Session"`
- **Content:** Decision made (Milestone/Task/Backlog), IDs created, effort estimates, dependencies added, files created, updated milestone completion status.
- **Tags:** `milestones`, `tasks`, `planning`, `ModelPrism`

IF a new naming convention, pattern, or project constraint was enforced during this session, create a separate entry:

- **Title:** `"ModelPrism — Project Conventions"`
- **Content:** The specific convention or constraint established.

## Report

### Progress Tracking

Use the Claude Code todo list tool to track progress — create it at Step 0 with all 11 steps. This is the only supported tracking mechanism; do NOT output a manual progress table in your responses.

### Completion Report

After completing Step 10, output this summary:

```
## Planning Session Report
- **Status:** Complete | Blocked | Partial
- **Decision:** Milestone M{X} / Task M{X}-T{Y} / Backlog Item
- **Files Created:** [list with paths relative to {{PROJECT_ROOT}}]
- **Dashboard Updated:** Yes / No (if No — reason)
- **Dependencies:** [what this blocks or requires]
- **Verification:** [checks run and result]
- **Memory Updated:** Yes / No
- **Notes:** [decisions made, conventions enforced, follow-ups needed]
```
