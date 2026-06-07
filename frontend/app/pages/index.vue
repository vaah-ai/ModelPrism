<script setup lang="ts">
// Redirect to dashboard on page load
onMounted(() => {
  navigateTo("/dashboard", { replace: true });
});
</script>

<template>
  <div
    class="flex min-h-screen items-center justify-center"
    style="background-color: var(--bg-page)"
  >
    <div class="text-center">
      <i class="pi pi-spin pi-spinner mb-4 text-3xl text-accent" />
      <p class="text-sm" style="color: var(--text-secondary)">
        Redirecting to dashboard...
      </p>
    </div>
  </div>
</template>
