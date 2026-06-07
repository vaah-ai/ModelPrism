// https://nuxt.com/docs/api/nuxt-config
import Aura from '@primeuix/themes/aura'
import { definePreset } from '@primeuix/themes'
import tailwindcss from '@tailwindcss/vite'

/**
 * Custom PrimeVue theme preset — Bold & Tech-forward
 * Dark-first design with Cyan (#06b6d4) accent
 */
const ModelPrismPreset = definePreset(Aura, {
  semantic: {
    primary: {
      50: '{cyan.50}',
      100: '{cyan.100}',
      200: '{cyan.200}',
      300: '{cyan.300}',
      400: '{cyan.400}',
      500: '{cyan.500}',
      600: '{cyan.600}',
      700: '{cyan.700}',
      800: '{cyan.800}',
      900: '{cyan.900}',
      950: '{cyan.950}',
    },
    colorScheme: {
      light: {
        primary: {
          color: '{cyan.500}',
          inverseColor: '#ffffff',
          hoverColor: '{cyan.600}',
          activeColor: '{cyan.700}',
        },
        surface: {
          0: '#fafaf8',
          50: '#f0f0ea',
          100: '#e6e6de',
          200: '#d8d8d0',
          300: '#c8c8be',
          400: '#a8a89e',
          500: '#88887e',
          600: '#6b6b60',
          700: '#4a4a44',
          800: '#2a2a28',
          900: '#1a1a18',
          950: '#0d0d0c',
        },
      },
      dark: {
        primary: {
          color: '{cyan.400}',
          inverseColor: '{slate.900}',
          hoverColor: '{cyan.300}',
          activeColor: '{cyan.200}',
        },
        surface: {
          0: '#0a0a0b',
          50: '#131316',
          100: '#1a1a1e',
          200: '#1e1e22',
          300: '#2a2a30',
          400: '#63636e',
          500: '#94949e',
          600: '#b0b0b8',
          700: '#c8c8ce',
          800: '#e0e0e4',
          900: '#e8e8ea',
          950: '#f5f5f6',
        },
      },
    },
  },
})

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
        preset: ModelPrismPreset,
        options: {
          prefix: 'p',
          darkModeSelector: '.p-dark',
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
