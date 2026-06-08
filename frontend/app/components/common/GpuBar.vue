<template>
  <div class="flex flex-col gap-1">
    <div v-if="label || showValue" class="flex items-center justify-between">
      <span v-if="label" class="text-xs font-medium" style="color: var(--text-secondary)">
        {{ label }}
      </span>
      <span v-if="showValue" class="text-xs font-mono font-semibold" :style="{ color: barColor }">
        {{ clampedValue }}%
      </span>
    </div>
    <div
      class="overflow-hidden rounded-full"
      :style="{ height: `${barHeight}px`, backgroundColor: 'var(--border-color)' }"
    >
      <div
        class="h-full rounded-full transition-all duration-300 ease-out"
        :style="{
          width: `${clampedValue}%`,
          backgroundColor: barColor,
        }"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { GPU_THRESHOLDS } from '~/types/dashboard'

const props = withDefaults(defineProps<{
  value: number
  label?: string
  showValue?: boolean
  barHeight?: number
}>(), {
  showValue: true,
  barHeight: 6,
})

const clampedValue = computed(() => Math.max(0, Math.min(100, props.value)))

const barColor = computed(() => {
  if (clampedValue.value >= GPU_THRESHOLDS.AMBER_MAX) return 'var(--danger)'
  if (clampedValue.value >= GPU_THRESHOLDS.GREEN_MAX) return 'var(--warning)'
  return 'var(--success)'
})
</script>
