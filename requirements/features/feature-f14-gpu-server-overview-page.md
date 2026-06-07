# F14: GPU Server Overview Page

## Metadata
- **ID:** F14
- **Phase:** MVP
- **Effort:** Large
- **Dependencies:** F2, F5, F7, F10
- **Acceptance Criteria Count:** 7

## Description

The GPU server overview page (`/dashboard`) is the primary landing page of the ModelPrism dashboard, displayed immediately after login. It provides a bird's-eye view of all registered GPU servers in the user's workspace, showing their operational status, aggregate resource utilization, and the models currently deployed on each. This page answers the operator's first question: *"What is the state of my GPU fleet right now?"*

The page is driven by two data sources working in concert. On initial load, it fetches a JSON:API collection (`GET /api/agents`) from the FastAPI backend that returns the full list of registered agents with their hardware specs, status, last-seen timestamps, and aggregate metrics (total VRAM, aggregate GPU utilization, running model count). A persistent WebSocket connection (`/ws/dashboard`) then delivers real-time metric deltas — updated GPU utilization, VRAM usage, and model count — every 2 seconds from the Redis pub/sub pipeline that ingests agent metrics. The frontend merges these deltas into the Pinia `agents` store without re-fetching the entire collection, enabling a smooth live-updating view with zero polling overhead.

Each GPU server is rendered as a row in a PrimeVue `DataTable` (desktop) or a card stack (mobile) that conveys status at a glance: a color-coded status badge (green = online, yellow = degraded, gray = offline), a per-GPU utilization sparkline, aggregate VRAM bar, running model chips, and a "last seen" relative-time stamp. Rows are actionable — clicking a server navigates to the single-server dashboard at `/dashboard/servers/{agent_id}` (F15). The overview page also provides bulk actions (pause/resume selected servers) and an agent registration token generator (F6) so users can add new GPU servers without leaving the overview.

## Concrete Examples (Specification by Example)

### Example 1: Initial Page Load with Two GPU Servers

A workspace has two registered GPU servers: one online (agent ID `ag_a1b2c3d4`) with 4× NVIDIA A100-80GB GPUs running 2 models, and one offline (agent ID `ag_e5f6g7h8`) with 1× NVIDIA RTX 4090 that hasn't reported in 8 minutes.

- **Input:** Authenticated user navigates to `/dashboard`.
- **Action:** The page's `onMounted` hook dispatches two parallel requests:
  1. `GET /api/agents` (JSON:API) to `https://api.modelprism.io/api/agents` with `Authorization: Bearer eyJhbGci...`.
  2. `new WebSocket("wss://api.modelprism.io/ws/dashboard")` to open the real-time metrics stream.

- **Expected JSON:API Response (truncated):**
  ```json
  {
    "data": [
      {
        "id": "ag_a1b2c3d4",
        "type": "agent",
        "attributes": {
          "name": "cyan-koala-42",
          "status": "online",
          "hostname": "gpu-node-01",
          "agent_version": "0.1.0",
          "gpu_count": 4,
          "gpu_model": "NVIDIA A100-SXM4-80GB",
          "gpu_memory_total_mb": 324800,
          "gpu_memory_used_mb": 156000,
          "gpu_util_avg_pct": 73.5,
          "cpu_cores": 64,
          "ram_total_gb": 512.0,
          "ram_used_gb": 192.4,
          "disk_total_gb": 2048.0,
          "disk_used_gb": 876.2,
          "running_models": 2,
          "uptime_seconds": 284400,
          "last_seen_at": "2026-06-07T10:15:30.000Z",
          "created_at": "2026-06-01T08:00:00.000Z"
        },
        "relationships": {
          "deployments": {
            "data": [
              { "id": "dep_001", "type": "deployment" },
              { "id": "dep_002", "type": "deployment" }
            ]
          }
        }
      },
      {
        "id": "ag_e5f6g7h8",
        "type": "agent",
        "attributes": {
          "name": "lucky-bear-77",
          "status": "offline",
          "hostname": "gpu-node-02",
          "agent_version": "0.1.0",
          "gpu_count": 1,
          "gpu_model": "NVIDIA GeForce RTX 4090",
          "gpu_memory_total_mb": 24564,
          "gpu_memory_used_mb": 0,
          "gpu_util_avg_pct": 0.0,
          "cpu_cores": 24,
          "ram_total_gb": 128.0,
          "ram_used_gb": 64.0,
          "disk_total_gb": 1024.0,
          "disk_used_gb": 512.0,
          "running_models": 0,
          "uptime_seconds": 0,
          "last_seen_at": "2026-06-07T10:07:30.000Z",
          "created_at": "2026-06-05T14:00:00.000Z"
        },
        "relationships": {
          "deployments": { "data": [] }
        }
      }
    ],
    "meta": {
      "total": 2,
      "online": 1,
      "offline": 1,
      "total_gpu_count": 5,
      "total_gpu_vram_gb": 349.3,
      "total_running_models": 2
    }
  }
  ```

- **Expected UI:** A DataTable with two rows. The first row shows a green status badge, "cyan-koala-42", "4× A100-80GB", a utilization bar at 73.5% (orange), a VRAM bar at 48% (156 GB / 324.8 GB), two model chips ("Qwen2.5-72B-Instruct", "Mistral-7B-Instruct"), and "Last seen: 30s ago". The second row shows a gray status badge, "lucky-bear-77", "1× RTX 4090", zeroed bars, "No models", and "Last seen: 8m ago". A summary header card shows "2 Servers — 5 GPUs — 2 Models Running — 1 Offline".

### Example 2: Real-Time Metric Update via WebSocket

While the user is viewing the overview page, the agent on `ag_a1b2c3d4` sends a new 2-second metric snapshot.

- **Input:** WebSocket message arrives at `/ws/dashboard`:
  ```json
  {
    "type": "metrics",
    "agent_id": "ag_a1b2c3d4",
    "ts": "2026-06-07T10:15:32.000Z",
    "gpu_util_avg_pct": 82.1,
    "gpu_memory_used_mb": 172000,
    "running_models": 2,
    "ram_used_gb": 198.2,
    "disk_used_gb": 877.0
  }
  ```

- **Action:** The `useWebSocketMetrics` composable dispatches the delta to the Pinia `agents` store. The store updates `gpu_util_avg_pct` from 73.5 → 82.1, `gpu_memory_used_mb` from 156000 → 172000, and `ram_used_gb` from 192.4 → 198.2. The DataTable row for `ag_a1b2c3d4` re-renders with the new values. No HTTP request is made — the pinia store mutation is the sole source of the update.

- **Expected UI:** The GPU utilization bar smoothly transitions from 73.5% to 82.1%. The VRAM bar updates from 48% to 53%. The RAM bar updates. The summary header card's GPU utilization average (across all agents) recalculates. No visible flicker or full-table re-render occurs — only the affected cells update via PrimeVue DataTable's reactive change detection.

### Example 3: A New Model Deploys Mid-Session

The user deploys `Llama-3.1-405B-Instruct` onto `ag_a1b2c3d4` from the model deployment wizard (F19). The page automatically reflects the change.

- **Input:** The backend command handler (F11) confirms deployment success via WebSocket:
  ```json
  {
    "type": "agent_update",
    "agent_id": "ag_a1b2c3d4",
    "changes": {
      "running_models": 3,
      "gpu_memory_used_mb": 231000
    }
  }
  ```

- **Action:** The `agents` store increments `running_models` from 2 to 3 and updates VRAM usage. The model chip area renders a new chip: "Llama-3.1-405B-Instruct". The summary header increments "Models Running" to 3.

- **Expected UI:** The row for `cyan-koala-42` now shows three model chips (with overflow truncation). The VRAM bar adjusts to 71% (231 GB / 324.8 GB). The "Models Running" counter in the summary header reads 3. No toast or modal appears — the change is silent and automatic, reflecting the dashboard's role as a live monitoring surface. The user can click the new model chip to navigate directly to `/dashboard/models/{deployment_id}` (F22).

### Example 4: Generating a New Agent Registration Token

The user needs to add a new GPU server to the fleet.

- **Input:** User clicks the "Add Server" button in the top-right of the overview page. A PrimeVue `Dialog` opens with a "Generate Token" button inside.

- **Action:** The frontend calls `POST /api/agents/tokens` with JSON:API format:
  ```json
  {
    "data": {
      "type": "agent-token"
    }
  }
  ```

- **Expected Response:**
  ```json
  {
    "data": {
      "id": "tok_xyz789",
      "type": "agent-token",
      "attributes": {
        "token": "mp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
        "expires_at": "2026-06-08T10:15:00.000Z"
      }
    }
  }
  ```

- **Expected UI:** The dialog displays the raw token in a monospace `<code>` block inside a copyable text field (PrimeVue `InputText` with a copy-to-clipboard icon). Below the token, the dialog shows the formatted install command:
  ```bash
  curl -fsSL https://github.com/modelprism/agent/install.sh | \
    bash -s -- --server https://api.modelprism.io --token mp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
  ```
  A "Copy Command" button copies the install command to the clipboard. A countdown shows the token's remaining validity (24 hours from creation). A warning banner at the bottom reads: "This token will not be shown again. Copy it now." A "Done" button closes the dialog.

### Example 5: Server Degraded Status — GPU Memory Pressure

A server's aggregate GPU utilization exceeds 95% and available VRAM drops below 5 GB across all GPUs.

- **Input:** WebSocket metric delta arrives for agent `ag_a1b2c3d4` with `gpu_util_avg_pct: 97.2` and `gpu_memory_used_mb: 318000` (97.9% of 324800 MB total).

- **Action:** The Pinia `agents` store's computed property evaluates `agent.status` based on heuristics:
  - If `gpu_util_avg_pct >= 95` → status changes from `"online"` to `"degraded"`.
  - The store sets `agent.status = "degraded"`.

- **Expected UI:** The status badge changes from green to yellow. A tooltip on hover explains: "GPU at 97% — 6.8 GB VRAM free". The summary header card's "Online" count decrements by 1 and reflects the degraded state (e.g., "1 Online, 1 Degraded, 1 Offline"). The DataTable row is visually distinguished with a subtle yellow left border. No other data in the row changes. If VRAM frees up below the threshold on a subsequent update (e.g., a model is stopped), the status returns to `"online"` automatically.

## Acceptance Criteria

- **ACF14-1: Page loads agent list from JSON:API and renders a DataTable** — Navigating to `/dashboard` with a valid JWT sends `GET /api/agents` with `Authorization: Bearer <token>` and `Accept: application/vnd.api+json`. A successful 200 response populates a PrimeVue `DataTable` with one row per agent. Each row displays: agent name, status badge (green/yellow/gray), GPU model + count, GPU utilization bar (% with color coding: green < 70%, orange 70–94%, red ≥ 95%), VRAM bar (used/total with percentage), RAM bar (used/total), running models count (with model name chips when expanded), and "last seen" relative timestamp (e.g., "30s ago", "8m ago", "2h ago"). An empty response (`meta.total = 0`) renders a centered empty-state card with illustration and text: "No GPU servers yet. Add your first server to get started." plus an "Add Server" button.

- **ACF14-2: Real-time metric deltas update store without full-page reload** — After initial load, the page opens a WebSocket to `/ws/dashboard`. Incoming messages of type `metrics` and `agent_update` are dispatched to the Pinia `agents` store, which updates only the mutated fields of the relevant agent objects. The DataTable re-renders only the affected cells (PrimeVue reactive rendering with `row-key="id"`). If the WebSocket disconnects, the composable reconnects with exponential backoff (1s, 2s, 4s, max 30s) and displays a small banner: "Live updates paused — reconnecting..." which disappears on reconnect. A 30-second window of metric deltas is buffered during disconnection and replayed on reconnect (or discarded if the agent status changed to `offline`).

- **ACF14-3: Summary header card shows aggregate fleet statistics** — At the top of the page, above the DataTable, a row of metric cards (PrimeVue `Card` with `MetricCard` component) displays: total server count, total GPU count, aggregate GPU utilization (%), aggregate VRAM usage (used GB / total GB), total running models, and online/degraded/offline breakdown. These values are sourced from `meta` (initial load) and updated via WebSocket deltas (recalculated client-side by the Pinia store). Each metric card shows a trend direction arrow (up/down/steady) compared to 5 minutes ago, computed by comparing against a rolling window of metric snapshots in the store.

- **ACF14-4: Row click navigates to single-server dashboard** — Clicking anywhere on a DataTable row (except interactive elements like action buttons or model chips) triggers `navigateTo("/dashboard/servers/{agent_id}")`. Clicking a model chip navigates to `navigateTo("/dashboard/models/{deployment_id}")`. Both navigations preserve the current WebSocket connection (the dashboard WS handler in F16 manages multiple subscriptions) and do not trigger a full page reload. Clicking the "Pause" or "Stop" action button in a row opens a confirmation dialog (PrimeVue `ConfirmDialog`) before sending the lifecycle command via the agents WebSocket.

- **ACF14-5: "Add Server" dialog generates and displays a registration token** — Clicking "Add Server" in the summary header or empty state opens a PrimeVue `Dialog` with a "Generate Token" button. After generation (`POST /api/agents/tokens`), the dialog displays: the raw token in a monospace, copyable `InputText` field; the full install command (`curl ... | bash -s -- --server ... --token ...`) in a copyable `<pre>` block; a countdown of token validity (24 hours from creation); and the warning banner "This token will not be shown again. Copy it now." The "Copy Command" button copies the install command to the clipboard using `navigator.clipboard.writeText()`. A "Done" button closes the dialog. Generating a second token invalidates the previous one (two-phase token registration in F6).

- **ACF14-6: Degraded status triggers automatically based on GPU thresholds** — The Pinia `agents` store computes the `status` field based on the latest metric data: if `gpu_util_avg_pct >= 95` OR `(gpu_memory_total_mb - gpu_memory_used_mb) < 5120` (less than 5 GB free VRAM) AND the agent WebSocket is connected and metrics are flowing, the status is set to `"degraded"`. If the WebSocket has been disconnected for more than 60 seconds, the status is set to `"offline"`. If the WebSocket is connected and neither condition is met, the status is `"online"`. The status badge (PrimeVue `Tag` with `severity` mapping: `online` → `success`, `degraded` → `warn`, `offline` → `secondary`) re-renders reactively when the store's computed property updates. The summary header card reflects the count of servers in each status.

- **ACF14-7: Pagination and search work for large agent fleets** — If the workspace has more than 25 agents, the backend paginates the JSON:API response with `page[number]` and `page[size]` query parameters. The DataTable renders PrimeVue `Paginator` at the bottom with configurable page sizes (10, 25, 50). A search input above the DataTable filters agents client-side by name and hostname (case-insensitive `string.includes()` match). The summary header statistics (total servers, total GPUs, etc.) reflect all agents in the workspace (not just the current page — sourced from `meta`). WebSocket metric deltas continue to update all agents regardless of the current page; paginated rows that are not visible update their data in the Pinia store but the DOM re-renders only when the user pages to that row.

## Technical Notes

### File Map

**Frontend (Nuxt 4):**
- `frontend/app/pages/dashboard/index.vue` — The overview page. PrimeVue `DataTable` for the agent list, summary header `MetricCard` row, "Add Server" `Dialog`, search input, paginator. Uses `useAgents()` composable and `useWebSocketMetrics()` composable.
- `frontend/app/composables/useAgents.ts` — Pinia wrapper around agent CRUD operations:
  - `fetchAgents()` — `GET /api/agents` with JSON:API deserialization, stores result in Pinia `agents` store.
  - `generateToken()` — `POST /api/agents/tokens`, returns the raw token and expiry.
  - `pauseAgent(id)` / `resumeAgent(id)` / `stopAgent(id)` — Sends lifecycle commands via WebSocket (F13).
  - Merges WebSocket metric deltas into the store's agent objects.
- `frontend/stores/agents.ts` — Pinia store:
  - State: `agents: Map<UUID, Agent>`, `meta` (total, online, offline, degraded, totalGpuCount, totalRunningModels), `metricBuffer: Map<UUID, MetricSnapshot[]>` (rolling window for trend computation).
  - Getters: `onlineAgents`, `degradedAgents`, `offlineAgents`, `aggregateGpuUtil`, `aggregateVramGb`.
  - Actions: `setAgents()`, `updateAgentMetrics()`, `updateAgentStatus()`.
  - The `status` field is a **computed property** derived from raw metrics (utilization thresholds, WebSocket connection state) — it is never stored as a raw database column. The backend returns `status` as a convenience field in the JSON:API response (computed from `last_seen_at`), but the frontend may override it based on live WebSocket data.
- `frontend/app/composables/useWebSocketMetrics.ts` — WebSocket client composable:
  - Connects to `wss://<api-base>/ws/dashboard` (or `ws://` in development).
  - Parses incoming messages: `metrics`, `agent_update`, `heartbeat`.
  - Dispatches to the `useAgents` store. Buffers messages during reconnect.
  - Exposes reactive `connectionState: "connected" | "disconnected" | "reconnecting"`.
  - Reconnect with exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s max.
- `frontend/app/components/dashboard/AgentTableRow.vue` — Reusable row component for the agent list (server-side pagination variant) and single-agent detail cards.
- `frontend/app/components/common/MetricCard.vue` — Reusable stat card: label, value, unit, trend arrow (up/down/steady), optional sparkline. Used in the summary header row and throughout F15.
- `frontend/app/components/common/StatusBadge.vue` — PrimeVue `Tag` wrapper. Maps `online` → severity=`success`, `degraded` → severity=`warn`, `offline` → severity=`secondary`. Shows a tooltip on hover with details.

**Backend (FastAPI):**
- `backend/app/api/agents.py` — Route handler for `GET /api/agents`:
  - Returns JSON:API `Document` with agent resources.
  - Supports pagination: `?page[number]=1&page[size]=25`.
  - Supports filter: `?filter[status]=online` (optional).
  - Supports sort: `?sort=-created_at` (default by creation date descending).
  - `meta` block includes aggregate statistics for the workspace (total agents, online count, offline count, total GPUs, total VRAM, total running models).
- `backend/app/api/agents.py` — Route handler for `POST /api/agents/tokens`:
  - Creates a new agent registration token via the agent manager service.
  - Returns the raw token and expiry in JSON:API format.
  - Each workspace can have at most one active unclaimed token at a time (generating a new one invalidates the previous).
- `backend/app/services/agent_manager.py` — Business logic:
  - `get_agents(workspace_id, filters, pagination)` — Queries `agents` table, joins with latest metrics from the `agent_metrics` downsampled view, computes `status` from `last_seen_at`, returns paginated results with aggregate meta.
  - `generate_token(workspace_id)` — Creates an `agent_registration_tokens` row, invalidates any existing unclaimed token for the workspace.
- `backend/app/ws/dashboard_ws.py` — WebSocket handler for `/ws/dashboard`:
  - Authenticates via JWT (same JWT as REST API).
  - Subscribes to the workspace's Redis pub/sub channel for metric broadcasts.
  - Forwards metric messages to the connected browser client.
  - Supports a single WebSocket per browser tab (the overview page). The single-server dashboard (F15) uses a separate WebSocket path `/ws/dashboard/{agent_id}`.

**Shared:**
- `backend/app/schemas/agent.py` — Pydantic models for JSON:API agent resource serialization:
  ```python
  class AgentAttributes(BaseModel):
      name: str
      status: str  # "online" | "offline" | "degraded"
      hostname: str
      agent_version: str
      gpu_count: int
      gpu_model: str
      gpu_memory_total_mb: int
      gpu_memory_used_mb: int
      gpu_util_avg_pct: float
      cpu_cores: int
      ram_total_gb: float
      ram_used_gb: float
      disk_total_gb: float
      disk_used_gb: float
      running_models: int
      uptime_seconds: int
      last_seen_at: datetime
      created_at: datetime
  ```

### Status Computation Logic

The agent status is computed client-side and server-side using the same rules:

| Condition | Status |
|-----------|--------|
| `last_seen_at` is within the last 60 seconds AND WebSocket is connected AND `gpu_util_avg_pct < 95` AND free VRAM >= 5 GB | `online` |
| `last_seen_at` is within the last 60 seconds AND WebSocket is connected AND (`gpu_util_avg_pct >= 95` OR free VRAM < 5 GB) | `degraded` |
| `last_seen_at` is more than 60 seconds ago OR WebSocket is disconnected | `offline` |

The server-side `status` in the JSON:API response is computed from `last_seen_at` only (a database column). The frontend may override it based on the more granular WebSocket metric stream. This dual-source approach means the page is always accurate even during the brief window between initial load (REST) and WebSocket connection establishment.

### WebSocket Data Flow

```
Agent (every 2s)                Backend                Redis Pub/Sub          Browser
     │                             │                       │                    │
     │── WebSocket metrics ───────>│                       │                    │
     │   (to /ws/agents/{id})      │── publish ──────────>│                    │
     │                             │                       │── broadcast ──────>│
     │                             │                       │   (via /ws/dashboard)│
     │                             │                       │                    │
     │                             │                       │                    │
     │                             │                       │   ┌────────────────┴────┐
     │                             │                       │   │ Pinia agents store  │
     │                             │                       │   │                     │
     │                             │                       │   │ mergeMetricsDelta() │
     │                             │                       │   │ updateStatus()      │
     │                             │                       │   └─────────────────────┘
```

### Edge Cases

- **First load before WebSocket connects:** The DataTable renders from the JSON:API response immediately. The summary header may show slightly stale metrics (up to the polling delay of the agent to backend to REST response) until the WebSocket delivers the first update (~2 seconds after page load).
- **All servers offline:** The page renders all rows with gray status badges, zeroed bars, and "N/A" model chips. The summary header shows "0 Online — X Offline". An info banner renders: "Your servers appear offline. Check that the modelprism-agent is running and can reach the backend."
- **Single server, single GPU:** The page works identically — one DataTable row. The "aggregate" statistics in the summary header equal the single server's values.
- **Agent name contains special characters:** Agent names are auto-generated (e.g., `cyan-koala-42`) by the naming service and are alphanumeric with hyphens. User-customized names may contain spaces, underscores, or Unicode characters — the DataTable renders these via `v-text` (not `v-html`) and sorts them via `String.localeCompare()` with no special sanitisation needed.
- **Large model name truncation:** Model name chips in the row use a `max-width` of 200px with `text-overflow: ellipsis`. The full model name is shown in a tooltip on hover.
- **Concurrent token generation:** If two browser tabs generate tokens simultaneously, the second request invalidates the first. The first tab's dialog displays a warning banner: "This token has been superseded by a newer token." The user must generate a new one.

### Integration Points

- **F2 (Frontend Scaffolding):** The overview page lives at `dashboard/index.vue`, which was scaffolded as a stub in F2. The dashboard layout (`layouts/dashboard.vue`), `useApi` composable, auth middleware, and sidebar navigation with "Servers" highlighted as active are all provided by F2.
- **F5 (Email/Password Auth):** The page requires a valid JWT — the F5 auth middleware and `useAuth` composable ensure the user is authenticated before the page renders. Token refresh happens transparently in the background.
- **F6 (Agent Registration):** The "Add Server" dialog calls `POST /api/agents/tokens` — this endpoint is defined in F6. The token display and install command copy functionality depend on the token format and two-phase registration flow from F6.
- **F7 (Agent WebSocket):** The agent → backend WebSocket connection (F7) is the upstream source of metric data. Without F7, the overview page is a static snapshot with no real-time updates.
- **F9 (Agent Metric Push):** The 2-second metric push from agents (F9) feeds the Redis pub/sub channel that `/ws/dashboard` subscribes to. The metric delta format in the WebSocket messages is defined in F9's shared schemas.
- **F10 (Backend Metric Ingestion):** The historical metric data accessed by `GET /api/agents` (the aggregate `gpu_util_avg_pct`, `gpu_memory_used_mb`) is sourced from the downsampled metrics stored by F10. The meta block's aggregate statistics are computed by F10's query layer.
- **F13 (Agent Lifecycle):** The "Pause" and "Stop" action buttons in each DataTable row send lifecycle commands via the agents WebSocket. F13 defines the pause/resume/stop lifecycle and the command format.
- **F15 (Single Server Dashboard):** The overview page is the entry point to the single-server dashboard — clicking a DataTable row navigates to F15 at `/dashboard/servers/{agent_id}`.
- **F16 (WebSocket Broadcast):** The `/ws/dashboard` WebSocket endpoint used by the overview page is defined in F16. This endpoint subscribes to the workspace's Redis pub/sub channel and forwards metric broadcasts to all browser tabs viewing the overview.

## Depends on: F2 (Frontend scaffolding), F5 (Email/password auth), F7 (Agent WebSocket connection), F10 (Backend metric ingestion)
