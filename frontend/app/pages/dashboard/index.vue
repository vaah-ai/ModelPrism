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
          <Button
            label="Add Server"
            icon="pi pi-plus"
            size="small"
            @click="showAddDialog = true"
          />
        </div>
      </template>
    </Card>

    <!-- Add Server Dialog -->
    <Dialog
      v-model:visible="showAddDialog"
      header="Add GPU Server"
      :modal="true"
      class="w-full max-w-lg"
    >
      <div class="space-y-4">
        <div
          class="card-base rounded-lg p-4"
          style="background-color: var(--bg-elevated)"
        >
          <h4 class="mb-2 font-medium" style="color: var(--text-primary)">
            Install the Agent
          </h4>
          <p class="mb-3 text-sm" style="color: var(--text-secondary)">
            Run this command on your GPU server to install the ModelPrism agent:
          </p>
          <div class="relative">
            <Textarea
              :value="installCommand"
              readonly
              rows="3"
              class="w-full font-mono text-sm"
              :pt="{ root: { style: { resize: 'none' } } }"
            />
            <Button
              icon="pi pi-copy"
              severity="secondary"
              text
              rounded
              class="absolute right-2 top-2"
              @click="copyInstallCommand"
            />
          </div>
        </div>

        <div
          class="rounded-lg border p-3"
          style="
            border-color: #f59e0b;
            background-color: rgba(245, 158, 11, 0.08);
          "
        >
          <p
            class="flex items-center gap-2 text-sm"
            style="color: var(--warning)"
          >
            <i class="pi pi-exclamation-triangle" />
            <span
              >Agent registration token generation will be available after
              backend integration.</span
            >
          </p>
        </div>
      </div>

      <template #footer>
        <Button
          label="Close"
          icon="pi pi-times"
          @click="showAddDialog = false"
        />
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

const installCommand = computed(() => {
  const backendUrl = useRuntimeConfig().public.backendUrl;
  return `curl -fsSL https://github.com/modelprism/agent/install.sh | \\
  bash -s -- --server ${backendUrl} --token <your-token>`;
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
