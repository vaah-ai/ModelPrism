<script setup lang="ts">
// Redirect to dashboard on page load
onMounted(() => {
  navigateTo('/dashboard', { replace: true })
})
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-surface-50 dark:bg-gray-950">
    <div class="text-center">
      <i class="pi pi-spin pi-spinner mb-4 text-3xl text-primary" />
      <p class="text-sm text-surface-500">Redirecting to dashboard...</p>
    </div>
  </div>
</template>
