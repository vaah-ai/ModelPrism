<template>
  <div class="flex min-h-screen" style="background-color: var(--bg-page)">
    <!-- Mobile overlay sidebar -->
    <Transition name="sidebar">
      <div
        v-if="sidebarOpen"
        class="fixed inset-0 z-[60] bg-black/50 lg:hidden"
        @click="sidebarOpen = false"
      />
    </Transition>

    <!-- Sidebar -->
    <aside
      class="sidebar-base fixed inset-y-0 left-0 z-50 flex w-64 flex-col shadow-lg transition-transform duration-300 lg:static lg:translate-x-0"
      :class="sidebarOpen ? 'translate-x-0' : '-translate-x-full'"
    >
      <!-- Brand -->
      <div
        class="flex h-16 items-center justify-between border-b px-6"
        style="border-color: var(--border-color)"
      >
        <NuxtLink to="/dashboard" class="flex items-center gap-2">
          <span class="text-xl font-bold" style="color: var(--accent)"
            >ModelPrism</span
          >
        </NuxtLink>
        <button
          class="flex h-11 w-11 items-center justify-center rounded-lg lg:hidden"
          style="color: var(--text-muted)"
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
      <div
        class="border-t p-4 text-center text-xs"
        style="border-color: var(--border-color); color: var(--text-muted)"
      >
        ModelPrism v{{ appConfig.version }}
      </div>
    </aside>

    <!-- Main content area -->
    <div class="flex flex-1 flex-col lg:pl-0">
      <!-- Top bar -->
      <header
        class="header-base flex h-16 items-center justify-between px-4 lg:px-6"
      >
        <div class="flex items-center gap-3">
          <button
            class="flex h-11 w-11 items-center justify-center rounded-lg"
            style="color: var(--text-secondary)"
            @click="sidebarOpen = !sidebarOpen"
          >
            <i class="pi pi-bars text-xl" />
          </button>
          <h2 class="text-lg font-semibold" style="color: var(--text-primary)">
            {{ pageTitle }}
          </h2>
        </div>

        <div class="flex items-center gap-2">
          <Button
            :icon="themeIcon"
            text
            rounded
            severity="secondary"
            :pt="{
              root: { class: 'h-11 w-11' },
            }"
            :aria-label="themeLabel"
            :v-tooltip="themeLabel"
            @click="cycleTheme"
          />
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
import { ref, computed } from "vue";

const appConfig = useAppConfig();
const route = useRoute();
const sidebarOpen = ref(false);

const {
  currentIcon: themeIcon,
  currentLabel: themeLabel,
  cycleTheme,
} = useTheme();

const pageTitle = computed(() => {
  const name = (route.name as string) || "";
  if (name.includes("dashboard-servers-id")) return "Server Dashboard";
  if (name.includes("dashboard-index")) return "GPU Server Overview";
  return "Dashboard";
});

interface NavItem {
  label: string;
  icon: string;
  to: string;
  items?: NavItem[];
}

const navItems = ref<NavItem[]>([
  {
    label: "Servers",
    icon: "pi pi-server",
    to: "/dashboard",
  },
  {
    label: "Models",
    icon: "pi pi-box",
    to: "#",
    items: [
      { label: "All Models", icon: "pi pi-th-large", to: "/dashboard/models" },
      { label: "Deploy", icon: "pi pi-plus", to: "/dashboard/models/deploy" },
    ],
  },
  {
    label: "Benchmarks",
    icon: "pi pi-chart-bar",
    to: "#",
    items: [
      { label: "History", icon: "pi pi-history", to: "/dashboard/benchmarks" },
      {
        label: "New Benchmark",
        icon: "pi pi-play",
        to: "/dashboard/benchmarks/new",
      },
    ],
  },
  {
    label: "API Keys",
    icon: "pi pi-key",
    to: "/dashboard/keys",
  },
  {
    label: "Usage",
    icon: "pi pi-chart-line",
    to: "/dashboard/usage",
  },
  {
    label: "Settings",
    icon: "pi pi-cog",
    to: "#",
    items: [
      {
        label: "Workspace",
        icon: "pi pi-sliders-h",
        to: "/dashboard/settings",
      },
      {
        label: "Members",
        icon: "pi pi-users",
        to: "/dashboard/settings/members",
      },
      {
        label: "Billing",
        icon: "pi pi-credit-card",
        to: "/dashboard/settings/billing",
      },
    ],
  },
  {
    label: "Admin",
    icon: "pi pi-shield",
    to: "/dashboard/admin",
  },
]);
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
