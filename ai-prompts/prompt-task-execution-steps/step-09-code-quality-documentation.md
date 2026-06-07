---
step: 9
title: Code Quality & Documentation
phase: Completion
---

# Step 9: Code Quality & Documentation

## Quality Checks (run in order)

1. **Formatter:** `npx prettier --write frontend/` + `ruff format backend/`
2. **Linter:** `npm run lint` + `ruff check backend/` — zero warnings
3. **Type checker:** `npm run typecheck` + `mypy backend/` — zero errors
4. **Dead code:** Remove unused imports, variables, functions from changed files.
5. **Complexity:** Each function ≤ 30 lines, nesting ≤ 3 levels, single responsibility.
6. **Diff review:** Confirm only intended changes — no debug artifacts, no commented code.

**Invoke `code-review` skill** for a full correctness and cleanup review of the diff.
**Invoke `security-review` skill** if the task touched auth endpoints, API key handling, Docker config, or WebSocket security.

**Load `reference-coding-principles.md`** and run every check in the Principles Audit Checklist.

## Documentation

If the task introduced new components, API endpoints, data models, services, or patterns — create or update docs in `{{DOCS_DIR}}`. For each item: purpose, API/props/parameters, usage example, integration notes, gotchas.

If the task was a minor bug fix with no new patterns, skip documentation.
