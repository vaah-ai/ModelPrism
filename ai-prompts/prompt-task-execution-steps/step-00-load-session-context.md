---
step: 0
title: Load Session Context
phase: Orientation
---

# Step 0: Load Session Context

Invoke `memory` MCP server. Search for `"ModelPrism"` entries. Load any cached findings.

Read in parallel:
- `{{MILESTONES_DIR}}/project-dashboard.md` — active milestones, priorities
- `{{DOCS_DIR}}/README.md` — developer orientation

If a `"ModelPrism — {{TASK_ID}} Implementation Plan"` entry exists, a task was interrupted — load it, read the TodoWrite list, and resume from the next `pending` step.

Initialize the TodoWrite list from the orchestrator file's Progress Tracker section. Mark Step 0 as `in_progress`.
