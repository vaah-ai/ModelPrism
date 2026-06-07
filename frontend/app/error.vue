<template>
  <div class="flex min-h-screen items-center justify-center bg-surface-50 p-4 dark:bg-gray-950">
    <Card class="w-full max-w-md">
      <template #title>
        <div class="flex items-center gap-3">
          <i :class="errorIcon" class="text-2xl" :style="{ color: errorColor }" />
          <span>{{ errorTitle }}</span>
        </div>
      </template>
      <template #content>
        <p class="mb-4 text-surface-600 dark:text-surface-400">
          {{ error.message || 'An unexpected error occurred.' }}
        </p>
        <div v-if="error.statusCode" class="mb-4">
          <Tag :value="`Error ${error.statusCode}`" :severity="errorSeverity" />
        </div>
      </template>
      <template #footer>
        <div class="flex gap-2">
          <Button label="Go Home" icon="pi pi-home" @click="handleGoHome" />
          <Button
            v-if="error.statusCode === 404"
            label="Back"
            icon="pi pi-arrow-left"
            severity="secondary"
            @click="handleGoBack"
          />
        </div>
      </template>
    </Card>
  </div>
</template>

<script setup lang="ts">
import type { NuxtError } from '#app'
import { clearError } from 'nuxt/app'

const props = defineProps<{
  error: NuxtError
}>()

const errorTitle = computed(() => {
  if (props.error.statusCode === 404) return 'Page Not Found'
  if (props.error.statusCode === 500) return 'Server Error'
  return 'Error'
})

const errorIcon = computed(() => {
  if (props.error.statusCode === 404) return 'pi pi-exclamation-circle'
  if (props.error.statusCode === 500) return 'pi pi-times-circle'
  return 'pi pi-info-circle'
})

const errorColor = computed(() => {
  if (props.error.statusCode === 404) return '#f59e0b'
  if (props.error.statusCode === 500) return '#ef4444'
  return '#3b82f6'
})

const errorSeverity = computed(() => {
  if (props.error.statusCode === 404) return 'warn'
  if (props.error.statusCode === 500) return 'danger'
  return 'info'
})

function handleGoHome() {
  clearError({ redirect: '/dashboard' })
}

function handleGoBack() {
  clearError({ redirect: undefined })
  history.back()
}
</script>
