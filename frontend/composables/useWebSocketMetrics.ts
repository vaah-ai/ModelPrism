import { ref, onUnmounted, type Ref } from 'vue'
import { useAgentsStore, type MetricDelta } from '~/stores/agents'
import { useMetricsStore, type MetricPoint } from '~/stores/metrics'

export type WsConnectionState = 'disconnected' | 'connecting' | 'connected' | 'reconnecting'

export interface DashboardWsMessage {
  type: string
  agent_id?: string
  ts?: string
  [key: string]: unknown
}

export interface UseWebSocketMetricsReturn {
  connectionState: Ref<WsConnectionState>
  connect: () => void
  disconnect: () => void
  send: (msg: Record<string, unknown>) => void
  isConnected: Ref<boolean>
}

/**
 * WebSocket composable for connecting to the backend's dashboard broadcast endpoint.
 *
 * - Connects to `ws://<backendUrl>/ws/dashboard` (or `/ws/dashboard/{agentId}` for per-agent)
 * - Buffers incoming metrics for 500ms and batch-updates Pinia stores
 * - Auto-reconnects with 3-second delay on disconnect
 * - Tracks connection state reactively
 */
export function useWebSocketMetrics(agentId?: string): UseWebSocketMetricsReturn {
  const config = useRuntimeConfig()
  const backendUrl = config.public.backendUrl as string
  const wsBaseUrl = backendUrl.replace(/^http/, 'ws')
  const wsPath = agentId
    ? `${wsBaseUrl}/ws/dashboard/${agentId}`
    : `${wsBaseUrl}/ws/dashboard`

  const ws = ref<WebSocket | null>(null)
  const connectionState = ref<WsConnectionState>('disconnected')
  const isConnected = ref(false)

  let messageBuffer: DashboardWsMessage[] = []
  let flushTimer: ReturnType<typeof setTimeout> | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let reconnectAttempts = 0
  const MAX_RECONNECT_DELAY = 30000
  const BASE_RECONNECT_DELAY = 3000
  const FLUSH_INTERVAL_MS = 500

  function startFlushTimer() {
    if (flushTimer) return
    flushTimer = setInterval(() => {
      flushBuffer()
    }, FLUSH_INTERVAL_MS)
  }

  function stopFlushTimer() {
    if (flushTimer) {
      clearInterval(flushTimer)
      flushTimer = null
    }
  }

  function flushBuffer() {
    if (messageBuffer.length === 0) return

    const batch = messageBuffer.splice(0, messageBuffer.length)
    const agentsStore = useAgentsStore()
    const metricsStore = useMetricsStore()

    for (const msg of batch) {
      const agentId = msg.agent_id
      if (!agentId) continue

      switch (msg.type) {
        case 'metrics': {
          // Update agent store with metric delta
          const delta: MetricDelta = {
            agentId,
            ts: msg.ts as string || new Date().toISOString(),
            gpuUtilAvgPct: msg.gpu_util_avg_pct as number | undefined,
            gpuMemoryUsedMb: msg.gpu_memory_used_mb as number | undefined,
            runningModels: msg.running_models as number | undefined,
            ramUsedGb: msg.ram_used_gb as number | undefined,
            diskUsedGb: msg.disk_used_gb as number | undefined,
          }
          agentsStore.applyMetricDelta(delta)

          // Add to metric buffer for charts
          if (msg.ts && msg.gpu_util_avg_pct !== undefined) {
            const point: MetricPoint = {
              ts: msg.ts as string,
              gpuUtilAvgPct: (msg.gpu_util_avg_pct as number) ?? 0,
              gpuMemoryUsedMb: (msg.gpu_memory_used_mb as number) ?? 0,
              ramUsedGb: (msg.ram_used_gb as number) ?? 0,
              cpuPct: (msg.cpu_pct as number) ?? 0,
              running: (msg.running as number) ?? 0,
              waiting: (msg.waiting as number) ?? 0,
            }
            metricsStore.pushMetric(agentId, point)
          }
          break
        }

        case 'agent_status': {
          agentsStore.updateAgentStatus(
            agentId,
            msg.status as 'online' | 'offline' | 'degraded',
            msg.ts as string || new Date().toISOString(),
          )
          break
        }

        case 'agent_update': {
          const changes = msg.changes as Record<string, unknown> | undefined
          if (changes) {
            agentsStore.updateAgent(agentId, changes as any)
          }
          break
        }

        default:
          // Unknown message types are silently dropped
          break
      }
    }
  }

  function connect() {
    if (ws.value?.readyState === WebSocket.OPEN) return

    connectionState.value = reconnectAttempts > 0 ? 'reconnecting' : 'connecting'

    const socket = new WebSocket(wsPath)

    socket.onopen = () => {
      connectionState.value = 'connected'
      isConnected.value = true
      reconnectAttempts = 0
      startFlushTimer()
    }

    socket.onmessage = (event: MessageEvent) => {
      try {
        const msg: DashboardWsMessage = JSON.parse(event.data)

        // Handle replay_batch — process entries immediately
        if (msg.type === 'replay_batch') {
          const entries = msg.entries as DashboardWsMessage[] | undefined
          if (entries) {
            // Push to buffer for processing
            messageBuffer.push(...entries)
          }
          return
        }

        // Handle shutdown notice
        if (msg.type === 'shutdown_notice') {
          const delayMs = (msg.reconnect_delay_ms as number) || 2000
          ws.value?.close(1001, 'Server shutting down')
          scheduleReconnect(delayMs)
          return
        }

        // Handle pong
        if (msg.type === 'pong') {
          return
        }

        // Buffer all other messages
        messageBuffer.push(msg)
      } catch {
        // Silently drop malformed messages
      }
    }

    socket.onclose = () => {
      connectionState.value = 'disconnected'
      isConnected.value = false
      ws.value = null
      stopFlushTimer()

      // Flush any remaining buffered messages
      flushBuffer()

      if (reconnectAttempts < 10) {
        scheduleReconnect()
      }
    }

    socket.onerror = () => {
      socket.close()
    }

    ws.value = socket
  }

  function scheduleReconnect(delay?: number) {
    const actualDelay = delay ?? Math.min(
      BASE_RECONNECT_DELAY * Math.pow(1.5, reconnectAttempts),
      MAX_RECONNECT_DELAY,
    )
    reconnectAttempts++

    if (reconnectTimer) clearTimeout(reconnectTimer)
    reconnectTimer = setTimeout(() => {
      connect()
    }, actualDelay)
  }

  function disconnect() {
    stopFlushTimer()
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    ws.value?.close(1000, 'Client disconnect')
    ws.value = null
    connectionState.value = 'disconnected'
    isConnected.value = false
    reconnectAttempts = 0
  }

  function send(msg: Record<string, unknown>) {
    if (ws.value?.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify(msg))
    }
  }

  // Clean up on component unmount
  onUnmounted(() => {
    disconnect()
  })

  return {
    connectionState,
    connect,
    disconnect,
    send,
    isConnected,
  }
}
