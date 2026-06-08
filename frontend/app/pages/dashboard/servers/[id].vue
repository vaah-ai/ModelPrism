<template>
  <div>
    <!-- Loading skeleton -->
    <div v-if="loadingState === 'loading'" class="space-y-6">
      <div class="card-base p-6">
        <div class="flex items-center gap-4">
          <Skeleton shape="circle" size="3rem" />
          <div class="space-y-2">
            <Skeleton width="200px" height="24px" />
            <Skeleton width="140px" height="14px" />
          </div>
        </div>
      </div>
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div v-for="i in 4" :key="i">
          <Skeleton height="96px" class="rounded-xl" />
        </div>
      </div>
      <div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div v-for="i in 2" :key="i">
          <Skeleton height="280px" class="rounded-xl" />
        </div>
      </div>
    </div>

    <!-- Offline/Error banner -->
    <div
      v-else-if="loadingState === 'offline' || loadingState === 'error'"
      class="flex flex-col items-center justify-center py-20"
    >
      <div
        class="mb-4 flex h-14 w-14 items-center justify-center rounded-full"
        :style="{
          backgroundColor: loadingState === 'offline' ? 'rgba(161, 161, 170, 0.1)' : 'rgba(239, 68, 68, 0.1)',
        }"
      >
        <i
          :class="loadingState === 'offline' ? 'pi pi-server' : 'pi pi-exclamation-triangle'"
          class="text-xl"
          :style="{ color: loadingState === 'offline' ? 'var(--text-muted)' : 'var(--danger)' }"
        />
      </div>
      <h3 class="mb-1 text-base font-semibold" style="color: var(--text-primary);">
        {{ loadingState === 'offline' ? 'Agent Offline' : 'Could Not Load Agent' }}
      </h3>
      <p class="mb-4 text-xs" style="color: var(--text-secondary);">
        {{ errorMessage }}
      </p>
      <Button
        label="Retry"
        icon="pi pi-refresh"
        severity="secondary"
        @click="reconnect"
      />
    </div>

    <!-- Live content -->
    <div v-else>
      <!-- WebSocket state indicator -->
      <div
        v-if="wsConnectionState === 'reconnecting'"
        class="mb-3 flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs"
        :style="{
          borderColor: 'rgba(245, 158, 11, 0.3)',
          backgroundColor: 'rgba(245, 158, 11, 0.06)',
          color: 'var(--warning)',
        }"
      >
        <i class="pi pi-sync animate-spin text-xs" />
        <span>Reconnecting to live data...</span>
      </div>

      <!-- Server header -->
      <div class="card-base mb-6 p-6">
        <div class="flex items-start justify-between">
          <div>
            <div class="flex items-center gap-3">
              <StatusBadge :status="agentStatus" />
              <h1 class="text-2xl font-bold" style="color: var(--text-primary);">
                {{ agentName }}
              </h1>
            </div>
            <p class="mt-1 text-sm" style="color: var(--text-secondary);">
              {{ hostname }} · {{ gpuSummary }}
            </p>
            <p v-if="uptime" class="text-xs" style="color: var(--text-muted);">
              Uptime: {{ uptime }}
            </p>
          </div>
          <Button
            v-if="agentStatus === 'offline'"
            label="Reconnect"
            icon="pi pi-refresh"
            severity="secondary"
            size="small"
            @click="reconnect"
          />
        </div>
      </div>

      <!-- Empty metrics banner -->
      <div
        v-if="chartData.length === 0"
        class="mb-4 flex items-center gap-2 rounded-lg border px-3 py-2 text-xs"
        :style="{
          borderColor: 'rgba(6, 182, 212, 0.3)',
          backgroundColor: 'rgba(6, 182, 212, 0.06)',
          color: 'var(--text-accent)',
        }"
      >
        <i class="pi pi-chart-bar text-xs" />
        <span>Awaiting first metric data...</span>
      </div>

      <!-- Metric Cards row -->
      <div class="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="GPU Util"
          :value="`${Math.round(currentMetrics.gpuUtilAvgPct)}%`"
          :severity="gpuUtilSeverity"
          :trend="'stable'"
        />
        <MetricCard
          label="VRAM"
          :value="formatGb(currentMetrics.gpuMemoryUsedMb)"
          unit="GB"
          :severity="vramSeverity"
          :trend="'stable'"
        />
        <MetricCard
          label="Requests"
          :value="`${vllmMetrics.running} / ${vllmMetrics.waiting}`"
          unit="run/wait"
          :severity="requestsSeverity"
          :trend="'stable'"
        />
        <MetricCard
          label="Throughput"
          :value="vllmMetrics.tps.toFixed(1)"
          unit="tok/s"
          severity="info"
          :trend="'stable'"
        />
      </div>

      <!-- Charts row (2x2 grid) -->
      <div class="mb-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <GpuMetricsChart
          :metrics-history="chartData"
          chart-type="gpuUtil"
          title="GPU Utilization %"
        />
        <GpuMetricsChart
          :metrics-history="chartData"
          chart-type="vram"
          title="VRAM Usage (GB)"
        />
        <GpuMetricsChart
          :metrics-history="chartData"
          chart-type="throughput"
          title="Throughput (tok/s)"
        />
        <GpuMetricsChart
          :metrics-history="chartData"
          chart-type="requests"
          title="Requests"
        />
      </div>

      <!-- Bottom panels -->
      <div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SystemResources :metrics="currentResources" />
        <QueueDiagnostics :vllm-metrics="vllmMetrics" />
      </div>
      <div class="mt-6">
        <ModelList :models="runningModels" />
      </div>
      <div class="mt-6">
        <LiveLog
          :logs="liveLogs"
          :filterable="true"
          :searchable="true"
          :max-logs="500"
          height="360px"
          @update:logs="liveLogs = $event"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useAgentsStore, type Agent } from '~~/stores/agents'
import { useMetricsStore } from '~~/stores/metrics'
import { useWebSocketMetrics } from '~~/composables/useWebSocketMetrics'
import { useApi } from '~~/composables/useApi'
import { formatGb } from '~/utils/dashboard'
import type { MetricSnapshot, VllmMetrics, LogEntry, SeverityLevel } from '~/types/dashboard'
import type { MetricPoint } from '~/types/dashboard'

definePageMeta({
  layout: 'dashboard',
})

const route = useRoute()
const agentId = computed(() => route.params.id as string)
const agentsStore = useAgentsStore()
const metricsStore = useMetricsStore()
const api = useApi()

// State management
type LoadingState = 'loading' | 'live' | 'offline' | 'error'
const loadingState = ref<LoadingState>('loading')
const errorMessage = ref('')
const liveLogs = ref<LogEntry[]>([])

// WebSocket connection (per-agent)
const ws = useWebSocketMetrics(agentId.value)
const wsConnectionState = ws.connectionState

// Current metrics derived from store
const currentAgent = computed<Agent | null>(() => {
  return agentsStore.agents.get(agentId.value) ?? null
})

const agentName = computed(() => currentAgent.value?.name ?? 'Unknown')
const hostname = computed(() => currentAgent.value?.hostname ?? '')
const agentStatus = computed(() => currentAgent.value?.status ?? 'offline')
const gpuSummary = computed(() => {
  const a = currentAgent.value
  if (!a) return 'N/A'
  return `${a.gpuCount}× ${a.gpuModel}`
})
const uptime = computed(() => {
  const sec = currentAgent.value?.uptimeSeconds
  if (!sec) return ''
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  return `${h}h ${m}m`
})

// Metric snapshots for charts (from metrics store buffer)
const chartData = computed<MetricPoint[]>(() => {
  const buffer = metricsStore.getBuffer(agentId.value)
  return buffer?.points ?? []
})

// Current snapshot (latest metric point) for SystemResources
function makeEmptySnapshot(): MetricSnapshot {
  return {
    ts: new Date().toISOString(),
    gpuUtilAvgPct: 0,
    gpuMemoryUsedMb: 0,
    gpuMemoryTotalMb: currentAgent.value?.gpuMemoryTotalMb ?? 0,
    gpuTempC: 0, gpuPowerW: 0,
    ramUsedGb: currentAgent.value?.ramUsedGb ?? 0,
    ramTotalGb: currentAgent.value?.ramTotalGb ?? 0,
    cpuPct: 0, load1: 0, load5: 0, load15: 0,
    diskUsedGb: currentAgent.value?.diskUsedGb ?? 0,
    diskTotalGb: currentAgent.value?.diskTotalGb ?? 0,
    gpuCachePct: 0,
  }
}

const currentMetrics = computed<MetricSnapshot>(() => {
  const pts = chartData.value
  if (pts.length === 0) return makeEmptySnapshot()
  const last = pts[pts.length - 1]
  if (!last) return makeEmptySnapshot()
  return {
    ts: last.ts,
    gpuUtilAvgPct: last.gpuUtilAvgPct,
    gpuMemoryUsedMb: last.gpuMemoryUsedMb,
    gpuMemoryTotalMb: currentAgent.value?.gpuMemoryTotalMb ?? 0,
    gpuTempC: 0,
    gpuPowerW: 0,
    ramUsedGb: last.ramUsedGb,
    ramTotalGb: currentAgent.value?.ramTotalGb ?? 0,
    cpuPct: last.cpuPct,
    load1: 0, load5: 0, load15: 0,
    diskUsedGb: currentAgent.value?.diskUsedGb ?? 0,
    diskTotalGb: currentAgent.value?.diskTotalGb ?? 0,
    gpuCachePct: 0,
  }
})

const currentResources = computed<MetricSnapshot | null>(() => {
  return loadingState.value === 'live' ? currentMetrics.value : null
})

// vLLM metrics (computed from latest data)
const vllmMetrics = computed<VllmMetrics>(() => {
  const ptsArr = chartData.value
  const latest = ptsArr.length > 0 ? ptsArr[ptsArr.length - 1] : null
  return {
    running: latest?.running ?? 0,
    waiting: latest?.waiting ?? 0,
    totalRequests: 0,
    promptTokensTotal: 0,
    genTokensTotal: 0,
    ttftP50Ms: 0,
    ttftP99Ms: 0,
    gpuCachePct: 0,
    tps: 0,
    prefixCacheHitPct: 0,
    errorPct: 0,
    truncPct: 0,
  }
})

// Running models (from agent data)
const runningModels = computed(() => {
  const a = currentAgent.value
  // No model list available from backend yet — this will be populated by deployment API (M2+)
  return []
})

// Severity colors for metric cards
const gpuUtilSeverity = computed<SeverityLevel>(() => {
  const val = currentMetrics.value.gpuUtilAvgPct
  if (val >= 95) return 'danger'
  if (val >= 70) return 'warn'
  return 'success'
})

const vramSeverity = computed<SeverityLevel>(() => {
  const used = currentMetrics.value.gpuMemoryUsedMb
  const total = currentMetrics.value.gpuMemoryTotalMb
  if (!total) return 'info'
  const pct = (used / total) * 100
  if (pct >= 95) return 'danger'
  if (pct >= 70) return 'warn'
  return 'success'
})

const requestsSeverity = computed<SeverityLevel>(() => {
  if (vllmMetrics.value.waiting > vllmMetrics.value.running * 2) return 'warn'
  return 'info'
})

function reconnect() {
  loadingState.value = 'loading'
  ws.disconnect()
  ws.connect()
  // After reconnect, try fetching fresh data
  setTimeout(() => {
    loadingState.value = 'live'
  }, 1000)
}

onMounted(async () => {
  // Initialize metrics buffer for this agent
  metricsStore.initBuffer(agentId.value)

  try {
    // Fetch agent details from backend
    const response = await api.get(`/api/agents/${agentId.value}`)
    const data = (response as any)?.data
    if (data) {
      const attr = data.attributes
      const agent: Agent = {
        id: data.id,
        name: attr.name,
        status: attr.status,
        hostname: attr.hostname,
        agentVersion: attr.agent_version,
        gpuCount: attr.gpu_count,
        gpuModel: attr.gpu_model,
        gpuMemoryTotalMb: attr.gpu_memory_total_mb,
        gpuMemoryUsedMb: attr.gpu_memory_used_mb,
        gpuUtilAvgPct: attr.gpu_util_avg_pct,
        cpuCores: attr.cpu_cores,
        ramTotalGb: attr.ram_total_gb,
        ramUsedGb: attr.ram_used_gb,
        diskTotalGb: attr.disk_total_gb,
        diskUsedGb: attr.disk_used_gb,
        runningModels: attr.running_models,
        uptimeSeconds: attr.uptime_seconds,
        lastSeenAt: attr.last_seen_at,
        createdAt: attr.created_at,
      }
      agentsStore.upsertAgent(agent)
      loadingState.value = 'live'
    } else {
      loadingState.value = 'offline'
      errorMessage.value = 'Agent not found. It may have been de-registered.'
    }
  } catch {
    loadingState.value = 'offline'
    errorMessage.value = 'Could not reach the agent. It may be offline or the backend is unavailable.'
  }

  // Connect WebSocket for per-agent live updates
  ws.connect()
})

onUnmounted(() => {
  ws.disconnect()
  metricsStore.clearBuffer(agentId.value)
})
</script>
