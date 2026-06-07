<template>
  <div>
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
    <Toast />
  </div>
</template>

<script setup lang="ts">
const appConfig = useAppConfig();
useHead({
  titleTemplate: `%s — ${appConfig.title}`,
  htmlAttrs: {
    lang: "en",
  },
});
</script>
