---
step: 5
title: Research, Code Analysis & UI Plan
phase: Planning
---

# Step 5: Research, Code Analysis & UI Plan

## Technology Research

For technologies in this task you're not already familiar with:
- Use `context7` MCP for official docs at the version in use.
- Load `{{STEPS_DIR}}/reference-tech-stack.md` for version numbers.
- Invoke relevant skills: `nuxt`, `fastapi-development`, `primevue-components`, `tailwind-css-patterns`, `playwright`.

If the implementation approach is uncertain or involves a design decision, invoke `brainstorming` skill to explore at least 2 approaches.

## Code Analysis

Read existing code the task will touch. Note naming conventions, import patterns, error handling, and design patterns already in use.

For ModelPrism, watch for:
- JSON:API ResourceObject structure (`id, type, attributes, relationships`)
- Pydantic v2 patterns (`model_config`, `from_attributes`)
- Pinia store patterns (option vs setup, WebSocket subscriptions)
- FastAPI dependency injection patterns
- Agent WebSocket message type discrimination
- Agent connection/reconnection with exponential backoff

## UI Plan (skip if no UI component)

Invoke `ui-ux-pro-max` skill (or `brainstorming` if unavailable) to plan the UI approach before writing code.

Review PrimeVue 4 components that match the UI requirements. Consider layout, dark mode, and accessibility. Use `uPlot` for real-time metrics and `ECharts` for benchmark/billing analytics.

Plan: new page or modification? Which Pinia stores / WebSocket subscriptions / composables are needed?

(Optional) Use `agent-browser` skill to take a pre-change screenshot for reference before implementation.
