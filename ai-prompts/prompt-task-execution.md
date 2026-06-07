---
description: Execute ModelPrism development tasks
version: 2.0
auto_execution_mode: 3
generated_by: streamlined-analysis
generated_at: 2026-06-07
---

# ModelPrism Task Execution Prompt (Streamlined)

## Purpose

Execute ModelPrism development tasks sequentially. Each step's file has the full instructions — load one at a time, follow it, return here for the next.

## Variables

- **`{{TASK_ID}}`** — Task ID from milestone tracker (e.g., M1-T1).
- **`{{FEATURE_BRANCH}}`** — Pattern: `feature/{{TASK_ID}}-short-description`.
- **`{{MILESTONES_DIR}}`** — `ai-milestones-and-tasks/`
- **`{{DOCS_DIR}}`** — `requirements/`
- **`{{REQUIREMENTS_DIR}}`** — `requirements/`
- **`{{STEPS_DIR}}`** — `ai-prompts/prompt-task-execution-steps/`

## Execution Rules

1. Read this file once at session start. Load step files one at a time — never multiple.
2. Complete each step before loading the next. Never skip.
3. Load `{{STEPS_DIR}}/reference-{topic}.md` when a step instructs you to.
4. Use **Read** for files, **Edit** for modifications, **Write** for new files. Bash only for actual shell commands.
5. Report failures honestly. Mark unverifiable items `manual-verified`. Never suppress test failures.

## Step 1 Behavior

Step 01 now follows an **auto-select with override** flow:
1. Read the milestone dashboard to identify the **last completed task** and present it.
2. Auto-select the next task: check for interruptions first, then find the first eligible `⚪ Not Started` task with all dependencies met. On the critical path, prefer the task with the most downstream dependents.
3. Present the selection to the user along with any **alternative unblocked tasks** (for possible parallel execution).
4. Wait for the user to **confirm, override, or cancel** before updating status and proceeding.

## Workflow (14 Steps)

| Phase | Step | File |
|-------|------|------|
| **Orientation** | 0–2 | `step-00` → `step-02` |
| **Planning** | 3–6 | `step-03` → `step-06` |
| **Execution** | 7–8 | `step-07` → `step-08` |
| **Completion** | 9–10 | `step-09` → `step-10` |

## Report Template

```
## Task Completion Report
- **Task:** {{TASK_ID}} — [title]
- **Branch:** {{FEATURE_BRANCH}}
- **Status:** 🟢 Complete
- **Changes:** [files created/modified]
- **Tests:** [pass/fail count + commands]
- **Verification:** [what was verified vs manual-verified]
- **Notes:** [decisions, skipped steps, follow-ups]
```

## Progress Tracker

At Step 0, invoke **TodoWrite** with this list. Keep exactly one `in_progress` at a time.

```json
[
  { "id": "step-00", "content": "Step 00: Load Session Context", "activeForm": "Loading session context", "status": "in_progress" },
  { "id": "step-01", "content": "Step 01: Select Next Task", "activeForm": "Selecting next task", "status": "pending" },
  { "id": "step-02", "content": "Step 02: Check Dependencies", "activeForm": "Checking dependencies", "status": "pending" },
  { "id": "step-03", "content": "Step 03: Create Feature Branch", "activeForm": "Creating feature branch", "status": "pending" },
  { "id": "step-04", "content": "Step 04: Understand Task Scope", "activeForm": "Understanding task scope", "status": "pending" },
  { "id": "step-05", "content": "Step 05: Research, Code Analysis & UI Plan", "activeForm": "Researching and planning", "status": "pending" },
  { "id": "step-06", "content": "Step 06: Create & Audit Implementation Plan", "activeForm": "Creating and auditing plan", "status": "pending" },
  { "id": "step-07", "content": "Step 07: Implement the Task", "activeForm": "Implementing the task", "status": "pending" },
  { "id": "step-08", "content": "Step 08: Test (UAT + E2E + Unit)", "activeForm": "Testing and fixing bugs", "status": "pending" },
  { "id": "step-09", "content": "Step 09: Code Quality & Documentation", "activeForm": "Running quality checks and writing docs", "status": "pending" },
  { "id": "step-10", "content": "Step 10: Finalize & Commit", "activeForm": "Finalizing and committing", "status": "pending" }
]
```
