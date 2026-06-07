# F17: Time Range Selector

## Metadata
- **ID:** F17
- **Phase:** MVP
- **Effort:** Medium
- **Dependencies:** F10
- **Acceptance Criteria Count:** 7

## Description

The time range selector is the primary temporal navigation control for every chart, table, and metric display across the ModelPrism dashboard. It appears as a reusable horizontal bar of preset buttons and a custom date-time picker overlay in the GPU server overview page (F14), the single-server dashboard (F15), the usage tracking page (F29), and the benchmark comparison page (F26). When a user selects a time range, all visible charts — GPU utilization lines, VRAM timelines, throughput graphs, request queue history, TTFT P99 trends, and token usage bars — shift to show data exclusively within that window. The selection is stored as reactive Pinia state so that changing the range on any page updates all charts on that page, and navigating between pages preserves the selection within the same session.

The selector offers **twelve preset ranges**: **Live** (2-second WebSocket resolution, rolling 5-minute window), **5 minutes**, **15 minutes**, **1 hour**, **6 hours**, **12 hours**, **1 day**, **3 days**, **1 week**, **1 month**, **3 months**, **6 months**, and **1 year**. A **Custom** option opens a date-time picker with ISO 8601 start/end inputs (timezone-aware, defaulting to UTC). The selected range drives two query paths: (a) the **live WebSocket stream** for the Live preset, where the dashboard subscribes to real-time metric push from F16 and renders a continuously scrolling window; and (b) the **REST historical data query** for all other presets and custom dates, where the frontend fetches downsampled metrics from `GET /api/metrics/{agent_id}` with query parameters that map to F10's tiered storage. The backend routes to the appropriate table — raw `agent_metrics` for ranges under 1 hour, `metric_aggregates_1m` for ranges from 1 hour to 30 days, and `metric_aggregates_5m` for ranges beyond 30 days — keeping query latency under 500 ms regardless of range width.

The component lives at `frontend/app/components/common/TimeRangeSelector.vue` and emits a selected range object `{ preset: string, since: ISO8601, until: ISO8601, resolution: string }`. Any dashboard page imports the component and passes the selected range to its chart composables or API call helpers. uPlot chart instances handle updates by calling `chart.setData()` with the new time-bucketed series, avoiding full re-renders. Live mode uses `frontend/app/composables/useLiveMetrics.ts`, which manages a WebSocket subscription (F16) and a rotating ring buffer — the UI renders the last 5 minutes of 2-second data points, dropping older points as new ones arrive.

## Concrete Examples (Specification by Example)

### Example 1: Selecting "1 Hour" on the Single-Server Dashboard

- **Input:** A user is viewing the single-server dashboard for agent `ag_cyan_koala_42` (UUID `a1b2c3d4-e5f6-7890-abcd-ef1234567890`). The current time range is "Live". The user clicks the **1 hour** preset button in `TimeRangeSelector.vue`.
- **Action:** The Pinia store (`frontend/stores/timeRange.ts`) updates `activeRange` to:

```json
{
  "preset": "1h",
  "since": "2026-06-07T12:00:00.000Z",
  "until": "2026-06-07T13:00:00.000Z",
  "resolution": "1m"
}
```

The `useMetrics` composable (`frontend/app/composables/useMetrics.ts`) detects the change via a `watch()` on the store and issues:

```
GET /api/metrics/a1b2c3d4-e5f6-7890-abcd-ef1234567890
  ?since=2026-06-07T12:00:00.000Z
  &until=2026-06-07T13:00:00.000Z
  &bucket=1m
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

The backend's `metric_query_service.py` computes `range_width = 1h`, consults `RANGE_TABLE_MAP`, and routes the query to `metric_aggregates_1m`. It returns 60 data points (one per minute), each containing `avg`, `min`, `max`, `p50`, `p95`, `p99` for all numeric metric fields.

- **Expected Output:** The dashboard renders GPU utilization, VRAM, throughput, and request queue charts covering 12:00–13:00 UTC with 1-minute resolution. The x-axis ticks align at 5-minute intervals. The time range selector highlights the "1 hour" button. Any WebSocket subscription (active for Live mode) is closed and replaced by the REST poll. Each chart calls `chart.setData()` with the new series; no component re-mounts.

### Example 2: Live Mode with Rolling WebSocket Window

- **Input:** A user is viewing the GPU server overview page (F14) with the time range set to "Live". The page connects to the WebSocket broadcast channel (F16) and shows GPU utilization sparklines for four agents, each updating every 2 seconds.
- **Action:** The frontend calls `useLiveMetrics()` which opens a single WebSocket connection to `wss://api.modelprism.io/ws/workspaces/ws_abc?token=eyJhbGci...`. Incoming messages arrive in this format:

```json
{
  "type": "metrics",
  "agent_id": "ag_cyan_koala_42",
  "ts": "2026-06-07T14:30:02.000Z",
  "gpu": [{ "index": 0, "util_pct": 87.2, "mem_used_mb": 42100 }],
  "gpu_cache_pct": 62.5
}
```

Messages are pushed into a per-agent ring buffer capped at 150 entries (5 minutes × 60 / 2 seconds = 150). When the buffer exceeds 150 entries, the oldest entry is dropped. Sparkline components re-render every 500 ms (batched via `requestAnimationFrame`) with the current buffer contents.

- **Expected Output:** Four sparklines show a continuously scrolling chart window covering the last 5 minutes. As new data arrives every 2 seconds, the chart shifts left by one point and the rightmost point updates. X-axis labels show HH:MM:SS. The "Live" button shows a pulsing green dot indicator (CSS animation on `.live-indicator`). The backend pushes exactly one WebSocket message per agent per 2-second interval; the frontend ring buffer never exceeds 150 entries. Switching to another page calls `onUnmounted()`, which closes the WebSocket and clears the ring buffer.

### Example 3: Custom Date Range — Cross-Month Usage Query

- **Input:** A user on the usage tracking page (F29) clicks the "Custom" button. A PrimeVue `DatePicker` overlay (two inputs, `start` and `end`, `appendTo="body"`) appears. The user selects start `2026-05-15 00:00 UTC` and end `2026-06-15 23:59 UTC`, then clicks "Apply".
- **Action:** The store updates:

```json
{
  "preset": "custom",
  "since": "2026-05-15T00:00:00.000Z",
  "until": "2026-06-15T23:59:59.000Z",
  "resolution": "1d"
}
```

The usage composable calls the usage metrics endpoint:

```
GET /api/usage?workspace_id=ws_abc&since=2026-05-15T00:00:00.000Z&until=2026-06-15T23:59:59.000Z&group=day
Authorization: Bearer eyJhbGci...
```

- **Expected Response (JSON:API):**

```json
{
  "data": [
    {
      "type": "usageDataPoints",
      "id": "2026-05-15",
      "attributes": {
        "date": "2026-05-15",
        "inputTokens": 12500000,
        "outputTokens": 4200000,
        "costCents": 1250,
        "requestCount": 84500
      }
    }
  ],
  "meta": {
    "totalDays": 32,
    "currency": "USD",
    "bucket": "1d"
  }
}
```

- **Expected Output:** The usage page shows a bar chart with 32 daily columns. The time range selector highlights "Custom" and displays the date range as "May 15, 2026 – Jun 15, 2026". The date picker overlay closes. Hovering over a bar shows a tooltip with the date and exact values. The aggregate footer reads "31 days of usage (2026-05-15 — 2026-06-14)".

### Example 4: Range Change Triggers Cross-Page Refetch on Return

- **Input:** A user is on the single-server dashboard for agent `ag_cyan_koala_42` viewing the "1 hour" GPU utilization chart. They navigate to the running models page, then return to the dashboard after 30 minutes.
- **Action:** `onMounted()` reads `useTimeRangeStore().activeRange` and finds it still set to `{ preset: "1h", since: "2026-06-07T12:00:00.000Z", until: "2026-06-07T13:00:00.000Z" }`. The composable detects that `until` is now 30 minutes in the past (stale range) and calls `refreshToNow()`, which rewinds `since = now() - 1h` and sets `until = now()`. It then issues:

```
GET /api/metrics/a1b2c3d4...?since=2026-06-07T13:00:00.000Z&until=2026-06-07T13:30:00.000Z&bucket=1m
```

- **Expected Output:** The charts render the last 60 minutes of data (a 30-minute window the user was away plus the preceding 30 minutes). No stale data is visible. The x-axis updates to the new time window. The "1 hour" preset remains highlighted. There is no flicker — charts show a loading skeleton (`PrimeVue Skeleton` for 3px × width) during the 150ms debounced fetch.

### Example 5: Backend Routes Query to Correct Aggregate Table

- **Input:** The frontend requests a 3-month range for benchmark charts on F26:

```
GET /api/metrics/a1b2c3d4...?since=2026-03-07T00:00:00.000Z&until=2026-06-07T00:00:00.000Z&bucket=1d
```

- **Action:** The backend computes `range_width = 92 days`. It traverses `RANGE_TABLE_MAP`:
  - `92 days > 1 hour` → skip `agent_metrics`
  - `92 days > 30 days` → skip `metric_aggregates_1m`
  - `92 days ≤ 365 days` → select `metric_aggregates_5m`

It executes `SELECT * FROM metric_aggregates_5m WHERE agent_id = :aid AND bucket_ts >= :since AND bucket_ts < :until ORDER BY bucket_ts ASC`. The 5m table stores every-5-minute data; the frontend has requested `bucket=1d`, so the query layer groups 288 rows (5m × 288 = 24h) per day into one aggregate row using PostgreSQL `date_trunc('day', bucket_ts)` with `AVG`, `MIN`, `MAX`, and approximate percentile re-aggregation from stored p50/p95/p99 values.

- **Expected Response (JSON:API, truncated to one data point):**

```json
{
  "data": [
    {
      "type": "metricDataPoints",
      "id": "2026-03-07T00:00:00.000Z",
      "attributes": {
        "ts": "2026-03-07T00:00:00.000Z",
        "avg": 76.4,
        "min": 12.3,
        "max": 99.1,
        "p50": 78.2,
        "p95": 95.8,
        "p99": 98.7,
        "gpuUtilPct": 76.4,
        "vramUsedGb": 38.2,
        "tokPerSec": 142.1
      }
    }
  ],
  "meta": {
    "sourceTable": "metric_aggregates_5m",
    "dataPoints": 92,
    "bucket": "1d"
  }
}
```

- **Expected Output:** The benchmark comparison renders 92 daily data points. Query latency is under 400 ms. The `meta.sourceTable` field confirms the routing decision.

## Acceptance Criteria

- **ACF17-1: Time range selector renders twelve presets and a custom option** — The `TimeRangeSelector.vue` component renders clickable preset buttons for Live, 5m, 15m, 1h, 6h, 12h, 1d, 3d, 1w, 1mo, 3mo, 6mo, 1y, and a "Custom" button that opens a date-time picker with ISO 8601-compliant start/end inputs (timezone-aware, defaulting to UTC with a "(UTC)" label). The active preset is visually highlighted via a `bg-primary` class on the selected button. The component emits a `range-change` event with `{ preset: string, since: ISO8601, until: ISO8601, resolution: string }` on every selection change. The emitted `since` and `until` are always in UTC ISO 8601 format (e.g., `2026-06-07T12:00:00.000Z`) with microsecond precision trimmed to milliseconds. The component is self-contained — it accepts no required props and communicates its selection through the Pinia store and the `range-change` event.

- **ACF17-2: Range changes trigger data refetch on all visible charts** — When a new time range is selected, every chart component on the page (GPU utilization, VRAM, throughput, request queue, TTFT, cost comparison, token usage) receives the updated range and calls its respective API fetch function or WebSocket handler. Each chart displays data exclusively within the selected window; no chart shows data from outside the window. The refetch completes within 500 ms for presets up to 1 week and within 2 seconds for ranges up to 1 year, measured from click to chart update on a production-like dataset with 10 agents × 30 days of aggregated metrics. The `useMetrics` composable debounces range changes by 150 ms to prevent duplicate fetches during rapid preset switching.

- **ACF17-3: Live mode streams via WebSocket with a 5-minute rolling buffer** — When "Live" is selected, the component subscribes to the dashboard WebSocket broadcast (F16) via `frontend/app/composables/useLiveMetrics.ts` and maintains a per-agent ring buffer of up to 150 data points (5 minutes at 2-second resolution). Data points older than 5 minutes are dropped from the buffer. The WebSocket connection is established on preset activation and closed on `onUnmounted()` or when switching to a non-Live preset. The "Live" button displays a pulsing green dot indicator (CSS `@keyframes pulse` on `.live-indicator`) while active. If the WebSocket disconnects, the composable shows a "Reconnecting..." toast (`PrimeVue Toast` with severity `warn`, life 3000) and automatically reconnects with exponential backoff (1s, 2s, 4s, max 30s). If the tab was hidden (`document.visibilityState === "hidden"`) for more than 5 minutes, the Live buffer is cleared and fresh data starts accumulating when the tab becomes visible again.

- **ACF17-4: Custom date range enforces valid boundaries and prevents future dates** — The custom date-time picker enforces: (a) start must be earlier than end; (b) end must not be later than `new Date()` (future dates are disallowed at the input level); (c) minimum range is 1 minute (shorter ranges snap to 1 minute with a toast: "Minimum range is 1 minute"); (d) maximum range is 2 years (longer ranges are capped client-side to exactly 2 years, and the backend enforces the same cap with a 422 response and code `RANGE_TOO_WIDE`). Invalid selections show an inline validation error below the picker with one of: "Start date must be before end date", "End date cannot be in the future", or "Minimum range is 1 minute". The Apply button is disabled while the selection is invalid. The date inputs use PrimeVue `DatePicker` with `showTime` and `hourFormat="24"` and `appendTo="body"` when used inside modals.

- **ACF17-5: Backend routes historical queries to the correct aggregate table** — The `GET /api/metrics/{agent_id}` endpoint accepts query parameters `since` (ISO 8601, required), `until` (ISO 8601, required), and `bucket` (`"2s"`, `"1m"`, `"5m"`, `"1d"`). The `backend/app/services/metric_query_service.py` computes the range width and selects the source table: `agent_metrics` (raw) when end - start ≤ 1 hour, `metric_aggregates_1m` when 1 hour < end - start ≤ 30 days, `metric_aggregates_5m` when end - start > 30 days. Each data point in the response is a JSON:API resource object with fields `ts`, `avg`, `min`, `max`, `p50`, `p95`, `p99` and any metric-specific values (`gpuUtilPct`, `vramUsedGb`, `tokPerSec`, `runningRequests`, `waitingRequests`). If no data exists for the requested range, the endpoint returns a 200 OK with an empty `data` array. The response `meta` block includes `sourceTable` (string), `dataPoints` (integer), and `bucket` (string). All queries include `workspace_id = <current_workspace>` in the WHERE clause enforced by the auth middleware (F5) — a request for an agent in a different workspace returns 403 Forbidden with code `WORKSPACE_MISMATCH`.

- **ACF17-6: Resolution auto-adjusts to prevent excessive data points** — When a preset or custom range is selected, the component automatically calculates the display resolution so no chart receives more than 1000 data points:

| Range | Display Resolution | Max Points |
|-------|-------------------|------------|
| ≤ 5 minutes | 2s | 150 |
| ≤ 1 hour | 1m | 60 |
| ≤ 12 hours | 5m | 144 |
| ≤ 3 days | 1h | 72 |
| ≤ 1 month | 6h | 120 |
| ≤ 1 year | 1d | 365 |
| ≤ 2 years | 1d | 730 |

The backend enforces the same constraint server-side: if the requested `bucket` would produce more than 2000 rows, the backend returns a 422 Unprocessable Entity with code `RESOLUTION_TOO_FINE`, a suggested coarser bucket, and `maxDataPoints: 2000` in the `meta` block:

```json
{
  "errors": [{
    "status": "422",
    "code": "RESOLUTION_TOO_FINE",
    "title": "Resolution too fine for requested range",
    "detail": "Bucket '2s' would produce 43200 data points for a 24-hour range. Maximum is 2000. Use bucket '5m' or coarser.",
    "meta": { "suggestedBucket": "5m", "maxDataPoints": 2000 }
  }]
}
```

The frontend catches this error and automatically retries with the coarsened bucket, notifying the user via a brief toast: "Data resolution adjusted for performance" (severity `info`, life 2000).

- **ACF17-7: Range state persists in Pinia store across page navigation** — The selected time range is stored in `frontend/stores/timeRange.ts` with `activeRange` as reactive state. When a user navigates from the server dashboard to the usage page and back within the same session, the range selection is preserved. The store initializes to a default of `{ preset: "1h", since: (now - 1h), until: now, resolution: "1m" }` on first load. Calling `setRange(newRange)` updates the store and all watchers in dependent composables fire. The store exposes:

- **`rangeDuration`** (computed getter, in milliseconds): `new Date(until).getTime() - new Date(since).getTime()`
- **`backendBucket`** (computed getter): returns `"2s"` for ≤ 1h, `"1m"` for ≤ 30d, `"5m"` for > 30d
- **`rangeLabel`** (computed getter): human-readable label like "Last 6 hours", "Custom range"
- **`refreshToNow()`** (action): updates `until` to `new Date().toISOString()` and recalculates `since` to preserve the current duration — called automatically when a page mounts and the current range's `until` is more than 60 seconds in the past

If a user navigates to a page that supports a different set of presets (e.g., benchmark page F26 only shows Live, 5m, 15m), the page passes an optional `allowedPresets` prop to `TimeRangeSelector.vue`. If the stored preset is not in `allowedPresets`, the selector falls back to the page's default preset without modifying the global store.

## Technical Notes

### File Map

**Frontend (Nuxt 4):**

| File | Purpose |
|------|---------|
| `frontend/app/components/common/TimeRangeSelector.vue` | Reusable time range selector component. Renders `<Button>` preset group in a horizontal bar + custom date-time picker overlay (PrimeVue `DatePicker` in range mode). Emits `range-change`. Handles Live mode indicator animation. Uses `useTimeRangeStore` internally. |
| `frontend/stores/timeRange.ts` | Pinia store. State: `activeRange: { preset, since, until, resolution }`, `isLive: boolean`. Actions: `setRange()`, `refreshToNow()`. Getters: `rangeDuration`, `backendBucket`, `rangeLabel`. |
| `frontend/app/composables/useTimeRange.ts` | Wraps the Pinia store, provides `range` (computed ref), `setRange()`, `isCustom`. Used by page components for reactive range watching. |
| `frontend/app/composables/useMetrics.ts` | Watches `useTimeRangeStore().activeRange`, debounces 150ms, calls `GET /api/metrics/{agentId}` with `since`, `until`, `bucket`. Returns `ref<MetricDataPoint[]>` that chart uPlot instances consume via `chart.setData()`. |
| `frontend/app/composables/useLiveMetrics.ts` | Live mode composable. Manages WebSocket connection to F16, per-agent ring buffer (150 entries), exposes `getLiveData(agentId)` and `isConnected` ref. Closes WebSocket on `onUnmounted()`. Batches incoming messages over 500ms. Handles exponential backoff reconnection. |

**Backend (FastAPI):**

| File | Purpose |
|------|---------|
| `backend/app/api/metrics.py` | Route handler for `GET /api/metrics/{agent_id}`. Accepts `since`, `until`, `bucket`. Validates UUID, parses ISO 8601, delegates to query service, serializes JSON:API response. |
| `backend/app/services/metric_query_service.py` | Table routing `resolve_metric_table(range_width)`, query builder `build_metric_query(agent_id, since, until, bucket, table)`, bucket validator `validate_bucket(range_width, bucket)` with auto-coarsen logic. |
| `backend/app/schemas/metrics.py` | Pydantic schemas: `MetricQueryParams` (since, until, bucket with validators), `MetricDataPointResponse`, `MetricCollectionResponse` (JSON:API wrapper). |

### Resolution Mapping Table

| Range | Display Resolution | Backend Bucket | Source Table |
|-------|-------------------|----------------|--------------|
| Live (5 min) | 2s | `"2s"` | `agent_metrics` (raw) |
| 5 min | 2s | `"2s"` | `agent_metrics` |
| 15 min | 1m | `"1m"` | `metric_aggregates_1m` |
| 1h | 1m | `"1m"` | `metric_aggregates_1m` |
| 6h | 5m | `"5m"` | `metric_aggregates_5m` |
| 12h | 5m | `"5m"` | `metric_aggregates_5m` |
| 1d | 1h | `"5m"` | `metric_aggregates_5m` |
| 3d | 1h | `"5m"` | `metric_aggregates_5m` |
| 1w | 6h | `"5m"` | `metric_aggregates_5m` |
| 1mo | 6h | `"5m"` | `metric_aggregates_5m` |
| 3mo | 1d | `"5m"` / `"1d"` | `metric_aggregates_5m` |
| 6mo | 1d | `"1d"` | `metric_aggregates_5m` |
| 1y | 1d | `"1d"` | `metric_aggregates_5m` |
| Custom | Auto (≤ 1000 pts) | Auto | Selected by range |

### API Contract: `GET /api/metrics/{agent_id}`

```http
GET /api/metrics/a1b2c3d4-e5f6-7890-abcd-ef1234567890?since=2026-06-07T12:00:00.000Z&until=2026-06-07T13:00:00.000Z&bucket=1m
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

Response (JSON:API):
```json
{
  "data": [
    {
      "type": "metricDataPoints",
      "id": "2026-06-07T12:00:00.000Z",
      "attributes": {
        "ts": "2026-06-07T12:00:00.000Z",
        "avg": 87.2,
        "min": 45.1,
        "max": 98.3,
        "p50": 88.0,
        "p95": 96.7,
        "p99": 98.0,
        "gpuUtilPct": 87.2,
        "vramUsedGb": 42.5,
        "tokPerSec": 185.3,
        "runningRequests": 3,
        "waitingRequests": 2
      }
    }
  ],
  "meta": {
    "sourceTable": "metric_aggregates_1m",
    "dataPoints": 60,
    "bucket": "1m"
  }
}
```

Error response (resolution too fine):
```json
{
  "errors": [
    {
      "status": "422",
      "code": "RESOLUTION_TOO_FINE",
      "title": "Resolution too fine for requested range",
      "detail": "Bucket '2s' would produce 43200 data points for a 24-hour range. Maximum is 2000. Use bucket '5m' or coarser.",
      "meta": {
        "suggestedBucket": "5m",
        "maxDataPoints": 2000
      }
    }
  ]
}
```

### Backend Query Logic

```python
# backend/app/services/metric_query_service.py

RANGE_TABLE_MAP = [
    (timedelta(hours=1),  "agent_metrics"),
    (timedelta(days=30),  "metric_aggregates_1m"),
    (timedelta(days=365), "metric_aggregates_5m"),
]

BUCKET_MAX_POINTS = {
    "2s": 150,
    "1m": 60,
    "5m": 144,
    "1h": 72,
    "6h": 120,
    "1d": 730,
}

def resolve_metric_table(range_width: timedelta) -> str:
    for max_duration, table in RANGE_TABLE_MAP:
        if range_width <= max_duration:
            return table
    return "metric_aggregates_5m"

def validate_bucket(range_width: timedelta, bucket: str) -> str:
    """Auto-coarsen bucket if it would exceed max data points."""
    total_points = range_width.total_seconds() / parse_bucket_seconds(bucket)
    max_points = BUCKET_MAX_POINTS.get(bucket, 2000)
    if total_points > max_points:
        raise ResolutionTooFineError(
            suggested_bucket=find_coarser_bucket(range_width)
        )
    return bucket
```

### Edge Cases

- **No data for range:** The backend returns 200 OK with an empty `data` array. Charts render an empty state with the message "No data available for this time range." uPlot receives an empty array and draws a horizontal dashed line at y=0 with a "No data" annotation overlay.
- **Time zone mismatch:** All timestamps are stored and queried in UTC. The date-time picker displays UTC times with a "(UTC)" label. Future F32 workspace settings may add per-workspace timezone display.
- **Browser tab backgrounded:** The WebSocket Live mode detects `document.visibilityState === "hidden"` and pauses chart re-renders (skips `requestAnimationFrame` updates) to save CPU. When the tab becomes visible again, the ring buffer catches up by replaying accumulated messages at the normal 500ms batch interval. If the tab was hidden for more than 5 minutes, the Live buffer is cleared and fresh data starts accumulating.
- **Rapid preset switching:** Range changes are debounced at 150ms in `useMetrics.ts` to avoid firing multiple API calls when a user clicks through presets quickly. Only the final selection triggers a fetch.
- **Date-time picker in modal dialogs:** When `TimeRangeSelector.vue` is used inside a PrimeVue `Dialog` or overlay panel, the date-time picker overlay must have `appendTo="body"` to avoid z-index clipping (a common PrimeVue issue with nested overlays).
- **Workspace scope:** All metric queries include `workspace_id = <current_workspace>` in the WHERE clause enforced by the auth middleware (F5) and the query service layer. A request for an agent in a different workspace returns 403 Forbidden with code `WORKSPACE_MISMATCH`, not an empty data set.
- **Backend retention horizon:** F10's retention cleanup drops raw `agent_metrics` after 24 hours, `metric_aggregates_1m` after 30 days, and `metric_aggregates_5m` after 365 days. If the frontend requests a range beyond the retention horizon, the backend returns an empty data array (not an error). The frontend displays "Data for this time range has been archived or is no longer available."

### Integration Points

- **F10 (Backend metric ingestion):** Provides the `agent_metrics`, `metric_aggregates_1m`, and `metric_aggregates_5m` tables that F17 queries. F10's downsampling pipeline determines how far back each table has data. The `resolve_metric_table()` function and `validate_bucket()` function in `metric_query_service.py` are the read-side counterparts to F10's write pipeline.
- **F14 (GPU server overview page):** Uses `TimeRangeSelector.vue` to control the time window for aggregate sparklines and utilization cards. Live mode surfaces as a real-time row of updating sparklines across all agents.
- **F15 (Single GPU server dashboard):** The primary consumer of F17. Every chart on the dashboard — GPU utilization, VRAM, throughput, requests, TTFT, KV cache, cost — watches the active range and updates on change. The dashboard layout reserves a sticky top-bar slot (position `sticky`, `z-index: 10`) for the time range selector.
- **F16 (WebSocket broadcast):** Powers the Live mode real-time data stream. `useLiveMetrics.ts` opens a WebSocket to `/ws/workspaces/{workspace_id}` and subscribes to type `metrics` messages. F16's 500ms client-side batching aligns with F17's 500ms ring buffer flush interval.
- **F26 (Benchmark comparison):** Benchmark charts showing metric time-series (e.g., TTFT over a benchmark run) consume `TimeRangeSelector.vue`. Benchmark runs are typically short (minutes), so Live and 5m/15m presets are most relevant. The page passes `allowedPresets` to restrict available options.
- **F29 (Usage tracking):** The usage page uses the time range selector for daily/weekly/monthly token usage and cost charts. The `group` parameter maps to the selected `bucket` ("1d" for day grouping, "1h" for hour grouping on short ranges).
- **F32 (Workspace settings):** Future per-workspace timezone configuration may affect how the custom date-time picker displays times. For MVP, all times are UTC with a "(UTC)" label.

### State Management

```typescript
// frontend/stores/timeRange.ts
export const useTimeRangeStore = defineStore('timeRange', () => {
  const activeRange = ref<TimeRange>({
    preset: '1h',
    since: subHours(new Date(), 1).toISOString(),
    until: new Date().toISOString(),
    resolution: '1m',
  });

  const isLive = computed(() => activeRange.value.preset === 'live');

  const rangeDuration = computed(() =>
    new Date(activeRange.value.until).getTime()
    - new Date(activeRange.value.since).getTime()
  );

  const backendBucket = computed(() => {
    const ms = rangeDuration.value;
    if (ms <= 3_600_000) return '2s';    // ≤ 1h
    if (ms <= 2_592_000_000) return '1m'; // ≤ 30d
    return '5m';                           // > 30d
  });

  const rangeLabel = computed(() => {
    const labels: Record<string, string> = {
      live: 'Live', '5m': 'Last 5 minutes', '15m': 'Last 15 minutes',
      '1h': 'Last 1 hour', '6h': 'Last 6 hours', '12h': 'Last 12 hours',
      '1d': 'Last 1 day', '3d': 'Last 3 days', '1w': 'Last 1 week',
      '1mo': 'Last 1 month', '3mo': 'Last 3 months', '6mo': 'Last 6 months',
      '1y': 'Last 1 year',
    };
    if (activeRange.value.preset === 'custom') {
      return `${formatDate(activeRange.value.since)} – ${formatDate(activeRange.value.until)}`;
    }
    return labels[activeRange.value.preset] ?? 'Custom';
  });

  function setRange(range: TimeRange) {
    activeRange.value = range;
  }

  function refreshToNow() {
    const dur = rangeDuration.value;
    activeRange.value.until = new Date().toISOString();
    activeRange.value.since = new Date(Date.now() - dur).toISOString();
  }

  return { activeRange, isLive, rangeDuration, backendBucket, rangeLabel, setRange, refreshToNow };
});
```

### Testing Notes

- **Unit tests** (`frontend/app/__tests__/stores/timeRange.spec.ts`): Verify store initialization, `setRange()`, `refreshToNow()`, computed getters for each preset, and that `backendBucket` returns the correct value for each range width boundary.
- **Component tests** (`frontend/app/__tests__/components/TimeRangeSelector.spec.ts`): Verify that clicking each preset button emits the correct `range-change` payload. Verify that custom date inputs validate boundaries. Verify that the "Live" button shows the pulsing dot and switches to WebSocket mode.
- **Backend integration tests** (`backend/tests/api/test_metrics.py`): Verify `GET /api/metrics/{agent_id}` with valid and invalid agent UUIDs, timestamps, and bucket values. Verify table routing for each boundary (59 min → raw, 61 min → 1m agg, 31 days → 5m agg). Verify 422 `RESOLUTION_TOO_FINE` response. Verify empty response for out-of-range queries. Verify 403 `WORKSPACE_MISMATCH` for cross-workspace requests.
- **Performance tests:** Measure query latency for the most expensive preset (1y, daily bucket, 5m aggregate table) against a dataset of 10 agents with 365 days of data. Latency must be under 500 ms. The test fixture seeds `metric_aggregates_5m` with 105,120 rows (10 agents × 365 days × 28.8 rows/day at 5-minute resolution).

## Depends on: F10
