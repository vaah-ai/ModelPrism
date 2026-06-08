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
          50: '#fafafa',
          100: '#f4f4f5',
          200: '#e4e4e7',
          300: '#d4d4d8',
          400: '#a1a1aa',
          500: '#71717a',
          600: '#52525b',
          700: '#3f3f46',
          800: '#27272a',
          900: '#18181b',
          950: '#09090b',
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
          50: '#121214',
          100: '#18181b',
          200: '#27272a',
          300: '#3f3f46',
          400: '#52525b',
          500: '#71717a',
          600: '#a1a1aa',
          700: '#d4d4d8',
          800: '#e4e4e7',
          900: '#f4f4f5',
          950: '#fafafa',
        },
      },
    },
  },
  components: {
    panelmenu: {
      panel: {
        background: 'transparent',
        borderColor: 'transparent',
        color: '{surface.700}',
        padding: '0',
      },
      item: {
        focusBackground: '{surface.200}',
        color: '{surface.600}',
        focusColor: '{surface.800}',
        borderRadius: '0.375rem',
        gap: '0.625rem',
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
      submenu: {
        indent: '0',
      },
    },
    card: {
      root: {
        background: '{surface.100}',
        borderRadius: '{border.radius.md}',
        color: '{surface.700}',
        shadow: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
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
        padding: '0.5rem 0.75rem',
      },
      header: {
        background: '{surface.50}',
        borderColor: '{surface.200}',
        color: '{surface.700}',
      },
      headerCell: {
        background: '{surface.50}',
        borderColor: '{surface.200}',
        color: '{surface.600}',
        hoverBackground: '{surface.200}',
        padding: '0.5rem 0.75rem',
      },
    },
    paginator: {
      root: {
        background: '{surface.100}',
        borderRadius: '0 0 {border.radius.md} {border.radius.md}',
        padding: '0.75rem 1rem',
        color: '{surface.600}',
      },
      navButton: {
        background: 'transparent',
        hoverBackground: '{surface.200}',
        color: '{surface.500}',
        hoverColor: '{surface.700}',
        borderRadius: '{border.radius.sm}',
      },
      currentPageReport: {
        color: '{surface.500}',
      },
    },
    inputtext: {
      root: {
        background: '{surface.100}',
        borderColor: '{surface.300}',
        color: '{surface.700}',
        borderRadius: '{border.radius.md}',
        paddingX: '0.75rem',
        paddingY: '0.5rem',
        transitionDuration: '{transition.duration}',
      },
    },
    select: {
      root: {
        background: '{surface.100}',
        borderColor: '{surface.300}',
        color: '{surface.700}',
        borderRadius: '{border.radius.md}',
        paddingX: '0.75rem',
        paddingY: '0.5rem',
        hoverBorderColor: '{surface.400}',
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
