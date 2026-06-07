---
step: 4
title: Understand Task Scope
phase: Planning
---

# Step 4: Understand Task Scope

Read in parallel:
- Task file at `{{MILESTONES_DIR}}/milestone-01-foundation/{{TASK_ID}}.md`
- Feature spec in `{{REQUIREMENTS_DIR}}/features/`
- Relevant ADRs in `{{DOCS_DIR}}/adr/`

Summarize: which files will be created, modified, or deleted.

If the task involves complex architecture or non-obvious integration, invoke `sequential-thinking` MCP to map the scope before proceeding.

After understanding the scope, perform a **pre-implementation gap analysis**:
- Compare the task's acceptance criteria against existing code/patterns
- Identify patterns already established in the codebase that should be followed
- Note any deviations from spec, directory structure, or architecture rules
- Flag missing dependencies or infrastructure requirements
- Document these pre-gaps so the implementation plan can address them

This pre-gap analysis feeds directly into Step 5 (research) and Step 6 (implementation plan) — ensuring the plan proactively closes gaps rather than needing post-implementation fixes.
