---
step: 1
title: Select Next Task
phase: Orientation
---

# Step 1: Select Next Task

Read `{{MILESTONES_DIR}}/project-dashboard.md`.

**If `{{TASK_ID}}` is provided:** read that task file directly and present it.

**Else** find the next task:
1. Check for an interrupted task (status `🔵 In Progress`) → resume it.
2. Find the active milestone (first `🔵 In Progress` or first `⚪ Not Started` with dependencies met).
3. Find the first `⚪ Not Started` task whose dependencies are all `🟢 Complete`.

**Present to user and wait for explicit confirmation.** After confirmation, invoke `Edit` tool to update the task status to `🔵 In Progress` in both the task file and `project-dashboard.md`.
