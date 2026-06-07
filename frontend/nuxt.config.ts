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
          0: '#ffffff',
          50: '{slate.50}',
          100: '{slate.100}',
          200: '{slate.200}',
          300: '{slate.300}',
          400: '{slate.400}',
          500: '{slate.500}',
          600: '{slate.600}',
          700: '{slate.700}',
          800: '{slate.800}',
          900: '{slate.900}',
          950: '{slate.950}',
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
          0: '#030712',
          50: '#111827',
          100: '#1f2937',
          200: '#374151',
          300: '#4b5563',
          400: '#6b7280',
          500: '#9ca3af',
          600: '#d1d5db',
          700: '#e5e7eb',
          800: '#f3f4f6',
          900: '#f9fafb',
          950: '#ffffff',
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
