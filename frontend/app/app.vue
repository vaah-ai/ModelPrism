<template>
  <div>
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
    <Toast />
  </div>
</template>

<script setup lang="ts">
const appConfig = useAppConfig()

useHead({
  titleTemplate: `%s — ${appConfig.title}`,
  htmlAttrs: {
    lang: 'en',
  },
  script: [
    {
      innerHTML: `
        (function() {
          var stored = localStorage.getItem('theme-preference');
          var dark;
          if (stored === 'dark') {
            dark = true;
          } else if (stored === 'light') {
            dark = false;
          } else {
            dark = window.matchMedia('(prefers-color-scheme: dark)').matches;
          }
          if (dark) {
            document.documentElement.classList.add('p-dark');
          } else {
            document.documentElement.classList.remove('p-dark');
          }
        })();
      `,
      tagPosition: 'head',
      type: 'text/javascript',
    },
  ],
})
</script>
