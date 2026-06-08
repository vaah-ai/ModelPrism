// ============================================
// ModelPrism Dashboard — Pure Utility Functions
// No component or store dependencies.
// Import from ~/utils/dashboard anywhere.
// ============================================

import type { SeverityLevel, ConnectionStatus } from '~/types/dashboard'

/**
 * Convert MB to GB with 1 decimal place.
 */
export function formatGb(mb: number): string {
  return (mb / 1024).toFixed(1)
}

/**
 * Auto-scale byte formatting (B, KB, MB, GB, TB).
 */
export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`
}

/**
 * Format milliseconds to a human-readable string.
 */
export function formatMs(ms: number): string {
  if (ms < 1) return '<1ms'
  if (ms < 1000) return `${Math.round(ms)}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`
}

/**
 * Convert an ISO 8601 timestamp to a human-readable relative time string.
 * Examples: "5s ago", "3m ago", "2h ago", "4d ago"
 */
export function timeAgo(isoString: string): string {
  if (!isoString) return 'N/A'
  const seconds = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000)
  if (seconds < 0) return 'just now'
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return `${Math.floor(seconds / 86400)}d ago`
}

/**
 * Map a log level to a CSS color value.
 */
export function getSeverityColor(level: string): string {
  switch (level) {
    case 'error':
      return 'var(--danger)'
    case 'warning':
      return 'var(--warning)'
    case 'info':
      return 'var(--info)'
    case 'debug':
      return 'var(--text-muted)'
    default:
      return 'var(--text-secondary)'
  }
}

/**
 * Return a color for VRAM usage percentage.
 * Green < 70%, Amber 70-94%, Red >= 95%.
 */
export function getVramColor(pct: number): string {
  if (pct >= 95) return 'var(--danger)'
  if (pct >= 70) return 'var(--warning)'
  return 'var(--success)'
}

/**
 * Return a SeverityLevel for GPU utilization percentage.
 */
export function getGpuUtilSeverity(pct: number): SeverityLevel {
  if (pct >= 95) return 'danger'
  if (pct >= 70) return 'warn'
  return 'success'
}

/**
 * Map a ConnectionStatus to a PrimeVue severity string.
 */
export function getStatusSeverity(status: ConnectionStatus): 'success' | 'warn' | 'secondary' | 'info' | 'danger' {
  switch (status) {
    case 'online':
      return 'success'
    case 'degraded':
      return 'warn'
    case 'connecting':
      return 'info'
    case 'offline':
      return 'secondary'
    default:
      return 'info'
  }
}
