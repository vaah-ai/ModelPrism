# Task M1-T9 — Dashboard Pages

> **Milestone:** M1 (Foundation)
> **Priority:** High
> **Status:** ⚪ Not Started
>
> **Impact from M1-T8:** Nuxt Dashboard Scaffold completed.
>
> **Impact from M1-T7:** Dashboard WebSocket Broadcast completed.
> - Backend provides `/ws/dashboard` (all agents) and `/ws/dashboard/{agent_id}` (per-agent) endpoints
> - Endpoints subscribe to Redis `metrics:{id}` channel (published by agent_ws.py every 2s) and forward transformed (averaged) flat metrics
> - Transformed format matches what `useWebSocketMetrics.ts` expects: `gpu_util_avg_pct`, `gpu_memory_used_mb`, `ram_used_gb`, `cpu_pct`, etc.
> - Raw GPU arrays from agents are averaged via `avg_gpu_field()` before forwarding
> - Backend handles ping/pong keepalive, replay_request (MVP stub — returns empty batch), and clean disconnect
> - No auth for MVP — direct WS connections
> - See `backend/app/ws/dashboard_ws.py` for handler implementation
> - Dashboard layout at `app/layouts/dashboard.vue` with sidebar PanelMenu navigation and responsive overlay
> - Pages scaffolded: `dashboard/index.vue` (overview) and `dashboard/servers/[id].vue` (detail) with placeholder panels marked "M1-T9"
> - Pinia stores: `stores/agents.ts` (agent list with fetchAgents, applyMetricDelta, updateAgentStatus) and `stores/metrics.ts` (per-agent metric buffer)
> - Composables: `useApi.ts` ($fetch wrapper to FastAPI base URL), `useWebSocketMetrics.ts` (WebSocket lifecycle with 500ms batch, auto-reconnect, message dispatch to stores)
> - Backend URL configurable via `NUXT_PUBLIC_BACKEND_URL` env var (defaults to `http://localhost:8000`)
> - WebSocket composable connects to `ws://<backendUrl>/ws/dashboard` expecting `metrics`, `agent_status`, `agent_update`, `replay_batch` message types per F16 spec
> - No auth middleware — direct HTTP/WS calls to FastAPI without JWT headers for MVP
> - Old `vllm-dashboard.html` preserved for chart layout reference
> **Estimated Effort:** 4 days

## Description

Implement the two core dashboard pages: the GPU server overview page (list all registered servers with aggregate metrics) and the single-server detail page (real-time charts, system resources, diagnostic cards, and live log viewer). Consume the FastAPI backend directly via REST for initial data load and WebSocket for real-time updates. Use uPlot for real-time GPU charts and PrimeVue components for the UI.

## Task Goals

- Implement server overview page with agent list, status indicators, aggregate GPU utilization, VRAM usage
- Implement single server detail page with real-time uPlot charts (GPU utilization, VRAM, throughput)
- Implement system resource cards (GPU, RAM, CPU, Disk with bars)
- Implement diagnostic cards (queue depth, KV cache, TTFT, bottleneck indicator)
- Implement live log viewer with streaming updates and level filtering
- Implement MetricCard common component for displaying key-value stats
- Implement StatusBadge component for online/offline status
- Wire up WebSocket composable for real-time metric updates on both pages

## Implementation Plan

> ⚠️ Analyze this plan thoroughly before implementing.

### Pre-Implementation Analysis

- Review the existing `vllm-dashboard.html` for proven chart layouts and metric display patterns
- Review `requirements/03-functional-requirements.md` F2.1 (Server Overview) and F2.2 (Single Server Dashboard)
- Review `requirements/06-api-surface.md` for metrics API format
- Review `requirements/05-tech-stack.md` for uPlot charting with 2s update intervals
- Invoke `nuxt` skill for Nuxt page patterns, PrimeVue component usage, and uPlot integration

### Steps

1. Create `app/components/common/MetricCard.vue`:
   - Props: `label`, `value`, `unit`, `trend` (up/down/stable), `severity` (info/success/warn/danger)
   - PrimeVue Card with styled display
   - Small trend arrow indicator

2. Create `app/components/common/StatusBadge.vue`:
   - Props: `status` (online/offline/connecting)
   - Color-coded badge: green pulse for online, gray for offline, yellow for connecting

3. Create `app/components/dashboard/SystemResources.vue`:
   - Props: `metrics` (MetricSnapshot)
   - GPU utilization bar (with temperature and power draw)
   - VRAM used / total bar
   - RAM used / total bar
   - CPU utilization with load averages
   - Disk used / total bar
   - Uses PrimeVue ProgressBar, styled with Tailwind

4. Create `app/components/dashboard/QueueDiagnostics.vue`:
   - Props: `metrics` (MetricSnapshot)
   - Running / waiting request counts
   - KV cache utilization bar
   - TTFT p50 and p99 display
   - Error rate and truncation rate

5. Create `app/components/dashboard/GpuMetricsChart.vue`:
   - Uses uPlot for real-time charting
   - Props: `metricsHistory` (array of MetricSnapshot), `metricKey` (which metric to chart)
   - Four chart instances on the detail page:
     - GPU Utilization % (line, 0-100%)
     - VRAM Used GB (line, area fill)
     - Throughput tok/s (line)
     - Requests (running/waiting, two lines)
   - 150 data points window (5 minutes at 2s intervals)
   - uPlot initialized on mount, updated via `setData()` on prop change (no re-render)
   - Chart sizing: responsive to container width

6. Create `app/components/dashboard/ModelList.vue`:
   - Props: `models` (list of running models)
   - Simple card showing running model names and basic stats
   - For MVP: shows model name + status from agent metrics

7. Create `app/components/dashboard/LiveLog.vue`:
   - Subscribe to `logs:{agent_id}` channel via WebSocket
   - Virtual scrolling log viewer (or simple scrollable div for MVP)
   - Filter buttons: All, Error, Warning, Info, Debug
   - Auto-scroll to bottom with pause-on-scroll-up
   - Color-coded log levels (red=error, yellow=warn, white=info, gray=debug)
   - Search input to filter log text

8. Update `app/pages/dashboard/index.vue` (Server Overview):
   - On mount: `GET /api/agents` → populate agent list
   - Connect to `/ws/dashboard` for aggregate real-time updates
   - DataTable with columns: Name, Status, GPU Model, GPU Count, GPU Util %, VRAM Used/Total, Models Running, Last Seen
   - Click row → navigates to `/dashboard/servers/{id}`
   - Auto-refresh: WebSocket updates the table in real-time
   - Empty state: "No GPU servers registered" with instructions

9. Update `app/pages/dashboard/servers/[id].vue` (Single Server Detail):
   - Header: server name, status indicator (StatusBadge), GPU model, specs summary, uptime
   - Connect to `/ws/dashboard/{agentId}` for real-time metrics
   - Charts row (2×2 grid):
     - GPU Utilization %
     - VRAM Usage
     - Throughput (tok/s)
     - Requests (running vs waiting)
   - System Resources panel (SystemResources component)
   - Queue Diagnostics panel (QueueDiagnostics component)
   - Running models card (ModelList component)
   - Live Log viewer (LiveLog component)
   - Loading skeleton while metrics arrive
   - Error state if agent is offline

10. Update Pinia stores with full implementation:
    - `stores/agents.ts`: `fetchAgents()` (GET /api/agents), `fetchAgent(id)` (GET /api/agents/{id}), `agents` ref, `currentAgent` ref
    - `stores/metrics.ts`: `updateMetrics(agentId, data)` — append to history buffer (max 150), `getHistory(agentId)` — return history for charting, `getLatest(agentId)` — return latest snapshot

### Skills & MCP Servers

| Resource              | Purpose                      | When to Invoke                   |
| --------------------- | ---------------------------- | -------------------------------- |
| `nuxt`                | Nuxt pages, PrimeVue, uPlot  | Steps 1-10 — component creation  |
| `filesystem` (MCP)    | File creation                | Creating component files         |

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

## Testing Checklist

- [ ] Component test: MetricCard renders with props
- [ ] Component test: StatusBadge shows correct color per status
- [ ] Component test: SystemResources renders bars correctly
- [ ] Integration test: uPlot chart updates with new data
- [ ] Component test: LiveLog filters by level
- [ ] Unit test: Pinia store metric history buffer (max 150, FIFO)

## Dependencies

- **Requires:** M1-T7 (Dashboard WS Broadcast), M1-T8 (Nuxt Dashboard Scaffold)
- **Blocks:** Milestone M2 (MVP Dashboard Enhancement)

## Documentation References

- `requirements/03-functional-requirements.md` — F2.1, F2.2
- `requirements/06-api-surface.md` — agents API, metrics API
- `requirements/05-tech-stack.md` — uPlot, PrimeVue, Tailwind
- `requirements/07-directory-structure.md` — component locations

## Notes

- uPlot is chosen for real-time charts because it renders 150 data points in ~5ms with no overhead
- Initialize uPlot on `onMounted`, update via `setData()` — never re-mount the chart
- The 150-point buffer = 5 minutes of data at 2s intervals, matching the "live" range
- For MVP, charts use simple line plots — no time range selector (that's M2)
- Use the existing `vllm-dashboard.html` as a visual reference for chart layout and metric placement
- Server overview auto-refreshes via WebSocket — no polling needed
- Log viewer uses a simple scrollable div for MVP (virtual scrolling in future milestone)
- WebSocket reconnection is handled by VueUse's `useWebSocket` — 3s retry delay
