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
      class="w-full max-w-xl"
      :pt="{ title: { class: 'flex items-center gap-2 text-base' } }"
    >
      <template #header>
        <div class="flex items-center gap-2.5">
          <span
            class="flex h-8 w-8 items-center justify-center rounded-lg"
            style="background-color: var(--accent-subtle)"
          >
            <i class="pi pi-server" style="color: var(--text-accent); font-size: 0.875rem" />
          </span>
          <span class="text-sm font-semibold" style="color: var(--text-primary)">Add GPU Server</span>
        </div>
      </template>
      <div class="space-y-5">
        <!-- Step 1: Install -->
        <div class="card-elevated rounded-xl p-5">
          <div class="mb-3 flex items-center gap-3">
            <span
              class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs font-bold"
              style="background-color: var(--accent); color: #fff"
            >1</span>
            <div>
              <h4 class="text-sm font-semibold" style="color: var(--text-primary)">
                Install the Agent
              </h4>
              <p class="text-xs" style="color: var(--text-muted)">
                Run once on each GPU server
              </p>
            </div>
          </div>
          <div class="relative">
            <div
              class="w-full overflow-hidden rounded-lg border font-mono text-sm leading-relaxed"
              style="background-color: #0a0a0b; border-color: var(--border-color);"
            >
              <div class="flex items-start justify-between px-3 py-2">
                <span class="text-xs font-medium uppercase tracking-wider" style="color: var(--text-muted);">bash</span>
              </div>
              <Textarea
                :value="installCommand"
                readonly
                rows="3"
                class="w-full border-0 font-mono text-sm"
                :pt="{
                  root: {
                    style: {
                      resize: 'none',
                      borderRadius: '0',
                      background: 'transparent',
                      border: 'none',
                      color: 'var(--text-secondary)',
                      padding: '0.5rem 0.75rem',
                      fontFamily: 'var(--font-mono)',
                    },
                  },
                }"
              />
            </div>
            <Button
              icon="pi pi-copy"
              severity="secondary"
              text
              rounded
              class="absolute right-4 top-9"
              :pt="{ root: { class: 'h-8 w-8' } }"
              @click="copyInstallCommand"
            />
          </div>
        </div>

        <!-- Step 2: Configure -->
        <div
          class="card-elevated rounded-xl p-5"
          style="opacity: 0.5; pointer-events: none"
        >
          <div class="flex items-center gap-3">
            <span
              class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs font-bold"
              style="background-color: var(--text-muted); color: var(--bg-page)"
            >2</span>
            <div>
              <h4 class="text-sm font-semibold" style="color: var(--text-primary)">
                Configure Monitoring
              </h4>
              <p class="text-xs" style="color: var(--text-muted)">
                Coming soon — set alert thresholds &amp; notifications
              </p>
            </div>
          </div>
        </div>

        <!-- Notice -->
        <div
          class="flex items-start gap-3 rounded-xl border p-4"
          style="
            border-color: rgba(245, 158, 11, 0.3);
            background-color: rgba(245, 158, 11, 0.06);
          "
        >
          <i
            class="pi pi-exclamation-triangle mt-0.5 shrink-0"
            style="color: var(--warning); font-size: 0.875rem"
          />
          <p class="text-sm leading-relaxed" style="color: var(--text-secondary)">
            Agent registration token generation will be available after backend integration.
          </p>
        </div>
      </div>

      <template #footer>
        <div class="flex items-center justify-between gap-2">
          <span class="text-xs" style="color: var(--text-muted)">
            Need help? See the
            <a
              href="#"
              class="underline underline-offset-2"
              style="color: var(--text-accent)"
            >docs</a>
          </span>
          <Button
            label="Done"
            icon="pi pi-check"
            severity="secondary"
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
