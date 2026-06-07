# Task M1-T8 — Nuxt Dashboard Scaffold

> **Milestone:** M1 (Foundation)
> **Priority:** Critical
> **Status:** 🟢 Complete
> **Estimated Effort:** 2 days

## Description

Scaffold the Nuxt 4 dashboard application at `/Users/pk/Projects/ai-models-hosting/dashboard-gpu-server/`. Initialize Nuxt 4 with PrimeVue 4 and Tailwind CSS v4, create the dashboard layout, configure routing without auth, set up the Pinia store skeleton, and create the base composable for WebSocket metric consumption. No authentication — direct FastAPI consumption.

## Task Goals

- Initialize Nuxt 4 project in `dashboard-gpu-server/`
- Install and configure PrimeVue 4 with Tailwind CSS v4
- Create `dashboard.vue` layout with sidebar navigation and top bar
- Configure pages: `/dashboard` (server overview), `/dashboard/servers/[id]` (detail)
- Create Pinia stores: `agents.ts`, `metrics.ts`
- Create composable: `useWebSocketMetrics.ts` (connects to dashboard WS with 500ms batching)
- Create `nuxt.config.ts` with PrimeVue auto-import, Tailwind, CORS proxy for FastAPI
- Configure no auth mode (bypass all auth logic, direct API calls)

## Implementation Plan

> ⚠️ Plan documented 2026-06-07. SPA mode (ssr: false), no auth for MVP, consumes FastAPI directly.

### Architecture Decision
- **SPA Mode** (`ssr: false`) — client-side only rendering. No SSR complexity needed for dashboard.
- **No Nitro API routes** — no `server/api/` directory. Dashboard calls FastAPI directly.
- **No auth** for MVP — runtime config provides backend URL; no JWT headers.
- **PrimeVue `cssLayer: false`** — avoids CSS layer conflicts with Tailwind v4.

### Files to Create (17 files, 6 phases)

**Phase 1 — Project Configs**
1. `package.json` — Nuxt 4 + PrimeVue 4 + Tailwind v4 + Pinia + VueUse + uPlot + ECharts
2. `nuxt.config.ts` — ssr: false, PrimeVue (Aura), Pinia, Tailwind v4 CSS, runtime config
3. `tsconfig.json` — Nuxt 4 auto-generated, strict mode
4. `.env.example` — `NUXT_PUBLIC_BACKEND_URL=http://localhost:8000`
5. `app/app.config.ts` — App metadata (title, version)

**Phase 2 — CSS & App Shell**
6. `app/assets/css/main.css` — `@import "tailwindcss"`
7. `app/app.vue` — NuxtLayout + NuxtPage + PrimeVue Toast

**Phase 3 — Layouts**
8. `app/layouts/default.vue` — Minimal layout (used by index redirect)
9. `app/layouts/dashboard.vue` — Sidebar (PanelMenu) + top bar + content slot, responsive

**Phase 4 — Pages**
10. `app/error.vue` — Nuxt error page
11. `app/pages/index.vue` — Redirect to `/dashboard`
12. `app/pages/dashboard/index.vue` — Server overview placeholder
13. `app/pages/dashboard/servers/[id].vue` — Server detail placeholder

**Phase 5 — State (Pinia)**
14. `stores/agents.ts` — Agent list store with typed Agent interface, actions, metric delta merge
15. `stores/metrics.ts` — Metric buffer store, per-agent histogram, summary stats

**Phase 6 — Composables**
16. `composables/useApi.ts` — `$fetch` wrapper with baseURL to FastAPI
17. `composables/useWebSocketMetrics.ts` — WebSocket lifecycle: connect, 500ms batch, buffer, auto-reconnect

### Implementation Order
Phases are sequential: 1 → 2 → 3 → 4 → 5 → 6.
Within each phase, files can be created in any order.

1. Initialize Nuxt 4 project:
   ```bash
   cd /Users/pk/Projects/ai-models-hosting/dashboard-gpu-server
   npx nuxi@latest init . --force
   ```
   Or manually create the project structure with `package.json`, `nuxt.config.ts`, `tsconfig.json`
2. Install dependencies:
   - `primevue`, `@primevue/themes`, `@primevue/auto-import-resolver` (PrimeVue 4)
   - `tailwindcss`, `@tailwindcss/vite` (Tailwind CSS v4)
   - `pinia`, `@pinia/nuxt` (state management)
   - `@vueuse/core`, `@vueuse/nuxt` (VueUse composables)
   - `uPlot` (real-time charts — install dep, charts created in M1-T9)
   - `echarts` (comparison charts — install dep, used in future milestones)
3. Configure `nuxt.config.ts`:
   - PrimeVue 4: import resolver, theme (Aura), CSS layer
   - Tailwind CSS v4: `@import "tailwindcss"` in main CSS
   - Pinia: enable with `@pinia/nuxt`
   - `nitro: false` — no Nitro API (consuming FastAPI directly)
   - Runtime config: `public.backendUrl` pointing to FastAPI base URL
   - No auth module (MVP has no authentication)
4. Create `app/assets/css/main.css` with Tailwind v4 imports + PrimeVue theme CSS layer
5. Create `app/app.vue` — root component with NuxtLayout and NuxtPage
6. Create `app/layouts/dashboard.vue` — sidebar layout with:
   - PrimeVue PanelMenu or Menu component for navigation
   - App header bar with project name "ModelPrism"
   - RouterView content area
   - No user menu (no auth for MVP)
7. Create pages:
   - `app/pages/index.vue` — redirect to `/dashboard`
   - `app/pages/dashboard/index.vue` — GPU server overview (placeholder, M1-T9)
   - `app/pages/dashboard/servers/[id].vue` — single server detail (placeholder, M1-T9)
8. Create Pinia stores:
   - `stores/agents.ts` — `Agent` interface, state (agent list), actions (`fetchAgents()`, `fetchAgent(id)`)
   - `stores/metrics.ts` — `MetricSnapshot` interface, state (current metrics per agent, histogram buffer), actions
9. Create composable `composables/useWebSocketMetrics.ts`:
   - `useWebSocketMetrics(agentId?: string)` — connect to `/ws/dashboard/{agentId}` or `/ws/dashboard`
   - Accumulate incoming messages for 500ms, then batch-update the Pinia store
   - Auto-reconnect on disconnect (3s delay)
   - Clean up on component unmount
10. Set `package.json` scripts: `dev`, `build`, `preview`

### Skills & MCP Servers

| Resource              | Purpose                      | When to Invoke                   |
| --------------------- | ---------------------------- | -------------------------------- |
| `nuxt`                | Nuxt 4 setup, PrimeVue 4     | Steps 2-10                      |
| `filesystem` (MCP)    | File creation                | Creating Nuxt project files      |

## Acceptance Criteria

- [ ] `npm run dev` starts Nuxt 4 dev server
- [ ] Index page redirects to `/dashboard`
- [ ] `/dashboard` page loads with sidebar layout
- [ ] `/dashboard/servers/[id]` page is routable
- [ ] PrimeVue components auto-import and render
- [ ] Tailwind CSS v4 classes apply correctly
- [ ] Pinia stores are accessible in components
- [ ] `useWebSocketMetrics` composable can connect to the backend WebSocket
- [ ] `nitro: false` is configured — no Nitro API calls
- [ ] Backend URL is configurable via runtime config

## Completion Criteria

- [ ] All acceptance criteria above pass
- [ ] TypeScript compiles without errors
- [ ] `npm run dev` serves the app with HMR
- [ ] `npm run build` succeeds

## Testing Checklist

- [ ] Component test: dashboard layout renders
- [ ] Component test: sidebar navigation links work
- [ ] Unit test: Pinia store actions (mock HTTP client)
- [ ] Unit test: WebSocket composable connect/disconnect

## Dependencies

- **Requires:** None (scaffolding is independent of backend)
- **Blocks:** M1-T9 (Dashboard Pages)

## Documentation References

- `requirements/07-directory-structure.md` — frontend directory layout
- `requirements/05-tech-stack.md` — Nuxt 4, PrimeVue 4, Tailwind CSS v4
- `requirements/02-architecture-overview.md` — frontend → backend pattern

## Notes

- `nitro: false` is critical — we consume FastAPI directly, not through Nitro
- Use VueUse's `useWebSocket` for the WebSocket composable (battle-tested, handles reconnection)
- PrimeVue 4 uses import resolution (no need to manually import components)
- Tailwind CSS v4 uses `@import "tailwindcss"` not `@tailwind` directives
- For MVP's no-auth mode, the dashboard makes direct HTTP calls to FastAPI without JWT headers
- The existing `vllm-dashboard.html` can be kept as reference for chart layouts and metric displays
