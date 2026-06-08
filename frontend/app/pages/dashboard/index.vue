<template>
  <div>
    <!-- WebSocket Connection Indicator -->
    <div
      v-if="wsConnectionState !== 'connected' && wsConnectionState !== 'disconnected'"
      class="mb-3 flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs"
      :style="{
        borderColor: 'rgba(245, 158, 11, 0.3)',
        backgroundColor: 'rgba(245, 158, 11, 0.06)',
        color: 'var(--warning)',
      }"
    >
      <i class="pi pi-sync animate-spin text-xs" />
      <span>
        {{ wsConnectionState === 'reconnecting' ? 'Reconnecting to live updates...' : 'Connecting to live updates...' }}
      </span>
    </div>

    <!-- Summary Header Cards -->
    <div class="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <MetricCard
        label="Total Servers"
        :value="agentsStore.meta.total"
        :severity="'info'"
        trend="stable"
      />
      <MetricCard
        label="Online"
        :value="agentsStore.onlineAgents.length"
        :severity="'success'"
        trend="stable"
      />
      <MetricCard
        label="Offline"
        :value="agentsStore.offlineAgents.length"
        :severity="'secondary'"
        trend="stable"
      />
      <MetricCard
        label="Degraded"
        :value="agentsStore.degradedAgents.length"
        :severity="'warn'"
        trend="stable"
      />
    </div>

    <!-- Server List -->
    <Card :pt="{ title: { class: 'px-5 pt-4 pb-0' } }">
      <template #title>
        <div class="flex items-center justify-between">
          <span class="text-sm font-semibold" style="color: var(--text-primary);">GPU Servers</span>
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
          v-if="agentsStore.agentList.length > 0 || agentsStore.loading"
          :value="agentsStore.agentList"
          :loading="agentsStore.loading"
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
                <StatusBadge :status="data.status" />
                <span class="text-sm font-medium" style="color: var(--text-primary)">{{ data.name }}</span>
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
                <span class="text-xs" style="color: var(--text-secondary)">
                  {{ Math.round(data.gpuUtilAvgPct ?? 0) }}%
                </span>
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
                      style: { background: utilsGetVramColor(getVramPct(data)) },
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

        <!-- Empty State -->
        <div
          v-if="!agentsStore.loading && agentsStore.agentList.length === 0"
          class="flex flex-col items-center justify-center py-16"
        >
          <div
            class="mb-4 flex h-12 w-12 items-center justify-center rounded-full"
            style="background-color: var(--accent-subtle); border: 1px solid var(--accent-light);"
          >
            <i class="pi pi-server" style="color: var(--text-accent); font-size: 1.25rem;" />
          </div>
          <h3 class="mb-1 text-base font-semibold" style="color: var(--text-primary);">
            No GPU Servers Yet
          </h3>
          <p class="mb-4 text-xs" style="color: var(--text-secondary);">
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
            <i class="pi pi-server" style="color: #fff; font-size: 1rem;" />
          </span>
          <div>
            <span class="text-sm font-semibold" style="color: var(--text-primary);">Add GPU Server</span>
            <p class="text-xs" style="color: var(--text-muted);">Connect a new inference node</p>
          </div>
        </div>
      </template>

      <div class="space-y-0">
        <div class="relative pl-10">
          <div class="absolute left-[15px] top-2 h-[calc(100%+1rem)] w-px" style="background: linear-gradient(to bottom, var(--accent), var(--border-color));" />

          <!-- Step 1: Install -->
          <div class="relative pb-8">
            <div
              class="absolute -left-[7px] top-0 z-10 flex h-[15px] w-[15px] items-center justify-center rounded-full"
              style="background-color: var(--accent);"
            >
              <span class="text-[9px] font-bold" style="color: #fff;">1</span>
            </div>
            <div class="rounded-xl border p-4 transition-colors" style="border-color: var(--border-color); background-color: var(--bg-surface);">
              <div class="mb-3">
                <h4 class="text-sm font-semibold" style="color: var(--text-primary);">Install the Agent</h4>
                <p class="text-xs leading-relaxed" style="color: var(--text-muted); margin-top: 1px;">
                  Run this one-liner on your GPU server. The agent auto-registers with ModelPrism.
                </p>
              </div>
              <div class="overflow-hidden rounded-lg border" style="border-color: var(--border-color); background-color: #050505;">
                <div class="flex items-center gap-1.5 border-b px-3 py-1.5" style="border-color: var(--border-color); background-color: #0a0a0b;">
                  <span class="h-2.5 w-2.5 rounded-full" style="background-color: #ef4444;" />
                  <span class="h-2.5 w-2.5 rounded-full" style="background-color: #f59e0b;" />
                  <span class="h-2.5 w-2.5 rounded-full" style="background-color: #22c55e;" />
                  <span class="ml-2 text-[10px] font-medium uppercase tracking-wider" style="color: var(--text-muted);">Terminal — bash</span>
                  <div class="ml-auto">
                    <Button
                      icon="pi pi-copy"
                      severity="secondary"
                      text
                      rounded
                      :pt="{ root: { class: 'h-6 w-6 opacity-50 hover:opacity-100' } }"
                      :aria-label="'Copy install command'"
                      @click="copyInstallCommand"
                    />
                  </div>
                </div>
                <div class="px-3 py-2.5 font-mono text-xs leading-relaxed" style="color: #e4e4e7;">
                  <pre class="m-0 whitespace-pre-wrap break-all">$ <span style="color: #22d3ee;">curl</span> <span style="color: #818cf8;">-fsSL</span> <span style="color: #a1a1aa;">https://github.com/modelprism/agent/install.sh</span> <span style="color: #71717a;">| \</span>
  <span style="color: #22d3ee;">bash</span> <span style="color: #818cf8;">-s -</span><span style="color: #818cf8;">-</span> <span style="color: #f59e0b;">--server</span> <span style="color: #a1a1aa;">{{ backendUrl }}</span> <span style="color: #f59e0b;">--token</span> <span style="color: #c084fc;">&lt;your-token&gt;</span></pre>
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
              <span class="text-[9px] font-bold" style="color: var(--bg-page);">2</span>
            </div>
            <div
              class="rounded-xl border p-4 transition-colors"
              style="border-color: var(--border-color); background-color: var(--bg-surface); opacity: 0.55;"
            >
              <div class="flex items-center gap-2">
                <i class="pi pi-sliders-h text-xs" style="color: var(--text-muted);" />
                <h4 class="text-sm font-semibold" style="color: var(--text-primary);">Configure Monitoring</h4>
                <span
                  class="ml-auto rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider"
                  style="background-color: var(--accent-subtle); color: var(--text-accent);"
                >Soon</span>
              </div>
              <p class="mt-1 text-xs" style="color: var(--text-muted);">
                Set alert thresholds, notification channels, and auto-remediation rules.
              </p>
            </div>
          </div>
        </div>

        <div
          class="mb-2 flex items-start gap-3 rounded-xl border p-3.5"
          style="border-color: rgba(245, 158, 11, 0.25); background-color: rgba(245, 158, 11, 0.05);"
        >
          <i class="pi pi-exclamation-triangle mt-0.5 shrink-0 text-xs" style="color: var(--warning);" />
          <p class="text-xs leading-relaxed" style="color: var(--text-secondary);">
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
          <Button label="Done" icon="pi pi-check" @click="showAddDialog = false" />
        </div>
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAgentsStore } from '~~/stores/agents'
import { useWebSocketMetrics } from '~~/composables/useWebSocketMetrics'
import { useApi } from '~~/composables/useApi'
import { formatGb, timeAgo, getVramColor as utilsGetVramColor } from '~/utils/dashboard'

definePageMeta({
  layout: 'dashboard',
})

const router = useRouter()
const agentsStore = useAgentsStore()
const api = useApi()

const showAddDialog = ref(false)

// WebSocket connection for real-time metrics
const ws = useWebSocketMetrics()
const wsConnectionState = ws.connectionState
const backendUrl = useRuntimeConfig().public.backendUrl as string

const installCommand = ref(
  `curl -fsSL https://github.com/modelprism/agent/install.sh | \\\n  bash -s -- --server ${backendUrl} --token <your-token>`,
)

function getVramPct(data: { gpuMemoryUsedMb: number; gpuMemoryTotalMb: number }): number {
  if (!data.gpuMemoryTotalMb || data.gpuMemoryTotalMb === 0) return 0
  return Math.round((data.gpuMemoryUsedMb / data.gpuMemoryTotalMb) * 100)
}

function navigateToServer(event: { data: { id: string } }) {
  router.push(`/dashboard/servers/${event.data.id}`)
}

async function copyInstallCommand() {
  try {
    await navigator.clipboard.writeText(installCommand.value)
    useToast().add({
      severity: 'success',
      summary: 'Copied',
      detail: 'Install command copied to clipboard',
      life: 3000,
    })
  } catch {
    useToast().add({
      severity: 'error',
      summary: 'Failed',
      detail: 'Could not copy to clipboard',
      life: 3000,
    })
  }
}

onMounted(async () => {
  agentsStore.setLoading(true)
  try {
    // Attempt to fetch agents from backend
    const response = await api.get('/api/agents')
    const data = (response as any)?.data
    if (data && Array.isArray(data)) {
      const parsed = data.map((item: any) => ({
        id: item.id,
        name: item.attributes.name,
        status: item.attributes.status,
        hostname: item.attributes.hostname,
        agentVersion: item.attributes.agent_version,
        gpuCount: item.attributes.gpu_count,
        gpuModel: item.attributes.gpu_model,
        gpuMemoryTotalMb: item.attributes.gpu_memory_total_mb,
        gpuMemoryUsedMb: item.attributes.gpu_memory_used_mb,
        gpuUtilAvgPct: item.attributes.gpu_util_avg_pct,
        cpuCores: item.attributes.cpu_cores,
        ramTotalGb: item.attributes.ram_total_gb,
        ramUsedGb: item.attributes.ram_used_gb,
        diskTotalGb: item.attributes.disk_total_gb,
        diskUsedGb: item.attributes.disk_used_gb,
        runningModels: item.attributes.running_models,
        uptimeSeconds: item.attributes.uptime_seconds,
        lastSeenAt: item.attributes.last_seen_at,
        createdAt: item.attributes.created_at,
      }))
      const meta = (response as any)?.meta
      agentsStore.setAgents(parsed, meta)
    }
  } catch {
    // Backend unavailable — leave loading false, store remains empty
    agentsStore.setError('Could not reach backend')
  } finally {
    agentsStore.setLoading(false)
  }

  // Connect WebSocket for live updates
  ws.connect()
})

onUnmounted(() => {
  ws.disconnect()
})
</script>
