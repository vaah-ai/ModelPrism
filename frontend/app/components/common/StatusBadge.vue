<template>
  <Tag
    :value="label"
    :severity="severity"
    class="text-xs font-medium"
    :pt="{
      root: {
        class: 'inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[11px] font-semibold uppercase tracking-wider',
      },
    }"
  >
    <template #icon>
      <span
        v-if="status === 'online'"
        class="inline-block h-1.5 w-1.5 rounded-full"
        :class="{ 'status-pulse': status === 'online' }"
        style="background-color: var(--success)"
      />
      <span
        v-else-if="status === 'connecting'"
        class="inline-block h-1.5 w-1.5 rounded-full animate-pulse"
        style="background-color: var(--warning)"
      />
    </template>
  </Tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ConnectionStatus } from '~/types/dashboard'

const props = defineProps<{
  status: ConnectionStatus
}>()

const severity = computed<'success' | 'warn' | 'secondary' | 'info' | 'danger'>(() => {
  switch (props.status) {
    case 'online':
      return 'success'
    case 'degraded':
      return 'warn'
    case 'connecting':
      return 'info'
    case 'offline':
      return 'secondary'
    default:
      return 'info'
  }
})

const label = computed(() => {
  switch (props.status) {
    case 'online':
      return 'Online'
    case 'offline':
      return 'Offline'
    case 'degraded':
      return 'Degraded'
    case 'connecting':
      return 'Connecting'
    default:
      return props.status
  }
})
</script>

<style scoped>
@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.status-pulse {
  animation: pulse-dot 2s ease-in-out infinite;
}
</style>
