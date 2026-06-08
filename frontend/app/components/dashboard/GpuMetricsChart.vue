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
  switch (props.chartType) {
    case 'gpuUtil':
      return 'var(--accent)'
    case 'vram':
      return 'var(--info)'
    case 'throughput':
      return 'var(--success)'
    case 'requests':
      return 'var(--warning)'
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
function toColumnar(history: MetricPoint[]): [number[], number[]] {
  const timestamps: number[] = []
  const values: number[] = []

  for (const pt of history) {
    timestamps.push(new Date(pt.ts).getTime() / 1000)
    switch (props.chartType) {
      case 'gpuUtil':
        values.push(pt.gpuUtilAvgPct)
        break
      case 'vram':
        values.push(pt.gpuMemoryUsedMb / 1024) // Convert MB to GB
        break
      case 'throughput':
        values.push(pt.running) // throughput proxy
        break
      case 'requests':
        // For multi-line, we handle via a single line for MVP
        values.push(pt.running)
        break
    }
  }

  return [timestamps, values]
}

function getChartOptions() {
  const color = accentColor.value

  let series: any[] = [
    {},
    {
      label: chartTitle.value,
      stroke: color,
      width: 2,
    },
  ]

  // Area fill for VRAM, line for others
  if (props.chartType === 'vram') {
    series[1].fill = `${color}33` // 20% opacity
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
        stroke: 'var(--text-muted)',
        grid: { stroke: 'var(--border-color)', width: 1 },
        ticks: { stroke: 'var(--border-color)' },
        font: '10px var(--font-mono)',
      },
      {
        stroke: 'var(--text-muted)',
        grid: { stroke: 'var(--border-color)', width: 1 },
        ticks: { stroke: 'var(--border-color)' },
        font: '10px var(--font-mono)',
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
  const data = toColumnar(props.metricsHistory.slice(-MAX_POINTS))

  // uPlot uses constructor: new uPlot(opts, data, container)
  // We use dynamic import to avoid SSR issues in Nuxt
  import('uplot').then((uplotModule) => {
    const uplot = uplotModule.default || uplotModule
    chart = new uplot(opts, data, chartContainer.value!)
  })
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

// Watch metrics history and update chart
watch(
  () => props.metricsHistory,
  () => {
    updateChart()
  },
  { deep: true },
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
