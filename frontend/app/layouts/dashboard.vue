<template>
  <div class="flex min-h-screen bg-surface-50 dark:bg-gray-950">
    <!-- Mobile overlay sidebar -->
    <Transition name="sidebar">
      <div
        v-if="sidebarOpen"
        class="fixed inset-0 z-40 bg-black/50 lg:hidden"
        @click="sidebarOpen = false"
      />
    </Transition>

    <!-- Sidebar -->
    <aside
      class="fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-surface-200 bg-white shadow-lg transition-transform duration-300 dark:border-gray-700 dark:bg-gray-900 lg:static lg:translate-x-0"
      :class="sidebarOpen ? 'translate-x-0' : '-translate-x-full'"
    >
      <!-- Brand -->
      <div class="flex h-16 items-center justify-between border-b border-surface-200 px-6 dark:border-gray-700">
        <NuxtLink to="/dashboard" class="flex items-center gap-2">
          <span class="text-xl font-bold text-primary">ModelPrism</span>
        </NuxtLink>
        <button
          class="flex h-8 w-8 items-center justify-center rounded-lg text-surface-500 hover:bg-surface-100 hover:text-surface-700 lg:hidden dark:hover:bg-gray-800"
          @click="sidebarOpen = false"
        >
          <i class="pi pi-times" />
        </button>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 overflow-y-auto p-3">
        <PanelMenu :model="navItems" class="border-none" />
      </nav>

      <!-- Footer -->
      <div class="border-t border-surface-200 p-4 text-center text-xs text-surface-400 dark:border-gray-700">
        ModelPrism v{{ appConfig.version }}
      </div>
    </aside>

    <!-- Main content area -->
    <div class="flex flex-1 flex-col lg:pl-0">
      <!-- Top bar -->
      <header class="flex h-16 items-center justify-between border-b border-surface-200 bg-white px-4 dark:border-gray-700 dark:bg-gray-900">
        <div class="flex items-center gap-3">
          <button
            class="flex h-10 w-10 items-center justify-center rounded-lg text-surface-500 hover:bg-surface-100 hover:text-surface-700 dark:hover:bg-gray-800"
            @click="sidebarOpen = !sidebarOpen"
          >
            <i class="pi pi-bars text-xl" />
          </button>
          <h2 class="text-lg font-semibold text-surface-800 dark:text-white">
            {{ pageTitle }}
          </h2>
        </div>

        <div class="flex items-center gap-2">
          <Tag value="MVP" severity="info" />
        </div>
      </header>

      <!-- Page content -->
      <main class="flex-1 overflow-auto p-6">
        <slot />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const appConfig = useAppConfig()
const route = useRoute()
const sidebarOpen = ref(false)

const pageTitle = computed(() => {
  const name = route.name as string || ''
  if (name.includes('dashboard-servers-id')) return 'Server Dashboard'
  if (name.includes('dashboard-index')) return 'GPU Server Overview'
  return 'Dashboard'
})

interface NavItem {
  label: string
  icon: string
  to: string
  items?: NavItem[]
}

const navItems = ref<NavItem[]>([
  {
    label: 'Servers',
    icon: 'pi pi-server',
    to: '/dashboard',
  },
  {
    label: 'Models',
    icon: 'pi pi-box',
    to: '#',
    items: [
      { label: 'All Models', icon: 'pi pi-th-large', to: '/dashboard/models' },
      { label: 'Deploy', icon: 'pi pi-plus', to: '/dashboard/models/deploy' },
    ],
  },
  {
    label: 'Benchmarks',
    icon: 'pi pi-chart-bar',
    to: '#',
    items: [
      { label: 'History', icon: 'pi pi-history', to: '/dashboard/benchmarks' },
      { label: 'New Benchmark', icon: 'pi pi-play', to: '/dashboard/benchmarks/new' },
    ],
  },
  {
    label: 'API Keys',
    icon: 'pi pi-key',
    to: '/dashboard/keys',
  },
  {
    label: 'Usage',
    icon: 'pi pi-chart-line',
    to: '/dashboard/usage',
  },
  {
    label: 'Settings',
    icon: 'pi pi-cog',
    to: '#',
    items: [
      { label: 'Workspace', icon: 'pi pi-sliders-h', to: '/dashboard/settings' },
      { label: 'Members', icon: 'pi pi-users', to: '/dashboard/settings/members' },
      { label: 'Billing', icon: 'pi pi-credit-card', to: '/dashboard/settings/billing' },
    ],
  },
  {
    label: 'Admin',
    icon: 'pi pi-shield',
    to: '/dashboard/admin',
  },
])
</script>

<style scoped>
.sidebar-enter-active,
.sidebar-leave-active {
  transition: opacity 0.3s ease;
}
.sidebar-enter-from,
.sidebar-leave-to {
  opacity: 0;
}
</style>
