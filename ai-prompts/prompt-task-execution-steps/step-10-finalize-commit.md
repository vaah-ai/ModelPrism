---
step: 10
title: Finalize & Commit
phase: Completion
---

# Step 10: Finalize & Commit

## Update Tracking

Mark the task `🟢 Complete` in its task file and update `project-dashboard.md`.

If all tasks in the milestone are complete, mark the milestone `🟢 Complete` too.

## Evaluate Impact on Upcoming Tasks

**Gate:** Only run this if you changed shared schemas, API endpoints, DB models, or public interfaces.

Read the staged diff to inventory changes. Read the milestone file for pending `⚪ Not Started` / `🟠 Deferred` tasks in the same milestone. For each affected task, prepend an impact context block in its task file:

```markdown
> **Impact from {{TASK_ID}}:** [what changed, where, why it matters, gotchas]
```

Invoke `memory` MCP server. Save summary as `"ModelPrism — {{TASK_ID}} Upcoming-Task Impact"`.

## Update AI Memory

Invoke `memory` MCP server. Save:
- `"ModelPrism — Patterns Established"` — new patterns/abstractions introduced
- `"ModelPrism — Decisions Made"` — rationale for key decisions
- `"ModelPrism — {{TASK_ID}} Complete"` — summary, files changed, test results

## Commit

Invoke `git` MCP server:
- Stage all changes.
- Write commit message:

```
[{{TASK_ID}}] Brief description

- Specific change 1
- Specific change 2

Refs: {{MILESTONES_DIR}}/{{TASK_ID}}-short-description.md
```

Use present tense, imperative mood. Do NOT push without user confirmation.

## Notify

Inform the user the task is complete on `{{FEATURE_BRANCH}}` and ready for merge. List any newly unblocked tasks if applicable.
