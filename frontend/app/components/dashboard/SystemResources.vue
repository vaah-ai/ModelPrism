<template>
  <Card>
    <template #title>
      <div class="flex items-center gap-2">
        <i class="pi pi-microchip text-sm" style="color: var(--accent)" />
        <span class="text-sm font-semibold" style="color: var(--text-primary)">System Resources</span>
      </div>
    </template>
    <template #content>
      <div v-if="!metrics" class="flex items-center justify-center py-8">
        <span class="text-xs" style="color: var(--text-muted)">No metrics available</span>
      </div>
      <div v-else class="flex flex-col gap-4">
        <!-- GPU Utilization -->
        <div class="space-y-1.5">
          <GpuBar
            :value="metrics.gpuUtilAvgPct"
            label="GPU Utilization"
            :show-value="true"
          />
          <div class="flex gap-3 text-xs" style="color: var(--text-muted)">
            <span v-if="metrics.gpuTempC > 0">🌡️ {{ metrics.gpuTempC }}°C</span>
            <span v-if="metrics.gpuPowerW > 0">⚡ {{ metrics.gpuPowerW }}W</span>
          </div>
        </div>

        <!-- VRAM -->
        <div class="space-y-1">
          <div class="flex items-center justify-between">
            <span class="text-xs font-medium" style="color: var(--text-secondary)">VRAM</span>
            <span class="text-xs font-mono" :style="{ color: vramColor }">
              {{ formatGb(metrics.gpuMemoryUsedMb) }} / {{ formatGb(metrics.gpuMemoryTotalMb) }} GB
            </span>
          </div>
          <div
            class="overflow-hidden rounded-full"
            :style="{ height: '6px', backgroundColor: 'var(--border-color)' }"
          >
            <div
              class="h-full rounded-full transition-all duration-300"
              :style="{ width: `${vramPct}%`, backgroundColor: vramColor }"
            />
          </div>
        </div>

        <!-- RAM -->
        <div class="space-y-1">
          <div class="flex items-center justify-between">
            <span class="text-xs font-medium" style="color: var(--text-secondary)">RAM</span>
            <span class="text-xs font-mono" style="color: var(--text-secondary)">
              {{ metrics.ramUsedGb.toFixed(1) }} / {{ metrics.ramTotalGb.toFixed(1) }} GB
            </span>
          </div>
          <ProgressBar
            :value="ramPct"
            :pt="progressBarPt('var(--info)')"
            style="height: 6px"
          />
        </div>

        <!-- CPU -->
        <div class="space-y-1">
          <div class="flex items-center justify-between">
            <span class="text-xs font-medium" style="color: var(--text-secondary)">CPU</span>
            <span class="text-xs font-mono" style="color: var(--text-secondary)">
              {{ Math.round(metrics.cpuPct) }}%
            </span>
          </div>
          <ProgressBar
            :value="Math.round(metrics.cpuPct)"
            :pt="progressBarPt('var(--text-accent)')"
            style="height: 6px"
          />
          <div class="flex gap-2 text-xs" style="color: var(--text-muted)">
            <span>load: {{ metrics.load1.toFixed(1) }} / {{ metrics.load5.toFixed(1) }} / {{ metrics.load15.toFixed(1) }}</span>
          </div>
        </div>

        <!-- Disk -->
        <div class="space-y-1">
          <div class="flex items-center justify-between">
            <span class="text-xs font-medium" style="color: var(--text-secondary)">Disk</span>
            <span class="text-xs font-mono" style="color: var(--text-secondary)">
              {{ formatGb(metrics.diskUsedGb * 1024) }} / {{ formatGb(metrics.diskTotalGb * 1024) }} GB
            </span>
          </div>
          <ProgressBar
            :value="diskPct"
            :pt="progressBarPt('var(--text-muted)')"
            style="height: 6px"
          />
        </div>
      </div>
    </template>
  </Card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { MetricSnapshot } from '~/types/dashboard'
import { formatGb, getVramColor } from '~/utils/dashboard'

const props = defineProps<{
  metrics: MetricSnapshot | null
}>()

const vramPct = computed(() => {
  if (!props.metrics || !props.metrics.gpuMemoryTotalMb) return 0
  return Math.round((props.metrics.gpuMemoryUsedMb / props.metrics.gpuMemoryTotalMb) * 100)
})

const vramColor = computed(() => getVramColor(vramPct.value))

const ramPct = computed(() => {
  if (!props.metrics || !props.metrics.ramTotalGb) return 0
  return Math.round((props.metrics.ramUsedGb / props.metrics.ramTotalGb) * 100)
})

const diskPct = computed(() => {
  if (!props.metrics || !props.metrics.diskTotalGb) return 0
  return Math.round((props.metrics.diskUsedGb / props.metrics.diskTotalGb) * 100)
})

function progressBarPt(color: string) {
  return {
    root: {
      style: {
        height: '6px',
        borderRadius: '3px',
        background: 'var(--border-color)',
      },
    },
    value: {
      style: { background: color },
    },
  }
}
</script>
