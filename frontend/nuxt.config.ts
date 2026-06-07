// https://nuxt.com/docs/api/nuxt-config
import Aura from '@primeuix/themes/aura'
import tailwindcss from '@tailwindcss/vite'

export default defineNuxtConfig({
  ssr: false,
  devtools: { enabled: true },

  modules: [
    '@primevue/nuxt-module',
    '@pinia/nuxt',
    '@vueuse/nuxt',
  ],

  primevue: {
    options: {
      theme: {
        preset: Aura,
        options: {
          prefix: 'p',
          darkModeSelector: 'system',
          cssLayer: false,
        },
      },
      ripple: true,
      inputVariant: 'filled',
    },
    autoImport: true,
  },

  css: ['~/assets/css/main.css'],

  vite: {
    plugins: [tailwindcss()],
  },

  runtimeConfig: {
    public: {
      backendUrl: import.meta.env.NUXT_PUBLIC_BACKEND_URL || 'http://localhost:8000',
    },
  },

  compatibilityDate: '2026-06-07',
})
