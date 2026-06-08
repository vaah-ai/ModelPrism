<template>
  <Card>
    <template #title>
      <div class="flex items-center gap-2">
        <i class="pi pi-box text-sm" style="color: var(--accent)" />
        <span class="text-sm font-semibold" style="color: var(--text-primary)">Running Models</span>
      </div>
    </template>
    <template #content>
      <div v-if="models.length === 0" class="flex flex-col items-center justify-center py-8">
        <i class="pi pi-inbox mb-2 text-lg" style="color: var(--text-muted)" />
        <span class="text-xs" style="color: var(--text-muted)">
          No models running on this server.
        </span>
      </div>
      <div v-else class="flex flex-col gap-2">
        <div
          v-for="model in models"
          :key="model.name"
          class="flex items-center justify-between rounded-lg border px-3 py-2 transition-colors hover-glow"
          :style="{ borderColor: 'var(--border-color)', backgroundColor: 'var(--bg-elevated)' }"
        >
          <div class="flex items-center gap-2 min-w-0">
            <i class="pi pi-box shrink-0 text-xs" style="color: var(--text-accent)" />
            <span class="truncate text-sm font-medium" style="color: var(--text-primary)">
              {{ model.name }}
            </span>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <span v-if="model.tps !== undefined" class="text-xs font-mono" style="color: var(--text-muted)">
              {{ model.tps }} tok/s
            </span>
            <Tag
              :value="model.status"
              :severity="model.status === 'running' ? 'success' : 'info'"
              class="text-[10px]"
            />
          </div>
        </div>
      </div>
    </template>
  </Card>
</template>

<script setup lang="ts">
import type { ModelInfo } from '~/types/dashboard'

defineProps<{
  models: ModelInfo[]
}>()
</script>
