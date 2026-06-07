---
step: 8
title: Test (UAT + E2E + Unit)
phase: Execution
---

# Step 8: Test (UAT + E2E + Unit)

## Phase A — Acceptance Criteria Verification

Load acceptance criteria from the task's requirements file (already read in Step 4).

**If task has a user-testable UI:** Use `agent-browser` to verify each criterion:
- Open the dev server, snapshot pages, drive flows, capture screenshots.
- Check: page structure, interaction behaviour, console cleanliness, network errors, dark mode.
- Cover: happy path, edge cases, error states, auth-gated paths.

**Bug fix loop:** While any criterion fails or errors exist:
1. Document the bug (expected vs actual + evidence).
2. Diagnose root cause, apply minimal fix, run typecheck.
3. Regression-test the affected flow. If fix touched shared code, re-run all critical paths.
4. If 3 attempts fail to find root cause, escalate to user.

**Gate:** Do not proceed to Phase B until all criteria pass with zero console/network errors.

## Phase B — Write Tests

Invoke `playwright` skill before writing E2E tests.

**E2E tests (Playwright):** Codify the verified flows. Use `getByRole` / `getByTestId` selectors. Cover happy path + primary edge case + primary error path. Run twice — fix flakes, never skip/fixme.

**Critical unit tests only — for:**
- Pure business-logic functions with non-trivial branches
- Validators, parsers, transformers, calculators
- Composables/hooks with conditional reactive behaviour
- Pydantic schema validation, JSON:API serialization

**Not for:** trivial getters, presentational components (covered by E2E), framework wrappers.

**Run the full suite:**
```bash
npm run typecheck    # Frontend type check
ruff check .         # Python lint + format
mypy backend/        # Python type check
npm run test         # Frontend unit tests
pytest               # Backend unit tests
npx playwright test  # E2E tests
```

**Gate:** All tests pass. Playwright passes twice in a row. Zero typecheck/lint errors.
