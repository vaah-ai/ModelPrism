# Dashboard Components

> Created during M1-T9 — Dashboard Pages

## Common Components (`app/components/common/`)

### MetricCard
Reusable metric display card with label, value, unit, trend direction, and severity color.

**Props:**
- `label: string` — Metric name
- `value: string | number` — Current value (auto-formats large numbers)
- `unit?: string` — Optional unit suffix (e.g., "GB", "tok/s")
- `trend?: 'up' | 'down' | 'stable'` — Direction indicator with arrow
- `severity?: 'info' | 'success' | 'warn' | 'danger' | 'secondary'` — Left border color

### StatusBadge
Color-coded connection status badge using PrimeVue Tag.

**Props:**
- `status: 'online' | 'offline' | 'connecting' | 'degraded'` — Agent connection status
- Shows pulsing green dot for online, yellow pulse for connecting

### GpuBar
Reusable GPU utilization progress bar with color thresholds.

**Props:**
- `value: number` — Utilization percentage (0-100)
- `label?: string` — Optional label text
- `showValue?: boolean` — Show percentage text (default: true)
- `barHeight?: number` — Bar height in px (default: 6)
- Color thresholds: <70% green, 70-94% amber, >=95% red

## Dashboard Components (`app/components/dashboard/`)

### SystemResources
System resource panel showing GPU, VRAM, RAM, CPU, and Disk usage bars. Uses GpuBar and PrimeVue ProgressBar.

**Props:**
- `metrics: MetricSnapshot | null` — Full system metric snapshot

### QueueDiagnostics
vLLM queue and diagnostic metrics panel.

**Props:**
- `vllmMetrics: VllmMetrics | null` — vLLM-specific metrics including running/waiting, KV cache, TTFT, error/truncation rates
- Computes and displays bottleneck indicator

### ModelList
Running model cards with status tags.

**Props:**
- `models: ModelInfo[]` — Array of running models

### GpuMetricsChart
Real-time chart component using uPlot. Initializes once on mount, updates via `setData()`.

**Props:**
- `metricsHistory: MetricPoint[]` — Array of data points (latest last)
- `chartType: 'gpuUtil' | 'vram' | 'throughput' | 'requests'` — Chart configuration
- `height?: number` — Chart height (default: 256px)
- `title?: string` — Chart title override

**Key behaviors:**
- uPlot initialized in `onMounted`, destroyed in `onUnmounted`
- `watch(metricsHistory)` calls `chart.setData()` — no re-mount
- ResizeObserver updates `chart.setSize()` on container resize
- 150-point window (5 minutes at 2s intervals)
- Empty state: "Awaiting data..." when no metrics

### LiveLog
Streaming log viewer with level filtering, search, and auto-scroll.

**Props:**
- `logs: LogEntry[]` — Array of log entries
- `loading?: boolean` — Show loading state
- `maxLogs?: number` — Max entries before FIFO trim (default: 500)
- `filterable?: boolean` — Show level filter buttons (default: true)
- `searchable?: boolean` — Show search input (default: true)
- `height?: string` — Container height (default: '320px')
- `levels?: LogEntry['level'][]` — Available level filters

**Events:**
- `update:logs` — Emitted when logs are trimmed (for sync with parent)

## Shared Types

All TypeScript interfaces live in `~/types/dashboard.ts`:
- `MetricSnapshot`, `VllmMetrics`, `LogEntry`, `MetricPoint`
- `SeverityLevel`, `TrendDirection`, `ConnectionStatus`
- `ModelInfo`

## Utility Functions

Pure functions in `~/utils/dashboard.ts`:
- `formatGb(mb)`, `formatBytes(bytes)`, `formatMs(ms)`
- `timeAgo(isoString)`, `getSeverityColor(level)`
- `getVramColor(pct)`, `getGpuUtilSeverity(pct)`, `getStatusSeverity(status)`
