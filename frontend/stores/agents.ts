import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface Agent {
  id: string
  name: string
  status: 'online' | 'offline' | 'degraded'
  hostname: string
  agentVersion: string
  gpuCount: number
  gpuModel: string
  gpuMemoryTotalMb: number
  gpuMemoryUsedMb: number
  gpuUtilAvgPct: number
  cpuCores: number
  ramTotalGb: number
  ramUsedGb: number
  diskTotalGb: number
  diskUsedGb: number
  runningModels: number
  uptimeSeconds: number
  lastSeenAt: string
  createdAt: string
}

export interface AgentMeta {
  total: number
  online: number
  offline: number
  totalGpuCount: number
  totalGpuVramGb: number
  totalRunningModels: number
}

export interface MetricDelta {
  agentId: string
  ts: string
  gpuUtilAvgPct?: number
  gpuMemoryUsedMb?: number
  runningModels?: number
  ramUsedGb?: number
  diskUsedGb?: number
}

export const useAgentsStore = defineStore('agents', () => {
  // State
  const agents = ref<Map<string, Agent>>(new Map())
  const meta = ref<AgentMeta>({
    total: 0,
    online: 0,
    offline: 0,
    totalGpuCount: 0,
    totalGpuVramGb: 0,
    totalRunningModels: 0,
  })
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const agentList = computed<Agent[]>(() => Array.from(agents.value.values()))

  const onlineAgents = computed(() =>
    agentList.value.filter(a => a.status === 'online')
  )

  const offlineAgents = computed(() =>
    agentList.value.filter(a => a.status === 'offline')
  )

  const degradedAgents = computed(() =>
    agentList.value.filter(a => a.status === 'degraded')
  )

  const aggregateGpuUtil = computed(() => {
    const list = agentList.value
    if (list.length === 0) return 0
    return list.reduce((sum, a) => sum + (a.gpuUtilAvgPct ?? 0), 0) / list.length
  })

  const aggregateVramGb = computed(() => {
    const list = agentList.value
    return {
      used: list.reduce((sum, a) => sum + (a.gpuMemoryUsedMb ?? 0), 0) / 1024,
      total: list.reduce((sum, a) => sum + (a.gpuMemoryTotalMb ?? 0), 0) / 1024,
    }
  })

  // Actions
  function setAgents(agentArray: Agent[], newMeta?: Partial<AgentMeta>) {
    const map = new Map<string, Agent>()
    for (const agent of agentArray) {
      map.set(agent.id, agent)
    }
    agents.value = map
    if (newMeta) {
      meta.value = { ...meta.value, ...newMeta }
    }
    loading.value = false
    error.value = null
  }

  function updateAgent(id: string, updates: Partial<Agent>) {
    const existing = agents.value.get(id)
    if (existing) {
      agents.value.set(id, { ...existing, ...updates })
      // Force reactivity by replacing the map
      agents.value = new Map(agents.value)
    }
  }

  function applyMetricDelta(delta: MetricDelta) {
    const agent = agents.value.get(delta.agentId)
    if (!agent) return

    const updates: Partial<Agent> = {}

    if (delta.gpuUtilAvgPct !== undefined) {
      updates.gpuUtilAvgPct = delta.gpuUtilAvgPct
    }
    if (delta.gpuMemoryUsedMb !== undefined) {
      updates.gpuMemoryUsedMb = delta.gpuMemoryUsedMb
    }
    if (delta.runningModels !== undefined) {
      updates.runningModels = delta.runningModels
    }
    if (delta.ramUsedGb !== undefined) {
      updates.ramUsedGb = delta.ramUsedGb
    }
    if (delta.diskUsedGb !== undefined) {
      updates.diskUsedGb = delta.diskUsedGb
    }

    // Compute status from metrics
    const gpuUtil = updates.gpuUtilAvgPct ?? agent.gpuUtilAvgPct
    const freeVram = (updates.gpuMemoryTotalMb ?? agent.gpuMemoryTotalMb) -
      (updates.gpuMemoryUsedMb ?? agent.gpuMemoryUsedMb)

    if (gpuUtil >= 95 || (freeVram > 0 && freeVram < 5120)) {
      updates.status = 'degraded'
    } else {
      updates.status = 'online'
    }

    updates.lastSeenAt = delta.ts

    agents.value.set(delta.agentId, { ...agent, ...updates })
    // Force reactivity
    agents.value = new Map(agents.value)
  }

  function updateAgentStatus(
    agentId: string,
    status: Agent['status'],
    ts: string,
  ) {
    const agent = agents.value.get(agentId)
    if (agent) {
      agents.value.set(agentId, {
        ...agent,
        status,
        lastSeenAt: ts,
      })
      agents.value = new Map(agents.value)
    }
  }

  function removeAgent(agentId: string) {
    agents.value.delete(agentId)
    agents.value = new Map(agents.value)
  }

  function setLoading(val: boolean) {
    loading.value = val
  }

  function setError(err: string | null) {
    error.value = err
    loading.value = false
  }

  return {
    // State
    agents,
    meta,
    loading,
    error,
    // Getters
    agentList,
    onlineAgents,
    offlineAgents,
    degradedAgents,
    aggregateGpuUtil,
    aggregateVramGb,
    // Actions
    setAgents,
    updateAgent,
    applyMetricDelta,
    updateAgentStatus,
    removeAgent,
    setLoading,
    setError,
  }
})
