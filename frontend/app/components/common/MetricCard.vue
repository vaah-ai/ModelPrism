<template>
  <div
    class="card-base flex flex-col rounded-xl border p-4 transition-colors"
    :class="$attrs.class"
    :style="{ borderLeftColor: borderColor, borderLeftWidth: '3px' }"
  >
    <span class="text-xs font-medium uppercase tracking-wider" style="color: var(--text-muted)">
      {{ label }}
    </span>
    <div class="mt-1 flex items-baseline gap-1.5">
      <span class="data-value-lg">{{ displayValue }}</span>
      <span v-if="unit" class="text-xs" style="color: var(--text-muted)">{{ unit }}</span>
    </div>
    <div v-if="trend" class="mt-1 flex items-center gap-1">
      <i
        :class="trendIcon"
        class="text-xs"
        :style="{ color: trendColor }"
      />
      <span class="text-xs" :style="{ color: trendColor }">{{ trendLabel }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { SeverityLevel, TrendDirection } from '~/types/dashboard'

const props = withDefaults(defineProps<{
  label: string
  value: string | number
  unit?: string
  trend?: TrendDirection
  severity?: SeverityLevel
}>(), {
  severity: 'info',
})

const borderColor = computed(() => {
  switch (props.severity) {
    case 'success':
      return 'var(--success)'
    case 'warn':
      return 'var(--warning)'
    case 'danger':
      return 'var(--danger)'
    case 'info':
      return 'var(--accent)'
    case 'secondary':
      return 'var(--text-muted)'
    default:
      return 'var(--accent)'
  }
})

const displayValue = computed(() => {
  if (typeof props.value === 'number') {
    // Format large numbers
    if (props.value >= 1000000) return (props.value / 1000000).toFixed(1) + 'M'
    if (props.value >= 1000) return (props.value / 1000).toFixed(1) + 'K'
    // Show decimals only when needed
    return Number.isInteger(props.value) ? props.value.toString() : props.value.toFixed(1)
  }
  return props.value
})

const trendIcon = computed(() => {
  switch (props.trend) {
    case 'up':
      return 'pi pi-arrow-up'
    case 'down':
      return 'pi pi-arrow-down'
    case 'stable':
      return 'pi pi-minus'
    default:
      return ''
  }
})

const trendColor = computed(() => {
  if (props.trend === 'up') return 'var(--success)'
  if (props.trend === 'down') return 'var(--danger)'
  return 'var(--text-muted)'
})

const trendLabel = computed(() => {
  switch (props.trend) {
    case 'up':
      return 'Up'
    case 'down':
      return 'Down'
    case 'stable':
      return 'Stable'
    default:
      return ''
  }
})
</script>
