// ============================================
// ModelPrism Dashboard — Shared Type Definitions
// All components use these interfaces for their props.
// No component should define its own inline types.
// ============================================

/** GPU and system metric snapshot from WebSocket */
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

/** vLLM-specific inference metrics */
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

/** Log entry from agent log streaming */
export interface LogEntry {
  ts: string
  level: 'debug' | 'info' | 'warning' | 'error'
  module: string
  message: string
  stackTrace?: string
}

/** A single data point for chart series */
export interface MetricPoint {
  ts: string
  gpuUtilAvgPct: number
  gpuMemoryUsedMb: number
  ramUsedGb: number
  cpuPct: number
  running: number
  waiting: number
}

/** Severity level for metric threshold coloring */
export type SeverityLevel = 'info' | 'success' | 'warn' | 'danger' | 'secondary'

/** Trend direction indicator */
export type TrendDirection = 'up' | 'down' | 'stable'

/** Agent connection status */
export type ConnectionStatus = 'online' | 'offline' | 'connecting' | 'degraded'

/** Running model summary */
export interface ModelInfo {
  name: string
  status: string
  tps?: number
  uptime?: string
}

/** GPU utilization bar color thresholds */
export const GPU_THRESHOLDS = {
  GREEN_MAX: 70,
  AMBER_MAX: 95,
} as const
