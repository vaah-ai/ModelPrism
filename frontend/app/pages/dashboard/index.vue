<template>
  <div>
    <!-- Summary Header -->
    <div class="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Card v-for="stat in summaryStats" :key="stat.label">
        <template #content>
          <div class="flex items-center justify-between">
            <div>
              <span class="text-sm font-medium text-surface-500">{{ stat.label }}</span>
              <div class="mt-1 text-2xl font-bold" :class="stat.color">
                {{ stat.value }}
              </div>
            </div>
            <i :class="`pi ${stat.icon} text-2xl text-surface-300`" />
          </div>
        </template>
      </Card>
    </div>

    <!-- Server List -->
    <Card>
      <template #title>
        <div class="flex items-center justify-between">
          <span>GPU Servers</span>
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
          :value="agentList"
          :loading="loading"
          paginator
          :rows="25"
          :rows-per-page-options="[10, 25, 50]"
          paginator-template="RowsPerPageDropdown FirstPageLink PrevPageLink CurrentPageReport NextPageLink LastPageLink"
          current-page-report-template="Showing {first} to {last} of {totalRecords}"
          sort-field="lastSeenAt"
          :sort-order="-1"
          striped-rows
          selection-mode="single"
          @row-click="navigateToServer"
        >
          <Column field="name" header="Name" sortable>
            <template #body="{ data }">
              <div class="flex items-center gap-2">
                <Tag
                  :value="data.status"
                  :severity="getStatusSeverity(data.status)"
                />
                <span class="font-medium">{{ data.name }}</span>
              </div>
            </template>
          </Column>
          <Column header="GPU" sortable :sort-field="'gpuModel'">
            <template #body="{ data }">
              <span class="text-sm text-surface-600">
                {{ data.gpuCount }}× {{ data.gpuModel }}
              </span>
            </template>
          </Column>
          <Column header="GPU Util" sortable :sort-field="'gpuUtilAvgPct'">
            <template #body="{ data }">
              <ProgressBar
                :value="Math.round(data.gpuUtilAvgPct ?? 0)"
                :class="getUtilColor(data.gpuUtilAvgPct ?? 0)"
                style="height: 8px"
              />
              <span class="ml-2 text-sm">{{ Math.round(data.gpuUtilAvgPct ?? 0) }}%</span>
            </template>
          </Column>
          <Column header="VRAM" sortable :sort-field="'gpuMemoryUsedMb'">
            <template #body="{ data }">
              <div class="flex items-center gap-2">
                <ProgressBar
                  :value="getVramPct(data)"
                  style="height: 8px; width: 80px"
                  :class="getUtilColor(getVramPct(data))"
                />
                <span class="text-sm">
                  {{ formatGb(data.gpuMemoryUsedMb) }} / {{ formatGb(data.gpuMemoryTotalMb) }} GB
                </span>
              </div>
            </template>
          </Column>
          <Column header="Running Models" sortable :sort-field="'runningModels'">
            <template #body="{ data }">
              <Tag
                :value="data.runningModels ?? 0"
                :severity="(data.runningModels ?? 0) > 0 ? 'info' : 'secondary'"
              />
            </template>
          </Column>
          <Column field="lastSeenAt" header="Last Seen" sortable>
            <template #body="{ data }">
              <span class="text-sm text-surface-500">
                {{ timeAgo(data.lastSeenAt) }}
              </span>
            </template>
          </Column>
          <Column header="Actions" style="width: 80px">
            <template #body>
              <Button
                icon="pi pi-chevron-right"
                severity="secondary"
                text
                rounded
              />
            </template>
          </Column>
        </DataTable>

        <!-- Empty State -->
        <div v-if="!loading && agentList.length === 0" class="py-12 text-center">
          <i class="pi pi-server mb-4 text-5xl text-surface-300" />
          <h3 class="mb-2 text-lg font-semibold text-surface-600">No GPU Servers Yet</h3>
          <p class="mb-6 text-sm text-surface-400">
            Add your first server to get started.
          </p>
          <Button label="Add Server" icon="pi pi-plus" @click="showAddDialog = true" />
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
        <div class="rounded-lg border border-surface-200 bg-surface-50 p-4 dark:border-gray-700 dark:bg-gray-800">
          <h4 class="mb-2 font-medium">Install the Agent</h4>
          <p class="mb-3 text-sm text-surface-500">
            Run this command on your GPU server to install the ModelPrism agent:
          </p>
          <div class="relative">
            <Textarea
              :value="installCommand"
              readonly
              rows="3"
              class="w-full font-mono text-sm"
              style="resize: none"
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

        <div class="rounded-lg border border-yellow-200 bg-yellow-50 p-3 dark:border-yellow-600 dark:bg-yellow-900/20">
          <p class="flex items-center gap-2 text-sm text-yellow-700 dark:text-yellow-400">
            <i class="pi pi-exclamation-triangle" />
            <span>Agent registration token generation will be available after backend integration.</span>
          </p>
        </div>
      </div>

      <template #footer>
        <Button label="Close" icon="pi pi-times" @click="showAddDialog = false" />
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

definePageMeta({
  layout: 'dashboard',
})

const router = useRouter()

interface AgentSummary {
  id: string
  name: string
  status: string
  hostname: string
  gpuCount: number
  gpuModel: string
  gpuMemoryTotalMb: number
  gpuMemoryUsedMb: number
  gpuUtilAvgPct: number
  runningModels: number
  lastSeenAt: string
}

const loading = ref(true)
const showAddDialog = ref(false)
const agentList = ref<AgentSummary[]>([])

const summaryStats = computed(() => [
  {
    label: 'Total Servers',
    value: agentList.value.length,
    icon: 'pi pi-server',
    color: 'text-primary',
  },
  {
    label: 'Online',
    value: agentList.value.filter(a => a.status === 'online').length,
    icon: 'pi pi-check-circle',
    color: 'text-green-600',
  },
  {
    label: 'Offline',
    value: agentList.value.filter(a => a.status === 'offline').length,
    icon: 'pi pi-times-circle',
    color: 'text-surface-400',
  },
  {
    label: 'Degraded',
    value: agentList.value.filter(a => a.status === 'degraded').length,
    icon: 'pi pi-exclamation-triangle',
    color: 'text-orange-500',
  },
])

const installCommand = computed(() => {
  const backendUrl = useRuntimeConfig().public.backendUrl
  return `curl -fsSL https://github.com/modelprism/agent/install.sh | \\
  bash -s -- --server ${backendUrl} --token <your-token>`
})

function getStatusSeverity(status: string): 'success' | 'warn' | 'secondary' | 'info' {
  switch (status) {
    case 'online': return 'success'
    case 'degraded': return 'warn'
    case 'offline': return 'secondary'
    default: return 'info'
  }
}

function getUtilColor(pct: number): string {
  if (pct >= 95) return 'bg-red-500'
  if (pct >= 70) return 'bg-orange-500'
  return 'bg-green-500'
}

function getVramPct(data: AgentSummary): number {
  if (!data.gpuMemoryTotalMb || data.gpuMemoryTotalMb === 0) return 0
  return Math.round((data.gpuMemoryUsedMb / data.gpuMemoryTotalMb) * 100)
}

function formatGb(mb: number): string {
  return (mb / 1024).toFixed(1)
}

function timeAgo(isoString: string): string {
  if (!isoString) return 'N/A'
  const seconds = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000)
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return `${Math.floor(seconds / 86400)}d ago`
}

function navigateToServer(event: { data: AgentSummary }) {
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
  // TODO M1-T9: Fetch agents from backend
  // const agentsStore = useAgentsStore()
  // await agentsStore.fetchAgents()
  // agentList.value = agentsStore.agents

  // Placeholder data for scaffold
  setTimeout(() => {
    loading.value = false
  }, 500)
})
</script>
