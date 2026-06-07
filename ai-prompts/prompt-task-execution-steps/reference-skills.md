---
title: Agent Skills Reference
purpose: Available skills, install commands, and when to invoke each
---

# Skills

Recommended agent skills from [skills.sh](https://skills.sh/). Install with `npx skills add <owner/repo>`.

| Skill | Install Command | When to Invoke |
| ----- | --------------- | -------------- |
| `nuxt` | `npx skills add nuxt/nuxt` | Step 7: Plan UI/UX. Step 11: Implement Nuxt components, pages, composables, stores, nuxt.config. Step 13: Write Playwright E2E tests for Nuxt pages. |
| `nuxt-content` | `npx skills add nuxt/nuxt-content` | If working with Nuxt Content v3 for documentation or CMS features. |
| `pinia` | `npx skills add vue/pinia` | Step 11: Define Pinia stores (`auth.ts`, `metrics.ts`, `agents.ts`, `models.ts`, `user.ts`). |
| `tailwind-css-patterns` | `npx skills add tailwind-labs/tailwind-css-patterns` | Step 7: Plan UI/UX. Step 11: Style components with utility-first Tailwind CSS. |
| `primevue` | `npx skills add primevue/primevue` | Step 7: Plan component usage. Step 11: Use PrimeVue 4 components (DataTable, Chart, Dialog, Stepper, etc.). |
| `primevue-components` | `npx skills add primevue/primevue-components` | Step 7: Review available PrimeVue components before UI planning. Step 11: Look up component API, props, slots before writing templates. |
| `fastapi-development` | `npx skills add fastapi/fastapi-development` | Step 11: Implement FastAPI route handlers, Pydantic schemas, dependency injection, WebSocket endpoints. |
| `agent-browser` | `npx skills add anthropic/agent-browser` | Step 12: Automated UAT — walk through acceptance criteria via browser automation (screenshots, click flows, form fills, console checks). |
| `playwright` | `npx skills add microsoft/playwright` | Step 13: Write deterministic Playwright E2E tests. |
| `brainstorming` | `npx skills add anthropic/brainstorming` | Step 8: Explore approaches for new features or non-obvious implementation patterns. Step 11: Complex sub-step decisions. |
| `diagram-creator` | `npx skills add mermaid/diagram-creator` | Step 14: Generate architecture diagrams for developer documentation. |
| `code-review` | `npx skills add anthropic/code-review` | Step 15: Run for correctness bugs and cleanup suggestions on the full diff. |
| `security-review` | `npx skills add anthropic/security-review` | Step 15: Security-specific review for auth endpoints, API key handling, Docker security, WebSocket auth. |
