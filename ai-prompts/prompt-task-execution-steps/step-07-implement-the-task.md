---
step: 7
title: Implement the Task
phase: Execution
---

# Step 7: Implement the Task

Execute the implementation plan. Create sub-todo items (e.g., `step-07a`, `step-07b`) for granular tracking — one `in_progress` at a time.

**Follow the layer ordering from Step 6** to avoid dependency issues.

**For each area, invoke the relevant skill:**
- `nuxt` for Nuxt components/pages/composables
- `fastapi-development` for FastAPI route handlers / Pydantic schemas
- `pinia` for Pinia stores
- `primevue-components` for PrimeVue component props/events/slots
- `tailwind-css-patterns` for styling

**Load `reference-coding-principles.md`** and apply its rules.

**After each file edit**, immediately:
- Run typecheck: `npm run typecheck` (frontend) or `mypy` (backend/agent)
- Run adjacent tests: `npm run test -- --related <file>` or `pytest <test-file>`

**Invoke `brainstorming` skill** for any sub-step where the implementation approach is uncertain or involves a design decision not covered by existing code patterns.

**No TODO or placeholder comments.** Every implementation sub-task must produce real code.
