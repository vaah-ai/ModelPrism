---
step: 1
title: Select Next Task
phase: Orientation
---

# Step 1: Select Next Task

Read `{{MILESTONES_DIR}}/project-dashboard.md`.

## 1. Identify Last Completed Task

From the dashboard's task table, find the last task with status `🟢 Complete`.
- Present its ID and title to the user.
- This confirms what was finished and establishes continuity.

## 2. Auto-Select the Next Task

**If `{{TASK_ID}}` is provided:** read that task file directly and use it.

**Else** auto-select the next task:
1. Check for an interrupted task (status `🔵 In Progress`) → resume it.
2. Find the active milestone (first `🔵 In Progress` or first `⚪ Not Started` with dependencies met).
3. Find the first `⚪ Not Started` task whose dependencies are all `🟢 Complete`.
   - If multiple tasks are unblocked, propose the one on the **critical path** (most downstream dependents) and note the alternative(s) for possible parallel execution.

## 3. Present & Confirm

Present to the user:
- **Last completed task**
- **Auto-selected next task** (with brief rationale)
- **Alternative available tasks** (for parallel execution if user prefers)

Wait for explicit user confirmation. The user can:
- **Confirm** the auto-selected task
- **Override** to a different task
- **Cancel** the session

## 4. Update Status

After confirmation, invoke `Edit` tool to update the task status to `🔵 In Progress` in both:
- The individual task file `{{MILESTONES_DIR}}/milestone-XX/task-{{TASK_ID}}-*.md`
- `{{MILESTONES_DIR}}/project-dashboard.md`
