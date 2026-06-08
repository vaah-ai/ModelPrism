import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { MetricPoint } from '~~/app/types/dashboard'

export interface MetricBuffer {
  agentId: string
  points: MetricPoint[]
  maxLength: number
}

export const useMetricsStore = defineStore('metrics', () => {
  // State: metric buffers keyed by agentId
  const buffers = ref<Map<string, MetricBuffer>>(new Map())
  const DEFAULT_BUFFER_SIZE = 300 // 10 minutes at 2s intervals

  // Getters
  function getBuffer(agentId: string): MetricBuffer | undefined {
    return buffers.value.get(agentId)
  }

  const allAgentIds = computed(() => Array.from(buffers.value.keys()))

  // Actions
  function initBuffer(agentId: string, maxLength = DEFAULT_BUFFER_SIZE) {
    if (!buffers.value.has(agentId)) {
      buffers.value.set(agentId, {
        agentId,
        points: [],
        maxLength,
      })
      buffers.value = new Map(buffers.value)
    }
  }

  function pushMetric(agentId: string, point: MetricPoint) {
    let buffer = buffers.value.get(agentId)
    if (!buffer) {
      buffer = {
        agentId,
        points: [],
        maxLength: DEFAULT_BUFFER_SIZE,
      }
      buffers.value.set(agentId, buffer)
    }

    buffer.points.push(point)

    // Trim to max length
    if (buffer.points.length > buffer.maxLength) {
      buffer.points = buffer.points.slice(-buffer.maxLength)
    }

    // Force reactivity
    buffers.value = new Map(buffers.value)
  }

  function pushMetricsBatch(agentId: string, points: MetricPoint[]) {
    let buffer = buffers.value.get(agentId)
    if (!buffer) {
      buffer = {
        agentId,
        points: [],
        maxLength: DEFAULT_BUFFER_SIZE,
      }
      buffers.value.set(agentId, buffer)
    }

    buffer.points.push(...points)

    // Trim to max length
    if (buffer.points.length > buffer.maxLength) {
      buffer.points = buffer.points.slice(-buffer.maxLength)
    }

    buffers.value = new Map(buffers.value)
  }

  function clearBuffer(agentId: string) {
    buffers.value.delete(agentId)
    buffers.value = new Map(buffers.value)
  }

  function clearAllBuffers() {
    buffers.value = new Map()
  }

  return {
    buffers,
    allAgentIds,
    getBuffer,
    initBuffer,
    pushMetric,
    pushMetricsBatch,
    clearBuffer,
    clearAllBuffers,
  }
})
