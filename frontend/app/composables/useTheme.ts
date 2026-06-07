export type ThemePreference = 'system' | 'light' | 'dark'

const STORAGE_KEY = 'theme-preference'
const DARK_CLASS = 'p-dark'

export function useTheme() {
  const isSystemDark = usePreferredDark()

  // Read initial preference from localStorage
  const stored = import.meta.client
    ? (localStorage.getItem(STORAGE_KEY) as ThemePreference | null)
    : null
  const preference = ref<ThemePreference>(stored ?? 'system')

  const isDark = computed(() => {
    if (preference.value === 'system') return isSystemDark.value
    return preference.value === 'dark'
  })

  function applyTheme(dark: boolean) {
    if (dark) {
      document.documentElement.classList.add(DARK_CLASS)
    } else {
      document.documentElement.classList.remove(DARK_CLASS)
    }
  }

  // Watch preference changes and persist
  watch(
    preference,
    (val) => {
      localStorage.setItem(STORAGE_KEY, val)
    },
    { immediate: true },
  )

  // Watch effective dark state and apply class
  watch(
    isDark,
    (dark) => {
      applyTheme(dark)
    },
    { immediate: true },
  )

  function cycleTheme() {
    const order: ThemePreference[] = ['system', 'light', 'dark']
    const idx = order.indexOf(preference.value)
    preference.value = order[(idx + 1) % order.length] as ThemePreference
  }

  const currentIcon = computed(() => {
    switch (preference.value) {
      case 'light':
        return 'pi pi-sun'
      case 'dark':
        return 'pi pi-moon'
      default:
        return 'pi pi-desktop'
    }
  })

  const currentLabel = computed(() => {
    switch (preference.value) {
      case 'light':
        return 'Theme: Light'
      case 'dark':
        return 'Theme: Dark'
      default:
        return 'Theme: System'
    }
  })

  return {
    preference,
    isDark,
    currentIcon,
    currentLabel,
    cycleTheme,
  }
}

export type UseThemeReturn = ReturnType<typeof useTheme>
