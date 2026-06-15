<template>
  <Card>
    <template #title>
      <div class="flex items-center gap-2">
        <i class="pi pi-chart-line text-sm" :style="{ color: accentColor }" />
        <span class="text-sm font-semibold" style="color: var(--text-primary)">{{ resolvedTitle }}</span>
      </div>
    </template>
    <template #content>
      <div
        ref="chartContainer"
        class="relative"
        :style="{ height: `${height}px` }"
      >
        <!-- Empty state overlay -->
        <div
          v-if="metricsHistory.length === 0"
          class="absolute inset-0 z-10 flex items-center justify-center rounded-lg"
          style="background-color: var(--bg-surface)"
        >
          <div class="flex flex-col items-center gap-1">
            <i class="pi pi-chart-bar text-base" style="color: var(--text-muted)" />
            <span class="text-xs" style="color: var(--text-muted)">Awaiting data...</span>
          </div>
        </div>
      </div>
    </template>
  </Card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import type { MetricPoint } from '~/types/dashboard'
import uplot from 'uplot'

const props = withDefaults(defineProps<{
  metricsHistory: MetricPoint[]
  chartType: 'gpuUtil' | 'vram' | 'throughput' | 'requests'
  height?: number
  title?: string
}>(), {
  height: 256,
})

const chartContainer = ref<HTMLDivElement | null>(null)
let chart: any = null
let resizeObserver: ResizeObserver | null = null

const MAX_POINTS = 150

const accentColor = computed(() => {
  // Resolve CSS custom properties to actual color values for canvas rendering
  const root = document.documentElement
  const style = getComputedStyle(root)
  switch (props.chartType) {
    case 'gpuUtil':
      return style.getPropertyValue('--accent').trim() || '#0891b2'
    case 'vram':
      return style.getPropertyValue('--info').trim() || '#2563eb'
    case 'throughput':
      return style.getPropertyValue('--success').trim() || '#16a34a'
    case 'requests':
      return style.getPropertyValue('--warning').trim() || '#d97706'
  }
})

const chartTitle = computed(() => {
  switch (props.chartType) {
    case 'gpuUtil':
      return 'GPU Utilization'
    case 'vram':
      return 'VRAM Usage'
    case 'throughput':
      return 'Throughput'
    case 'requests':
      return 'Requests'
  }
})

const resolvedTitle = computed(() => props.title ?? chartTitle.value)

// Convert MetricPoint[] to uPlot columnar data
function toColumnar(history: MetricPoint[]): (number[])[] {
  const timestamps: number[] = []
  const values: number[][] = []

  if (props.chartType === 'requests') {
    values.push([]) // running
    values.push([]) // waiting
  } else {
    values.push([]) // single series
  }

  for (const pt of history) {
    timestamps.push(new Date(pt.ts).getTime() / 1000)
    switch (props.chartType) {
      case 'gpuUtil':
        values[0].push(pt.gpuUtilAvgPct)
        break
      case 'vram':
        values[0].push(pt.gpuMemoryUsedMb / 1024) // Convert MB to GB
        break
      case 'throughput':
        values[0].push(pt.tps ?? 0) // tps from backend, or 0 until data arrives
        break
      case 'requests':
        values[0].push(pt.running)
        values[1].push(pt.waiting)
        break
    }
  }

  return [timestamps, ...values]
}

function resolveCssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

function getChartOptions() {
  const color = accentColor.value
  const success = resolveCssVar('--success') || '#16a34a'
  const warning = resolveCssVar('--warning') || '#d97706'
  const textMuted = resolveCssVar('--text-muted') || '#a1a1aa'
  const borderColor = resolveCssVar('--border-color') || '#e4e4e7'

  const font = `10px ${resolveCssVar('--font-mono') || 'monospace'}`

  const series: any[] = [
    {},
  ]

  if (props.chartType === 'requests') {
    series.push({
      label: 'Running',
      stroke: success,
      width: 2,
    })
    series.push({
      label: 'Waiting',
      stroke: warning,
      width: 2,
      fill: 'rgba(245, 158, 11, 0.1)',
    })
  } else {
    const name = chartTitle.value
    series.push({
      label: name,
      stroke: color,
      width: 2,
      ...(props.chartType === 'vram' ? { fill: `${color}33` } : {}),
    })
  }

  return {
    width: chartContainer.value?.clientWidth ?? 400,
    height: props.height,
    cursor: {
      show: true,
      drag: { x: false, y: false },
    },
    select: { show: false, left: 0, top: 0, width: 0, height: 0 },
    legend: { show: false },
    axes: [
      {
        stroke: textMuted,
        grid: { stroke: borderColor, width: 1 },
        ticks: { stroke: borderColor, size: 4 },
        font,
        // Limit x-axis time labels to 4 max to prevent overlap
        values: (self, splits, axisIdx, foundSpace, foundIncr) => {
          const step = Math.max(1, Math.floor(splits.length / 4))
          return splits.map((t, i) => {
            if (i % step !== 0) return ''
            const d = new Date(t * 1000)
            const h = d.getHours().toString().padStart(2, '0')
            const m = d.getMinutes().toString().padStart(2, '0')
            return h + ':' + m
          })
        },
      },
      {
        stroke: textMuted,
        grid: { stroke: borderColor, width: 1 },
        ticks: { stroke: borderColor, size: 4 },
        font,
      },
    ],
    series,
  }
}

function initChart() {
  if (!chartContainer.value) return

  // Clean up if exists
  if (chart) {
    chart.destroy()
    chart = null
  }

  const opts = getChartOptions()
  const initialData = toColumnar(props.metricsHistory.slice(-MAX_POINTS))

  // uPlot constructor: new uPlot(opts, data, container)
  chart = new uplot(opts, initialData, chartContainer.value!)
}

function updateChart() {
  if (!chart) return
  const data = toColumnar(props.metricsHistory.slice(-MAX_POINTS))
  chart.setData(data, false) // false = preserve current view window
}

function handleResize() {
  if (!chart || !chartContainer.value) return
  chart.setSize({
    width: chartContainer.value.clientWidth,
    height: props.height,
  })
}

// Watch metrics history length — detects new array references from store
watch(
  () => props.metricsHistory.length,
  () => {
    updateChart()
  },
)

onMounted(() => {
  initChart()

  // Set up ResizeObserver
  if (chartContainer.value) {
    resizeObserver = new ResizeObserver(() => {
      handleResize()
    })
    resizeObserver.observe(chartContainer.value)
  }
})

onUnmounted(() => {
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  if (chart) {
    chart.destroy()
    chart = null
  }
})
</script>
