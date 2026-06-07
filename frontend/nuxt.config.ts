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
          50: '#0e0e10',
          100: '#131316',
          200: '#1a1a1e',
          300: '#1e1e22',
          400: '#2a2a30',
          500: '#63636e',
          600: '#94949e',
          700: '#b0b0b8',
          800: '#c8c8ce',
          900: '#e0e0e4',
          950: '#e8e8ea',
        },
      },
    },
  },
  components: {
    panelmenu: {
      panel: {
        background: '{surface.100}',
        borderColor: '{surface.200}',
        color: '{surface.700}',
        padding: '0.25rem 0.25rem',
      },
      item: {
        focusBackground: '{surface.200}',
        color: '{surface.600}',
        focusColor: '{surface.800}',
        borderRadius: '0.375rem',
        gap: '0.5rem',
        padding: '0.5rem 0.75rem',
        icon: {
          color: '{surface.500}',
          focusColor: '{surface.700}',
        },
      },
      submenuIcon: {
        color: '{surface.500}',
        focusColor: '{surface.700}',
      },
    },
    card: {
      root: {
        background: '{surface.100}',
        borderRadius: '{border.radius.md}',
        color: '{surface.700}',
        shadow: '0 1px 2px 0 rgb(0 0 0 / 0.05)',
      },
    },
    datatable: {
      root: {
        borderColor: '{surface.200}',
      },
      row: {
        background: '{surface.100}',
        hoverBackground: '{surface.200}',
        color: '{surface.700}',
      },
      bodyCell: {
        borderColor: '{surface.200}',
      },
      header: {
        background: '{surface.50}',
        borderColor: '{surface.200}',
        color: '{surface.700}',
      },
      headerCell: {
        background: '{surface.100}',
        borderColor: '{surface.200}',
        color: '{surface.600}',
        hoverBackground: '{surface.200}',
      },
    },
    paginator: {
      root: {
        background: '{surface.100}',
        borderRadius: '{border.radius.md}',
        color: '{surface.600}',
      },
      navButton: {
        background: 'transparent',
        hoverBackground: '{surface.200}',
        color: '{surface.500}',
        hoverColor: '{surface.700}',
        borderRadius: '{border.radius.sm}',
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
