---
step: 6
title: Create & Audit Implementation Plan
phase: Planning
---

# Step 6: Create & Audit Implementation Plan

## Create Plan

Invoke `brainstorming` skill if this task involves a new feature, new component, or non-obvious implementation pattern — explore at least 2 approaches and document rationale.

Invoke `sequential-thinking` MCP to decompose the task into ordered steps.

Decompose the task into ordered implementation steps:
- Specific files to create/modify (paths relative to project root)
- Functions/components/modules to implement
- Tests to write
- Docs to update

**Layer ordering:**
- **Backend:** models → schemas → services → API routes → WebSocket handlers
- **Frontend:** types → Pinia stores → composables → UI components → pages
- **Agent:** shared schemas → core modules → feature modules → wiring
- **Shared:** Implement in `common/modelprism_common/schemas/` first

Invoke `memory` MCP server. Save the plan as `"ModelPrism — {{TASK_ID}} Implementation Plan"`.

## Audit Plan

Check against these principles before presenting to the user:
- **DRY/KISS/YAGNI** — no duplication, no over-engineering, no scope creep
- **SOLID** — single responsibility, open/closed, composition > inheritance
- **TDD** — test expectations defined

**Load `{{STEPS_DIR}}/reference-coding-principles.md`** and run the full checklist.

**Present to user and wait for explicit confirmation.** Include: task summary, plan, principles audit result, files list, risks.
