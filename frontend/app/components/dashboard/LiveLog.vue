<template>
  <Card>
    <template #title>
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <i class="pi pi-list text-sm" style="color: var(--accent)" />
          <span class="text-sm font-semibold" style="color: var(--text-primary)">Live Logs</span>
        </div>
        <div v-if="isPaused" class="flex items-center gap-1">
          <span class="text-xs" style="color: var(--warning)">
            {{ newLogsCount }} new log{{ newLogsCount !== 1 ? 's' : '' }}
          </span>
          <Button
            label="Scroll to bottom"
            icon="pi pi-arrow-down"
            severity="secondary"
            size="small"
            :pt="{ root: { class: 'h-6 text-xs px-2' } }"
            @click="scrollToBottom"
          />
        </div>
      </div>
    </template>
    <template #content>
      <!-- Level Filter & Search -->
      <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div v-if="filterable" class="flex flex-wrap gap-1">
          <Button
            v-for="level in availableLevels"
            :key="level.key"
            :label="level.label"
            :severity="activeLevel === level.key ? level.severity : 'secondary'"
            size="small"
            :variant="activeLevel === level.key ? undefined : 'text'"
            :pt="{ root: { class: 'h-7 text-xs px-2' } }"
            @click="activeLevel = level.key"
          />
        </div>
        <div v-if="searchable" class="relative min-w-[160px]">
          <i
            class="pi pi-search absolute left-2 top-1/2 -translate-y-1/2 text-xs"
            style="color: var(--text-muted)"
          />
          <InputText
            v-model="searchQuery"
            placeholder="Search logs..."
            class="w-full pl-7 text-xs"
            :pt="{ root: { class: 'h-7 text-xs' } }"
          />
        </div>
      </div>

      <!-- Log Entries -->
      <div
        ref="logContainer"
        class="overflow-y-auto rounded-lg border font-mono text-xs leading-relaxed"
        :style="{ height, borderColor: 'var(--border-color)', backgroundColor: '#0a0a0b' }"
        @scroll="onScroll"
      >
        <!-- Empty state -->
        <div
          v-if="filteredLogs.length === 0"
          class="flex items-center justify-center py-12"
        >
          <span class="text-xs" style="color: var(--text-muted)">
            {{ searchQuery ? 'No logs match your filter.' : 'No logs yet. Logs will appear here when the agent starts streaming.' }}
          </span>
        </div>

        <!-- Log entries -->
        <div v-for="(entry, index) in filteredLogs" :key="index" class="log-entry">
          <div
            class="flex items-start gap-2 px-2.5 py-1 transition-colors hover:bg-white/5"
          >
            <!-- Timestamp -->
            <span
              class="shrink-0 text-[10px]"
              style="color: var(--text-muted)"
              :title="entry.ts"
            >
              {{ formatTimestamp(entry.ts) }}
            </span>

            <!-- Level badge -->
            <span
              class="shrink-0 rounded px-1 py-[1px] text-[9px] font-semibold uppercase leading-tight"
              :style="logLevelStyle(entry.level)"
            >
              {{ entry.level }}
            </span>

            <!-- Module -->
            <span class="shrink-0 text-[10px]" style="color: var(--text-accent)">
              [{{ entry.module }}]
            </span>

            <!-- Message -->
            <span class="break-words" style="color: var(--text-primary)">
              {{ entry.message }}
            </span>
          </div>
        </div>
      </div>
    </template>
  </Card>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import type { LogEntry } from '~/types/dashboard'

const props = withDefaults(defineProps<{
  logs: LogEntry[]
  loading?: boolean
  maxLogs?: number
  filterable?: boolean
  searchable?: boolean
  height?: string
  levels?: LogEntry['level'][]
}>(), {
  loading: false,
  maxLogs: 500,
  filterable: true,
  searchable: true,
  height: '320px',
  levels: () => ['debug', 'info', 'warning', 'error'],
})

const emit = defineEmits<{
  (e: 'update:logs', logs: LogEntry[]): void
}>()

const logContainer = ref<HTMLDivElement | null>(null)
const activeLevel = ref<string>('all')
const searchQuery = ref('')
let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null
const debouncedSearch = ref('')

const isPaused = ref(false)
const newLogsCount = ref(0)
let autoScrollEnabled = true

const levelFilters: Array<{ key: string; label: string; severity: 'danger' | 'warn' | 'info' | 'secondary' | 'success' }> = [
  { key: 'all', label: 'All', severity: 'info' },
  { key: 'error', label: 'Error', severity: 'danger' },
  { key: 'warning', label: 'Warning', severity: 'warn' },
  { key: 'info', label: 'Info', severity: 'info' },
  { key: 'debug', label: 'Debug', severity: 'secondary' },
]

const availableLevels = computed(() => {
  const levelSet = new Set(props.levels)
  return levelFilters.filter((f) => f.key === 'all' || levelSet.has(f.key as LogEntry['level']))
})

const filteredLogs = computed(() => {
  let result = props.logs

  // Level filter
  if (activeLevel.value !== 'all') {
    result = result.filter((e) => e.level === activeLevel.value)
  }

  // Search filter
  if (debouncedSearch.value) {
    const q = debouncedSearch.value.toLowerCase()
    result = result.filter(
      (e) =>
        e.message.toLowerCase().includes(q) ||
        e.module.toLowerCase().includes(q),
    )
  }

  return result
})

function formatTimestamp(isoString: string): string {
  try {
    const d = new Date(isoString)
    return d.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return isoString
  }
}

function logLevelStyle(level: string): Record<string, string> {
  switch (level) {
    case 'error':
      return { backgroundColor: 'rgba(239, 68, 68, 0.15)', color: '#ef4444' }
    case 'warning':
      return { backgroundColor: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b' }
    case 'info':
      return { backgroundColor: 'rgba(59, 130, 246, 0.15)', color: '#3b82f6' }
    case 'debug':
      return { backgroundColor: 'rgba(161, 161, 170, 0.15)', color: '#a1a1aa' }
    default:
      return { backgroundColor: 'transparent', color: 'var(--text-secondary)' }
  }
}

function onScroll() {
  if (!logContainer.value) return
  const el = logContainer.value
  const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40
  autoScrollEnabled = atBottom
  if (atBottom) {
    isPaused.value = false
    newLogsCount.value = 0
  }
}

function scrollToBottom() {
  if (!logContainer.value) return
  logContainer.value.scrollTop = logContainer.value.scrollHeight
  autoScrollEnabled = true
  isPaused.value = false
  newLogsCount.value = 0
}

// Watch logs and auto-scroll / trim
watch(
  () => props.logs.length,
  (newLen, oldLen) => {
    if (newLen > oldLen) {
      if (!autoScrollEnabled) {
        isPaused.value = true
        newLogsCount.value += newLen - oldLen
      } else {
        // Use nextTick to scroll after DOM update
        setTimeout(() => {
          if (logContainer.value && autoScrollEnabled) {
            logContainer.value.scrollTop = logContainer.value.scrollHeight
          }
        }, 0)
      }
    }

    // Trim logs if over maxLogs
    if (newLen > props.maxLogs) {
      const trimmed = props.logs.slice(-props.maxLogs)
      emit('update:logs', trimmed)
    }
  },
)

// Watch search query with debounce
watch(searchQuery, (val) => {
  if (searchDebounceTimer) clearTimeout(searchDebounceTimer)
  searchDebounceTimer = setTimeout(() => {
    debouncedSearch.value = val
  }, 300)
})

onUnmounted(() => {
  if (searchDebounceTimer) clearTimeout(searchDebounceTimer)
  autoScrollEnabled = false
  isPaused.value = false
  newLogsCount.value = 0
})
</script>
