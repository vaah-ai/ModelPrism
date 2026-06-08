<template>
  <div>
    <!-- Summary Header Cards -->
    <div class="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <div
        v-for="stat in summaryStats"
        :key="stat.label"
        class="card-base hover-glow cursor-pointer p-4"
      >
        <div class="flex items-center justify-between">
          <div>
            <span
              class="text-xs font-medium"
              style="color: var(--text-secondary)"
              >{{ stat.label }}</span
            >
            <div class="mt-0.5 text-xl font-bold" :class="stat.color">
              {{ stat.value }}
            </div>
          </div>
          <div
            class="flex h-10 w-10 items-center justify-center rounded-lg"
            style="background-color: var(--accent-subtle)"
          >
            <i
              :class="`pi ${stat.icon}`"
              :style="{ color: stat.iconColor, fontSize: '1.1rem' }"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Server List -->
    <Card :pt="{ title: { class: 'px-5 pt-4 pb-0' } }">
      <template #title>
        <div class="flex items-center justify-between">
          <span class="text-sm font-semibold" style="color: var(--text-primary)">GPU Servers</span>
          <Button
            label="Add Server"
            icon="pi pi-plus"
            severity="secondary"
            size="small"
            @click="showAddDialog = true"
          />
        </div>
      </template>

      <template #content>
        <DataTable
          v-if="agentList.length > 0 || loading"
          :value="agentList"
          :loading="loading"
          paginator
          :rows="25"
          :rows-per-page-options="[10, 25, 50]"
          paginator-template="{FirstPageLink} {PreviousPageLink} {CurrentPageReport} {NextPageLink} {LastPageLink}"
          current-page-report-template="{first}–{last} of {totalRecords}"
          sort-field="lastSeenAt"
          :sort-order="-1"
          striped-rows
          selection-mode="single"
          @row-click="navigateToServer"
        >
          <Column field="name" header="Name" sortable>
            <template #body="{ data }">
              <div class="flex items-center gap-1.5">
                <Tag
                  :value="data.status"
                  :severity="getStatusSeverity(data.status)"
                  class="text-xs"
                />
                <span class="text-sm font-medium" style="color: var(--text-primary)">{{
                  data.name
                }}</span>
              </div>
            </template>
          </Column>
          <Column header="GPU" sortable :sort-field="'gpuModel'">
            <template #body="{ data }">
              <span class="text-xs" style="color: var(--text-secondary)">
                {{ data.gpuCount }}× {{ data.gpuModel }}
              </span>
            </template>
          </Column>
          <Column header="GPU Util" sortable :sort-field="'gpuUtilAvgPct'">
            <template #body="{ data }">
              <div class="flex items-center gap-1.5">
                <ProgressBar
                  :value="Math.round(data.gpuUtilAvgPct ?? 0)"
                  :pt="{
                    root: {
                      style: {
                        height: '6px',
                        borderRadius: '3px',
                        background: 'var(--border-color)',
                      },
                    },
                    value: { style: { background: 'var(--accent)' } },
                  }"
                  style="width: 64px"
                />
                <span class="text-xs" style="color: var(--text-secondary)"
                  >{{ Math.round(data.gpuUtilAvgPct ?? 0) }}%</span
                >
              </div>
            </template>
          </Column>
          <Column header="VRAM" sortable :sort-field="'gpuMemoryUsedMb'">
            <template #body="{ data }">
              <div class="flex items-center gap-1.5">
                <ProgressBar
                  :value="getVramPct(data)"
                  :pt="{
                    root: {
                      style: {
                        height: '6px',
                        borderRadius: '3px',
                        background: 'var(--border-color)',
                      },
                    },
                    value: {
                      style: { background: getVramColor(getVramPct(data)) },
                    },
                  }"
                  style="width: 64px"
                />
                <span class="text-xs" style="color: var(--text-secondary)">
                  {{ formatGb(data.gpuMemoryUsedMb) }} /
                  {{ formatGb(data.gpuMemoryTotalMb) }}
                </span>
              </div>
            </template>
          </Column>
          <Column header="Running" sortable :sort-field="'runningModels'">
            <template #body="{ data }">
              <Tag
                :value="data.runningModels ?? 0"
                :severity="(data.runningModels ?? 0) > 0 ? 'info' : 'secondary'"
                class="text-xs"
              />
            </template>
          </Column>
          <Column field="lastSeenAt" header="Last Seen" sortable>
            <template #body="{ data }">
              <span class="text-xs" style="color: var(--text-muted)">
                {{ timeAgo(data.lastSeenAt) }}
              </span>
            </template>
          </Column>
          <Column header="" style="width: 48px">
            <template #body>
              <Button
                icon="pi pi-chevron-right"
                severity="secondary"
                text
                rounded
                :pt="{ root: { class: 'h-7 w-7' } }"
              />
            </template>
          </Column>
        </DataTable>

        <!-- Empty State (only when no data and not loading) -->
        <div
          v-if="!loading && agentList.length === 0"
          class="flex flex-col items-center justify-center py-16"
        >
          <div
            class="mb-4 flex h-12 w-12 items-center justify-center rounded-full"
            style="background-color: var(--accent-subtle); border: 1px solid var(--accent-light);"
          >
            <i class="pi pi-server" style="color: var(--text-accent); font-size: 1.25rem" />
          </div>
          <h3 class="mb-1 text-base font-semibold" style="color: var(--text-primary)">
            No GPU Servers Yet
          </h3>
          <p class="mb-4 text-xs" style="color: var(--text-secondary)">
            Add your first server to get started.
          </p>
        </div>
      </template>
    </Card>

    <!-- Add Server Dialog -->
    <Dialog
      v-model:visible="showAddDialog"
      :modal="true"
      class="w-full max-w-2xl"
      :pt="{
        root: {
          class: 'border shadow-2xl',
          style: 'border-color: var(--border-color)',
        },
        header: { class: 'pb-0' },
        content: { class: 'pt-3' },
        title: { class: 'flex items-center gap-2 text-base' },
      }"
    >
      <template #header>
        <div class="flex items-center gap-3">
          <span
            class="flex h-9 w-9 items-center justify-center rounded-lg"
            style="background: linear-gradient(135deg, var(--accent), #0e7490);"
          >
            <i class="pi pi-server" style="color: #fff; font-size: 1rem" />
          </span>
          <div>
            <span class="text-sm font-semibold" style="color: var(--text-primary)">Add GPU Server</span>
            <p class="text-xs" style="color: var(--text-muted)">Connect a new inference node</p>
          </div>
        </div>
      </template>

      <div class="space-y-0">
        <!-- Step connector line -->
        <div class="relative pl-10">
          <!-- Vertical connector -->
          <div class="absolute left-[15px] top-2 h-[calc(100%+1rem)] w-px" style="background: linear-gradient(to bottom, var(--accent), var(--border-color));" />

          <!-- Step 1: Install -->
          <div class="relative pb-8">
            <div
              class="absolute -left-[7px] top-0 z-10 flex h-[15px] w-[15px] items-center justify-center rounded-full"
              style="background-color: var(--accent);"
            >
              <span class="text-[9px] font-bold" style="color: #fff">1</span>
            </div>
            <div class="rounded-xl border p-4 transition-colors" style="border-color: var(--border-color); background-color: var(--bg-surface);">
              <div class="mb-3">
                <h4 class="text-sm font-semibold" style="color: var(--text-primary)">Install the Agent</h4>
                <p class="text-xs leading-relaxed" style="color: var(--text-muted); margin-top: 1px;">
                  Run this one-liner on your GPU server. The agent auto-registers with ModelPrism.
                </p>
              </div>

              <!-- Terminal emulator -->
              <div class="overflow-hidden rounded-lg border" style="border-color: var(--border-color); background-color: #050505;">
                <!-- Title bar -->
                <div class="flex items-center gap-1.5 border-b px-3 py-1.5" style="border-color: var(--border-color); background-color: #0a0a0b;">
                  <span class="h-2.5 w-2.5 rounded-full" style="background-color: #ef4444;" />
                  <span class="h-2.5 w-2.5 rounded-full" style="background-color: #f59e0b;" />
                  <span class="h-2.5 w-2.5 rounded-full" style="background-color: #22c55e;" />
                  <span class="ml-2 text-[10px] font-medium uppercase tracking-wider" style="color: var(--text-muted);">Terminal — bash</span>
                </div>
                <!-- Code area -->
                <div class="relative">
                  <pre class="m-0 whitespace-pre-wrap break-all px-3 py-2.5 font-mono text-xs leading-relaxed" style="color: #e4e4e7;">$ <span style="color: #22d3ee;">curl</span> <span style="color: #818cf8;">-fsSL</span> <span style="color: #a1a1aa;">https://github.com/modelprism/agent/install.sh</span> <span style="color: #71717a;">| \</span>
  <span style="color: #22d3ee;">bash</span> <span style="color: #818cf8;">-s -</span><span style="color: #818cf8;">-</span> <span style="color: #f59e0b;">--server</span> <span style="color: #a1a1aa;">{{ backendUrl }}</span> <span style="color: #f59e0b;">--token</span> <span style="color: #c084fc;">&lt;your-token&gt;</span></pre>
                  <Button
                    icon="pi pi-copy"
                    severity="secondary"
                    text
                    rounded
                    class="absolute right-2 top-2"
                    :pt="{ root: { class: 'h-7 w-7 opacity-60 hover:opacity-100' } }"
                    @click="copyInstallCommand"
                  />
                </div>
              </div>
            </div>
          </div>

          <!-- Step 2: Configure (dimmed) -->
          <div class="relative pb-4">
            <div
              class="absolute -left-[7px] top-0 z-10 flex h-[15px] w-[15px] items-center justify-center rounded-full"
              style="background-color: var(--text-muted);"
            >
              <span class="text-[9px] font-bold" style="color: var(--bg-page)">2</span>
            </div>
            <div
              class="rounded-xl border p-4 transition-colors"
              style="border-color: var(--border-color); background-color: var(--bg-surface); opacity: 0.55;"
            >
              <div class="flex items-center gap-2">
                <i class="pi pi-sliders-h text-xs" style="color: var(--text-muted)" />
                <h4 class="text-sm font-semibold" style="color: var(--text-primary)">Configure Monitoring</h4>
                <span
                  class="ml-auto rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider"
                  style="background-color: var(--accent-subtle); color: var(--text-accent);"
                >Soon</span>
              </div>
              <p class="mt-1 text-xs" style="color: var(--text-muted)">
                Set alert thresholds, notification channels, and auto-remediation rules.
              </p>
            </div>
          </div>
        </div>

        <!-- Notice -->
        <div
          class="mb-2 flex items-start gap-3 rounded-xl border p-3.5"
          style="border-color: rgba(245, 158, 11, 0.25); background-color: rgba(245, 158, 11, 0.05);"
        >
          <i class="pi pi-exclamation-triangle mt-0.5 shrink-0 text-xs" style="color: var(--warning)" />
          <p class="text-xs leading-relaxed" style="color: var(--text-secondary)">
            Agent registration token generation requires backend integration — available in a future update.
          </p>
        </div>
      </div>

      <template #footer>
        <div class="flex w-full items-center justify-between gap-2">
          <Button
            label="Cancel"
            icon="pi pi-times"
            variant="text"
            severity="secondary"
            @click="showAddDialog = false"
          />
          <Button
            label="Done"
            icon="pi pi-check"
            @click="showAddDialog = false"
          />
        </div>
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";

definePageMeta({
  layout: "dashboard",
});

const router = useRouter();

interface AgentSummary {
  id: string;
  name: string;
  status: string;
  hostname: string;
  gpuCount: number;
  gpuModel: string;
  gpuMemoryTotalMb: number;
  gpuMemoryUsedMb: number;
  gpuUtilAvgPct: number;
  runningModels: number;
  lastSeenAt: string;
}

const loading = ref(true);
const showAddDialog = ref(false);
const agentList = ref<AgentSummary[]>([]);

const summaryStats = computed(() => [
  {
    label: "Total Servers",
    value: agentList.value.length,
    icon: "pi pi-server",
    color: "text-primary",
    iconColor: "var(--text-accent)",
  },
  {
    label: "Online",
    value: agentList.value.filter((a) => a.status === "online").length,
    icon: "pi pi-check-circle",
    color: "text-severity-success",
    iconColor: "var(--success)",
  },
  {
    label: "Offline",
    value: agentList.value.filter((a) => a.status === "offline").length,
    icon: "pi pi-times-circle",
    color: "text-secondary",
    iconColor: "var(--text-secondary)",
  },
  {
    label: "Degraded",
    value: agentList.value.filter((a) => a.status === "degraded").length,
    icon: "pi pi-exclamation-triangle",
    color: "text-severity-warning",
    iconColor: "var(--warning)",
  },
]);

const backendUrl = useRuntimeConfig().public.backendUrl;

const installCommand = computed(() => {
  return `curl -fsSL https://github.com/modelprism/agent/install.sh | \\\n  bash -s -- --server ${backendUrl} --token <your-token>`;
});

function getStatusSeverity(
  status: string,
): "success" | "warn" | "secondary" | "info" {
  switch (status) {
    case "online":
      return "success";
    case "degraded":
      return "warn";
    case "offline":
      return "secondary";
    default:
      return "info";
  }
}

function getVramColor(pct: number): string {
  if (pct >= 95) return "#ef4444";
  if (pct >= 70) return "#f59e0b";
  return "var(--accent)";
}

function getVramPct(data: AgentSummary): number {
  if (!data.gpuMemoryTotalMb || data.gpuMemoryTotalMb === 0) return 0;
  return Math.round((data.gpuMemoryUsedMb / data.gpuMemoryTotalMb) * 100);
}

function formatGb(mb: number): string {
  return (mb / 1024).toFixed(1);
}

function timeAgo(isoString: string): string {
  if (!isoString) return "N/A";
  const seconds = Math.floor(
    (Date.now() - new Date(isoString).getTime()) / 1000,
  );
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

function navigateToServer(event: { data: AgentSummary }) {
  router.push(`/dashboard/servers/${event.data.id}`);
}

async function copyInstallCommand() {
  try {
    await navigator.clipboard.writeText(installCommand.value);
    useToast().add({
      severity: "success",
      summary: "Copied",
      detail: "Install command copied to clipboard",
      life: 3000,
    });
  } catch {
    useToast().add({
      severity: "error",
      summary: "Failed",
      detail: "Could not copy to clipboard",
      life: 3000,
    });
  }
}

onMounted(async () => {
  // TODO M1-T9: Fetch agents from backend
  // const agentsStore = useAgentsStore()
  // await agentsStore.fetchAgents()
  // agentList.value = agentsStore.agents

  // Placeholder data for scaffold
  setTimeout(() => {
    loading.value = false;
  }, 500);
});
</script>
