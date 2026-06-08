<template>
  <Card>
    <template #title>
      <div class="flex items-center gap-2">
        <i class="pi pi-sort-alt text-sm" style="color: var(--accent)" />
        <span class="text-sm font-semibold" style="color: var(--text-primary)">Queue & Diagnostics</span>
      </div>
    </template>
    <template #content>
      <div v-if="!vllmMetrics" class="flex items-center justify-center py-8">
        <span class="text-xs" style="color: var(--text-muted)">Waiting for vLLM telemetry...</span>
      </div>
      <div v-else class="flex flex-col gap-4">
        <!-- Running / Waiting -->
        <div class="flex gap-3">
          <div class="metric-group flex-1">
            <span class="metric-label">Running</span>
            <span class="metric-value" style="color: var(--success)">{{ vllmMetrics.running }}</span>
          </div>
          <div class="metric-group flex-1">
            <span class="metric-label">Waiting</span>
            <span class="metric-value" style="color: var(--warning)">{{ vllmMetrics.waiting }}</span>
          </div>
        </div>

        <!-- KV Cache -->
        <div class="space-y-1">
          <div class="flex items-center justify-between">
            <span class="text-xs font-medium" style="color: var(--text-secondary)">KV Cache</span>
            <span class="text-xs font-mono" style="color: var(--text-accent)">
              {{ Math.round(vllmMetrics.gpuCachePct) }}%
            </span>
          </div>
          <ProgressBar
            :value="Math.round(vllmMetrics.gpuCachePct)"
            :pt="kvCacheBarPt"
            style="height: 6px"
          />
        </div>

        <!-- TTFT -->
        <div class="space-y-2">
          <span class="text-xs font-medium uppercase tracking-wider" style="color: var(--text-muted)">
            Time to First Token
          </span>
          <div class="flex gap-3">
            <div class="metric-group flex-1">
              <span class="metric-label">P50</span>
              <span class="metric-value">{{ formatMs(vllmMetrics.ttftP50Ms) }}</span>
            </div>
            <div class="metric-group flex-1">
              <span class="metric-label">P99</span>
              <span class="metric-value" :style="{ color: ttftP99Color }">
                {{ formatMs(vllmMetrics.ttftP99Ms) }}
              </span>
            </div>
          </div>
        </div>

        <!-- Error / Truncation Rates -->
        <div class="flex gap-3">
          <div class="metric-group flex-1">
            <span class="metric-label">Error Rate</span>
            <span class="metric-value" :style="{ color: vllmMetrics.errorPct > 5 ? 'var(--danger)' : 'var(--text-secondary)' }">
              {{ vllmMetrics.errorPct.toFixed(1) }}%
            </span>
          </div>
          <div class="metric-group flex-1">
            <span class="metric-label">Truncation Rate</span>
            <span class="metric-value" :style="{ color: vllmMetrics.truncPct > 10 ? 'var(--warning)' : 'var(--text-secondary)' }">
              {{ vllmMetrics.truncPct.toFixed(1) }}%
            </span>
          </div>
        </div>

        <!-- Bottleneck Indicator -->
        <div
          v-if="bottleneck"
          class="mt-1 flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs"
          :style="{
            borderColor: bottleneckColor,
            backgroundColor: bottleneckBg,
          }"
        >
          <i :class="bottleneckIcon" class="text-xs" :style="{ color: bottleneckColor }" />
          <span :style="{ color: bottleneckTextColor }">{{ bottleneck }}</span>
        </div>
      </div>
    </template>
  </Card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { VllmMetrics } from '~/types/dashboard'
import { formatMs } from '~/utils/dashboard'

const props = defineProps<{
  vllmMetrics: VllmMetrics | null
}>()

// KV Cache bar pass-through styles (cyan accent)
const kvCacheBarPt = {
  root: {
    style: {
      height: '6px',
      borderRadius: '3px',
      background: 'var(--border-color)',
    },
  },
  value: {
    style: {
      background: 'linear-gradient(90deg, var(--accent), var(--accent-hover))',
    },
  },
}

const ttftP99Color = computed(() => {
  if (!props.vllmMetrics) return 'var(--text-secondary)'
  return props.vllmMetrics.ttftP99Ms > 5000 ? 'var(--danger)' : 'var(--text-primary)'
})

const bottleneck = computed(() => {
  if (!props.vllmMetrics) return ''
  if (props.vllmMetrics.gpuCachePct >= 95) return 'KV Cache near capacity — consider scaling'
  if (props.vllmMetrics.waiting > props.vllmMetrics.running * 2) return 'Queue growing faster than throughput — consider adding capacity'
  if (props.vllmMetrics.ttftP99Ms > 10000) return 'High TTFT latency — check GPU contention'
  if (props.vllmMetrics.errorPct > 10) return 'Elevated error rate — check agent logs'
  return ''
})

const bottleneckColor = computed(() => {
  if (!bottleneck.value) return 'transparent'
  return 'var(--warning)'
})

const bottleneckBg = computed(() => {
  if (!bottleneck.value) return 'transparent'
  return 'rgba(245, 158, 11, 0.08)'
})

const bottleneckTextColor = computed(() => {
  if (!bottleneck.value) return 'transparent'
  return 'var(--text-secondary)'
})

const bottleneckIcon = computed(() => {
  if (!bottleneck.value) return ''
  return 'pi pi-exclamation-triangle'
})
</script>
