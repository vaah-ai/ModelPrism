# Task M1-T9 — Dashboard Pages

> **Milestone:** M1 (Foundation)
> **Priority:** High
> **Status:** ⚪ Not Started
>
> **Impact from M1-T8:** Nuxt Dashboard Scaffold completed.
> - Dashboard layout at `app/layouts/dashboard.vue` with sidebar PanelMenu navigation and responsive overlay
> - Pages scaffolded: `dashboard/index.vue` (overview) and `dashboard/servers/[id].vue` (detail) with placeholder panels
> - Pinia stores: `stores/agents.ts` (agent list with fetchAgents, applyMetricDelta, updateAgentStatus) and `stores/metrics.ts` (per-agent metric buffer with pushMetric, getBuffer)
> - Composables: `useWebSocketMetrics.ts` (WebSocket lifecycle with 500ms batch, auto-reconnect, message dispatch to stores)
> - Backend URL configurable via `NUXT_PUBLIC_BACKEND_URL` env var (defaults to `http://localhost:8000`)
> - WebSocket composable connects to `ws://<backendUrl>/ws/dashboard` expecting `metrics`, `agent_status`, `agent_update`, `replay_batch` message types
> - No auth middleware — direct HTTP/WS calls to FastAPI without JWT headers for MVP
> - Old `vllm-dashboard.html` preserved for chart layout reference
>
> **Impact from M1-T7:** Dashboard WebSocket Broadcast completed.
> - Backend provides `/ws/dashboard` (all agents) and `/ws/dashboard/{agent_id}` (per-agent) endpoints
> - Endpoints subscribe to Redis `metrics:{id}` channel and forward transformed flat metrics
> - Transformed format: `gpu_util_avg_pct`, `gpu_memory_used_mb`, `ram_used_gb`, `cpu_pct`, etc.
> - Raw GPU arrays from agents are averaged before forwarding
>
> **Estimated Effort:** 6 days (across 6 sub-tasks)

## Description

Implement the two core dashboard pages: the GPU server overview page (list all registered servers with aggregate metrics) and the single-server detail page (real-time charts, system resources, diagnostic cards, and live log viewer). Build components with reusability as the primary design goal — all dashboard components should be usable by future milestone pages (model management, benchmarks, admin panels) without modification.

Consume the FastAPI backend directly via REST for initial data load and WebSocket for real-time updates. Use uPlot for real-time GPU charts and PrimeVue components for the UI.

## Reusability Design Principles

All components in this task must follow these principles:

1. **Single Responsibility** — Each component does one thing and does it well. `MetricCard` displays a single metric; it does not fetch data. `SystemResources` composes multiple `ProgressBar` instances; it does not contain WebSocket logic.

2. **Props-Only Data Flow** — Components receive data via props. No component directly imports Pinia stores or WebSocket composables. Data fetching and store management live exclusively in page-level components.

3. **Type-Driven Interfaces** — Every component defines its props using TypeScript interfaces extracted to a shared types file (`~/types/dashboard.ts`). These types are the contract between pages and components.

4. **Framework-Agnostic Utility Functions** — Formatting, color calculation, and time-ago functions are pure functions in `~/utils/dashboard.ts` — not methods on components. Any page or component can import and reuse them.

5. **Composable Slot Design** — Components like `LiveLog` accept configuration via props (log levels, filters) rather than hardcoding behavior, making them reusable across deployment logs, agent logs, and benchmark logs.

## Task Goals

- Implement reusable common components: `MetricCard`, `StatusBadge`, `GpuBar`
- Implement dashboard-specific components: `SystemResources`, `QueueDiagnostics`, `GpuMetricsChart`, `ModelList`, `LiveLog`
- Implement server overview page with agent list, real-time status indicators, aggregate GPU utilization and VRAM usage
- Implement single server detail page with real-time uPlot charts, system resource bars, queue diagnostics, model list, and live log viewer
- Wire up WebSocket composable and Pinia stores for real-time metric updates on both pages
- Define shared TypeScript types in a central `~/types/dashboard.ts` for cross-component reuse
- Extract utility functions to `~/utils/dashboard.ts` (formatting, color mapping, time calculations)

## Implementation Plan

> ⚠️ Analyze this plan thoroughly before implementing. Invoke relevant skills and MCP servers as needed.

### Pre-Implementation Analysis

- Review the existing `vllm-dashboard.html` for proven chart layouts and metric display patterns
- Review `requirements/03-functional-requirements.md` F2.1 (Server Overview) and F2.2 (Single Server Dashboard)
- Review `requirements/06-api-surface.md` for metrics API format
- Review `requirements/05-tech-stack.md` for uPlot charting with 2s update intervals
- Invoke `nuxt` skill for Nuxt page patterns, PrimeVue component usage, and uPlot integration
- Review existing `stores/agents.ts` and `stores/metrics.ts` for store interface compatibility
- Review `composables/useWebSocketMetrics.ts` for WebSocket message format and store dispatch patterns

### Sub-Task Dependency Graph

```
M1-T9-01 (Types + Utils + Common) ──┬──→ M1-T9-02 (Dashboard Components)
                                      ├──→ M1-T9-05 (Overview Page)
                                      └──→ M1-T9-06 (Detail Page)
M1-T9-03 (uPlot Charts) ──────────────┼──→ M1-T9-06
M1-T9-04 (Live Log) ──────────────────┼──→ M1-T9-06
                                      └──→ M1-T9-06
```

**Parallel work:** M1-T9-03, M1-T9-04, and M1-T9-05 can start alongside M1-T9-02 (all need M1-T9-01 first).

### Steps

1. **Create shared foundation** (`M1-T9-01`):
   - Define types in `~/types/dashboard.ts` — `MetricSnapshot`, `MetricTimeSeries`, `LogEntry`, `AgentStatus`
   - Extract utilities to `~/utils/dashboard.ts` — `formatGb`, `formatMs`, `timeAgo`, `getSeverityColor`, `getVramColor`, `getGpuUtilSeverity`
   - Create common components: `MetricCard.vue`, `StatusBadge.vue`, `GpuBar.vue`

2. **Create dashboard components** (`M1-T9-02`):
   - `SystemResources.vue` — GPU/VRAM/RAM/CPU/Disk bars using `GpuBar` and `ProgressBar`
   - `QueueDiagnostics.vue` — running/waiting, KV cache, TTFT, error/truncation rates
   - `ModelList.vue` — running model names and basic stats

3. **Create uPlot chart component** (`M1-T9-03`):
   - `GpuMetricsChart.vue` — configurable chart type, metric key, color
   - Four chart configurations: GPU Utilization %, VRAM Used GB, Throughput tok/s, Requests (running/waiting)
   - 150-point window, responsive container, setData() updates

4. **Create log viewer component** (`M1-T9-04`):
   - `LiveLog.vue` — subscribes to logs channel, level filtering, search, auto-scroll
   - Accepts `logSource` prop for reuse across agent logs, deployment logs, benchmark logs

5. **Wire overview page** (`M1-T9-05`):
   - `dashboard/index.vue` — fetchAgents on mount, connect `/ws/dashboard`, bind DataTable to real store data
   - Summary stats cards, empty state, row click navigation, add-server dialog wired

6. **Wire detail page** (`M1-T9-06`):
   - `dashboard/servers/[id].vue` — connect `/ws/dashboard/{agentId}`, assemble all components
   - Header with agent info + StatusBadge, 2×2 chart grid, SystemResources, QueueDiagnostics, ModelList, LiveLog
   - Loading skeleton, error state, WebSocket reconnection indication

### Skills & MCP Servers

| Resource              | Purpose                      | When to Invoke                   |
| --------------------- | ---------------------------- | -------------------------------- |
| `nuxt`                | Nuxt pages, PrimeVue, uPlot  | Steps 1-6 — component creation   |
| `filesystem` (MCP)    | File creation                | Creating component files         |
| `sequential-thinking` | Complex component breakdown  | Sub-task dependency resolution   |
| `primevue`            | PrimeVue component API       | ProgressBar, Tag, Card styling   |

## Sub Tasks

| ID | Title | Effort | Depends On | Priority |
|----|-------|--------|------------|----------|
| M1-T9-01 | Shared Types, Utilities & Common Components | 0.5d | None | Critical |
| M1-T9-02 | Dashboard Components (SystemResources, QueueDiagnostics, ModelList) | 1d | M1-T9-01 | High |
| M1-T9-03 | uPlot Real-Time Charts (GpuMetricsChart) | 1.5d | M1-T9-01 | High |
| M1-T9-04 | Live Log Viewer (LiveLog) | 1d | M1-T9-01 | Medium |
| M1-T9-05 | Store Wiring + Overview Page | 1d | M1-T9-01, M1-T9-02 | High |
| M1-T9-06 | Detail Page Assembly | 1d | M1-T9-01 through M1-T9-05 | High |

### M1-T9-01 — Shared Types, Utilities & Common Components

**Goal:** Create the foundation that every other sub-task depends on — reusable types, pure utility functions, and the building-block UI components.

**Files to create:**
- `app/types/dashboard.ts` — All shared TypeScript interfaces and type aliases
- `app/utils/dashboard.ts` — Pure utility functions (formatting, colors, time)
- `app/components/common/MetricCard.vue` — Reusable metric display card
- `app/components/common/StatusBadge.vue` — Color-coded online/offline/connecting badge
- `app/components/common/GpuBar.vue` — Reusable GPU utilization bar with color thresholds

**Types to define (`dashboard.ts`):**
```typescript
export interface MetricSnapshot {
  ts: string
  gpuUtilAvgPct: number
  gpuMemoryUsedMb: number
  gpuMemoryTotalMb: number
  gpuTempC: number
  gpuPowerW: number
  ramUsedGb: number
  ramTotalGb: number
  cpuPct: number
  load1: number
  load5: number
  load15: number
  diskUsedGb: number
  diskTotalGb: number
  gpuCachePct: number
}

export interface VllmMetrics {
  running: number
  waiting: number
  totalRequests: number
  promptTokensTotal: number
  genTokensTotal: number
  ttftP50Ms: number
  ttftP99Ms: number
  gpuCachePct: number
  tps: number
  prefixCacheHitPct: number
  errorPct: number
  truncPct: number
}

export interface LogEntry {
  ts: string
  level: 'debug' | 'info' | 'warning' | 'error'
  module: string
  message: string
  stackTrace?: string
}

export type SeverityLevel = 'info' | 'success' | 'warn' | 'danger' | 'secondary'
export type TrendDirection = 'up' | 'down' | 'stable'
export type ConnectionStatus = 'online' | 'offline' | 'connecting' | 'degraded'
```

**Utilities (`dashboard.ts`):**
- `formatGb(mb: number): string` — Convert MB to GB with 1 decimal
- `formatBytes(bytes: number): string` — Auto-scale byte formatting
- `formatMs(ms: number): string` — Millisecond formatting
- `timeAgo(isoString: string): string` — Human-readable relative time
- `getSeverityColor(level: string): string` — Log level to CSS color mapping
- `getVramColor(pct: number): string` — Green/amber/red based on utilization
- `getGpuUtilSeverity(pct: number): SeverityLevel` — Severity for GPU thresholds

**MetricCard props:**
- `label: string` — Metric name
- `value: string | number` — Current value
- `unit?: string` — Optional unit suffix
- `trend?: TrendDirection` — Direction indicator arrow
- `severity?: SeverityLevel` — Color coding (default: info)

**StatusBadge props:**
- `status: ConnectionStatus` — online/offline/connecting/degraded
- Color-coded: green pulse for online, gray for offline, yellow for connecting, orange for degraded

**GpuBar props:**
- `value: number` — Utilization percentage (0-100)
- `label?: string` — Optional label prefix
- `showValue?: boolean` — Show percentage text (default: true)
- Compact reusable bar component with color thresholds (<70% green, 70-95% amber, >95% red)

**Acceptance Criteria (M1-T9-01):**
- [ ] All types defined with proper TypeScript interfaces and exported
- [ ] Utility functions are pure — no component or store dependencies
- [ ] MetricCard renders label, value, unit, trend arrow, and severity color
- [ ] StatusBadge shows correct color per status (green=online, gray=offline, yellow=connecting, orange=degraded)
- [ ] GpuBar renders with correct width percentage and color threshold
- [ ] All components accept `class` prop via `attrs` for external styling

### M1-T9-02 — Dashboard Components (SystemResources, QueueDiagnostics, ModelList)

**Goal:** Build the presentation components for the detail page's system resource panel, queue diagnostics panel, and model list. All components receive data via props only — no store or WebSocket coupling.

**Files to create:**
- `app/components/dashboard/SystemResources.vue`
- `app/components/dashboard/QueueDiagnostics.vue`
- `app/components/dashboard/ModelList.vue`

**SystemResources props:**
- `metrics: MetricSnapshot` — Full system metric snapshot
- Uses `GpuBar` and PrimeVue `ProgressBar` for each resource
- GPU: utilization bar + temperature + power draw
- VRAM: used/total bar with color threshold
- RAM: used/total bar
- CPU: utilization with load averages (1/5/15 min)
- Disk: used/total bar
- Layout: 2×3 grid on desktop, stacked on mobile

**QueueDiagnostics props:**
- `vllmMetrics: VllmMetrics` — vLLM-specific metrics
- Running / waiting request counts as MetricCard values
- KV cache utilization bar
- TTFT p50 and p99 display
- Error rate and truncation rate
- Bottleneck indicator (computed from metrics)

**ModelList props:**
- `models: Array<{ name: string; status: string; tps?: number; uptime?: string }>`
- Simple card listing running models with status tags
- Empty state when no models running
- Designed to be reusable by future `/dashboard/models/[id].vue` pages

**Acceptance Criteria (M1-T9-02):**
- [ ] SystemResources renders all resource bars correctly with color thresholds
- [ ] SystemResources shows GPU temperature and power draw when available
- [ ] QueueDiagnostics shows running/waiting requests, KV cache, TTFT p50/p99
- [ ] QueueDiagnostics computes and displays bottleneck indicator
- [ ] ModelList shows each model name with status tag
- [ ] ModelList shows empty state when models array is empty
- [ ] All components accept `class` prop for external styling override

### M1-T9-03 — uPlot Real-Time Charts (GpuMetricsChart)

**Goal:** Build the real-time chart component using uPlot. This is the most technically demanding sub-task — uPlot must be initialized once on mount and updated via `setData()` (never re-mounted).

**Files to create:**
- `app/components/dashboard/GpuMetricsChart.vue`

**GpuMetricsChart props:**
- `metricsHistory: MetricPoint[]` — Array of data points (latest last)
- `chartType: 'gpuUtil' | 'vram' | 'throughput' | 'requests'` — Chart configuration to use
- `height?: number` — Chart height in px (default: 256)
- `title?: string` — Chart title override

**Chart Configurations:**
1. **GPU Utilization** (`gpuUtil`): Line chart, 0-100% range, single line
2. **VRAM Usage** (`vram`): Area chart, GB scale, single line with area fill
3. **Throughput** (`throughput`): Line chart, tok/s scale, single line
4. **Requests** (`requests`): Multi-line, running vs waiting, two lines with legend

**Implementation details:**
- uPlot initialized in `onMounted()` using a template ref for the container div
- Watch `metricsHistory` with `{ deep: true }` — call `chart.setData()` with new series
- 150-point window (5 minutes at 2s intervals) — trim via the metrics store
- Responsive to container width using `ResizeObserver` (call `chart.setSize()`)
- Handle empty/null metric values gracefully (show "awaiting data..." placeholder)
- Clean up with `chart.destroy()` in `onUnmounted()`
- No re-render of the uPlot instance — always `setData()` / `setSize()` on existing instance

**Reusability Note:** The `chartType` prop and `metricKey` abstraction means this component can chart any numeric time series — not just GPU metrics. Future pages (benchmarks, usage tracking) can reuse it with different data.

**Acceptance Criteria (M1-T9-03):**
- [ ] Chart initializes on component mount with correct configuration per `chartType`
- [ ] Chart updates via `setData()` when `metricsHistory` changes — no re-mount
- [ ] 150-point window enforced (older points trimmed)
- [ ] Chart resizes responsively with container width
- [ ] Shows "awaiting data" placeholder when no metrics yet
- [ ] Handles null/undefined metric values without error
- [ ] Chart destroys cleanly on unmount (no memory leaks)
- [ ] All four chart types render correctly with proper axis labels

### M1-T9-04 — Live Log Viewer (LiveLog)

**Goal:** Build a reusable log viewer component that can display streaming logs from the WebSocket channel, with level filtering, search, and auto-scroll capabilities. Designed for reuse across agent logs, deployment logs, and benchmark logs in future milestones.

**Files to create:**
- `app/components/dashboard/LiveLog.vue`

**LiveLog props:**
- `logs: LogEntry[]` — Array of log entries to display
- `loading?: boolean` — Show loading state (default: false)
- `maxLogs?: number` — Max entries before trimming (default: 500)
- `filterable?: boolean` — Show level filter buttons (default: true)
- `searchable?: boolean` — Show search input (default: true)
- `height?: string` — Container height CSS (default: '320px')
- `levels?: Array<LogEntry['level']>` — Available level filters (default: all four)

**Features:**
- Level filter buttons: All, Error (red), Warning (yellow), Info (white), Debug (gray)
- Search input with debounced text filter (300ms)
- Auto-scroll to bottom on new log — pauses when user scrolls up
- "New logs below" indicator when paused
- Color-coded log level indicators (left border/icon)
- Timestamp display with relative + absolute tooltip
- Module/source column
- Empty state: "No logs yet. Logs will appear here when the agent starts streaming."
- Efficient rendering: simple scrollable div for MVP (virtual scrolling is M2+)

**Reusability:** This component accepts logs as a prop and is filterable/searchable via props. Future use cases:
- `app/components/deployment/DeploymentLogViewer.vue` can compose `LiveLog` with deployment-specific log source
- Benchmark log viewers can reuse with different `levels` configuration

**Acceptance Criteria (M1-T9-04):**
- [ ] Log viewer renders log entries with timestamp, level, module, message
- [ ] Level filtering works (All, Error, Warning, Info, Debug) — hides non-matching levels
- [ ] Search input filters log text with debounce
- [ ] Auto-scrolls to bottom for new logs
- [ ] Scrolling up pauses auto-scroll with "New logs below" indicator
- [ ] Error and Warning entries are visually distinct (color-coded)
- [ ] Entries beyond `maxLogs` are trimmed (FIFO)
- [ ] Empty state renders when no logs

### M1-T9-05 — Store Wiring + Overview Page

**Goal:** Wire up the overview page (`dashboard/index.vue`) to real data sources — REST API for initial agent list, WebSocket for real-time updates. Replace placeholder data with live agent data flowing through the Pinia stores.

**Files to modify:**
- `app/pages/dashboard/index.vue` — Wire to stores + WebSocket

**Implementation:**
1. On mount:
   - Call `useAgentsStore().fetchAgents()` via `GET /api/agents` (uses `useApi` composable)
   - Connect to `/ws/dashboard` (all agents) via `useWebSocketMetrics()`
   - Initialize metric buffers for each agent in store

2. Summary stats header cards wired to `agentsStore.meta`:
   - Total Servers, Online, Offline, Degraded (from computed values)

3. DataTable bound to `agentsStore.agentList`:
   - Columns: Name + StatusBadge, GPU (count × model), GPU Util (ProgressBar), VRAM (used/total + bar), Models Running (Tag), Last Seen (timeAgo)
   - Sort by lastSeenAt descending by default
   - Row click → router.push to `/dashboard/servers/{id}`
   - Real-time updates via WebSocket flush → store update → table reactivity

4. Add Server dialog:
   - Keep existing "Add Server" dialog with install instructions
   - Wire copy-to-clipboard with toast notification

5. Connection state indicator:
   - Show WebSocket connection status in header area (small indicator)
   - Display "Reconnecting..." when connection drops

6. WebSocket lifecycle:
   - `onUnmounted()` → `disconnect()` (handled by composable)
   - Auto-reconnect with exponential backoff (handled by composable)

**Acceptance Criteria (M1-T9-05):**
- [ ] Overview page fetches agents from `GET /api/agents` on mount
- [ ] DataTable columns display real agent data (not placeholders)
- [ ] Summary stats cards show correct aggregated counts
- [ ] WebSocket connection established and metrics update in real-time
- [ ] Sorting, pagination, and row selection work
- [ ] Clicking a row navigates to `/dashboard/servers/{id}`
- [ ] Empty state renders when no agents registered
- [ ] "Add Server" dialog displays install instructions with copy-to-clipboard
- [ ] WebSocket connection state indicator shown
- [ ] Table updates when agents come online/go offline via WebSocket

### M1-T9-06 — Detail Page Assembly

**Goal:** Complete the single-server detail page (`dashboard/servers/[id].vue`) by assembling all components, connecting to the per-agent WebSocket, and handling all states (loading, live, error, offline).

**Files to modify:**
- `app/pages/dashboard/servers/[id].vue` — Full implementation

**Layout:**
1. **Header section:**
   - Agent name (from store) + hostname
   - StatusBadge (online/offline/degraded)
   - GPU model + count summary
   - Uptime display
   - "Reconnect" button when offline

2. **Metric Cards row** (4 MetricCards):
   - GPU Utilization % (with severity coloring)
   - VRAM Used / Total GB
   - Requests (running / waiting)
   - Throughput (tok/s)

3. **Charts row** (2×2 grid on desktop, stacked on mobile):
   - GPU Utilization % — GpuMetricsChart (chartType: 'gpuUtil')
   - VRAM Usage — GpuMetricsChart (chartType: 'vram')
   - Throughput tok/s — GpuMetricsChart (chartType: 'throughput')
   - Requests — GpuMetricsChart (chartType: 'requests')

4. **Bottom panels** (2-column grid on desktop):
   - SystemResources (left/top)
   - QueueDiagnostics (right/top)
   - ModelList (full width or alongside)
   - LiveLog (full width at bottom)

5. **States:**
   - **Loading:** Skeleton cards while initial data loads
   - **Live:** All components rendering real data
   - **Offline/Error:** Agent offline banner, "Reconnect" button, stale data shown grayed out
   - **Empty:** No metrics yet — "Awaiting first metric data..." placeholder

6. **WebSocket lifecycle:**
   - Connect to `/ws/dashboard/{agentId}` on mount
   - Buffer metrics in store, bind components to store
   - Show connection state indicator
   - Auto-reconnect (handled by composable)

**Acceptance Criteria (M1-T9-06):**
- [ ] Header shows server name, StatusBadge, hostname, GPU summary, uptime
- [ ] Metric cards show current GPU util, VRAM, requests, throughput
- [ ] Charts row shows all 4 chart types with real-time updates
- [ ] System resources panel shows GPU, VRAM, RAM, CPU, Disk bars
- [ ] Queue diagnostics show running/waiting, KV cache, TTFT, bottleneck
- [ ] Model list shows running models
- [ ] Live log viewer shows agent logs streaming in real-time
- [ ] Log level filtering works
- [ ] Page shows loading skeleton while initial data loads
- [ ] Page shows error/offline state when agent is unreachable
- [ ] WebSocket connection state indicator visible in header
- [ ] All cleanup happens on unmount (no stale subscriptions)

## Acceptance Criteria

- [ ] Server overview page lists all registered agents from the backend
- [ ] Overview shows aggregate GPU utilization and VRAM for each server
- [ ] Clicking a server navigates to its detail page
- [ ] Single server detail page shows real-time charts updating every 2 seconds
- [ ] System resource bars show GPU, VRAM, RAM, CPU, Disk usage
- [ ] Queue diagnostics show running/waiting, KV cache, TTFT
- [ ] Live log viewer shows agent logs streaming in real-time
- [ ] Log level filtering works (Error, Warning, Info, Debug)
- [ ] WebSocket reconnects automatically on connection loss
- [ ] Charts handle empty/null metric values gracefully
- [ ] Server detail page shows error state when agent is offline

## Completion Criteria

- [ ] All acceptance criteria above pass
- [ ] TypeScript compiles without errors
- [ ] Pages render without console errors
- [ ] WebSocket metrics flow end-to-end: agent → backend → dashboard
- [ ] All components accept `class` prop for external styling overrides
- [ ] Shared types in `~/types/dashboard.ts` are used across all components (no duplicated interfaces)
- [ ] Utility functions in `~/utils/dashboard.ts` are pure — no component imports from them

## Testing Checklist

- [ ] Component test: MetricCard renders with all props
- [ ] Component test: StatusBadge shows correct color per status
- [ ] Component test: SystemResources renders bars correctly with color thresholds
- [ ] Component test: GpuBar renders with correct width and color
- [ ] Component test: LiveLog filters by level
- [ ] Integration test: uPlot chart initializes and updates with new data
- [ ] Integration test: Overview page renders agents from store and navigates on row click
- [ ] Unit test: Shared utility functions (formatGb, timeAgo, getVramColor)
- [ ] Unit test: Pinia store metric history buffer (max length, FIFO trim)

## Dependencies

- **Requires:** M1-T7 (Dashboard WS Broadcast), M1-T8 (Nuxt Dashboard Scaffold)
- **Blocks:** Milestone M2 (MVP Dashboard Enhancement — time range selector, model detail page, admin panel)

## Documentation References

- `requirements/03-functional-requirements.md` — F2.1, F2.2
- `requirements/06-api-surface.md` — agents API, metrics API
- `requirements/05-tech-stack.md` — uPlot, PrimeVue, Tailwind
- `requirements/07-directory-structure.md` — component locations

## Notes

- **Reusability is the priority.** Every component is designed to be consumed by future pages. No component imports stores or WebSocket composables directly — data flows in via props.
- uPlot is chosen for real-time charts because it renders 150 data points in ~5ms with no overhead.
- Initialize uPlot on `onMounted`, update via `setData()` — never re-mount the chart.
- The 150-point buffer = 5 minutes of data at 2s intervals, matching the "live" range (M2 adds time range selector).
- For MVP, charts use simple line plots — no time range selector (that's M2).
- Use the existing `vllm-dashboard.html` as a visual reference for chart layout and metric placement.
- Server overview auto-refreshes via WebSocket — no polling needed.
- Log viewer uses a simple scrollable div for MVP (virtual scrolling in future milestone).
- WebSocket reconnection is handled by VueUse's `useWebSocket` — 3s retry delay with exponential backoff.
- The `GpuMetricsChart` chartType prop abstraction means new chart types can be added by extending a single config map — no component changes needed.
