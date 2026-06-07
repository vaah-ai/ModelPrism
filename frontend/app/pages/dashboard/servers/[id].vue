<template>
  <div>
    <!-- Server header -->
    <div class="card-base mb-6 p-6">
      <div class="flex items-start gap-4">
        <div class="flex-1">
          <div class="flex items-center gap-3">
            <Tag
              :value="agentStatus"
              :severity="statusSeverity"
              class="text-sm"
            />
            <h1 class="text-2xl font-bold" style="color: var(--text-primary)">
              {{ agentName }}
            </h1>
          </div>
          <p class="mt-1 text-sm" style="color: var(--text-secondary)">
            {{ hostname }} · {{ gpuSummary }}
          </p>
        </div>
        <Button
          v-if="agentStatus === 'offline'"
          label="Reconnect"
          icon="pi pi-refresh"
          severity="secondary"
          size="small"
        />
      </div>
    </div>

    <!-- Metric Cards -->
    <div class="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <div
        v-for="metric in metricCards"
        :key="metric.label"
        class="card-base hover-lift p-5 text-center"
      >
        <span
          class="text-sm font-medium"
          style="color: var(--text-secondary)"
          >{{ metric.label }}</span
        >
        <div class="mt-1 text-2xl font-bold" :style="{ color: metric.color }">
          {{ metric.value }}
        </div>
        <span
          v-if="metric.unit"
          class="text-xs"
          style="color: var(--text-muted)"
          >{{ metric.unit }}</span
        >
      </div>
    </div>

    <!-- Placeholder for charts (M1-T9) -->
    <div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <Card>
        <template #title>GPU Utilization</template>
        <template #content>
          <div
            class="flex h-64 items-center justify-center rounded-lg border-2 border-dashed"
            style="border-color: var(--border-color)"
          >
            <p class="text-sm" style="color: var(--text-muted)">
              Real-time uPlot chart (M1-T9)
            </p>
          </div>
        </template>
      </Card>

      <Card>
        <template #title>System Resources</template>
        <template #content>
          <div
            class="flex h-64 items-center justify-center rounded-lg border-2 border-dashed"
            style="border-color: var(--border-color)"
          >
            <p class="text-sm" style="color: var(--text-muted)">
              System resources chart (M1-T9)
            </p>
          </div>
        </template>
      </Card>

      <Card>
        <template #title>Queue & Diagnostics</template>
        <template #content>
          <div
            class="flex h-48 items-center justify-center rounded-lg border-2 border-dashed"
            style="border-color: var(--border-color)"
          >
            <p class="text-sm" style="color: var(--text-muted)">
              Queue diagnostics panel (M1-T9)
            </p>
          </div>
        </template>
      </Card>

      <Card>
        <template #title>Running Models</template>
        <template #content>
          <div
            class="flex h-48 items-center justify-center rounded-lg border-2 border-dashed"
            style="border-color: var(--border-color)"
          >
            <p class="text-sm" style="color: var(--text-muted)">
              Model list panel (M1-T9)
            </p>
          </div>
        </template>
      </Card>
    </div>

    <!-- Live Log Viewer Placeholder -->
    <Card class="mt-6">
      <template #title>Live Logs</template>
      <template #content>
        <div
          class="flex h-48 items-center justify-center rounded-lg border-2 border-dashed"
          style="border-color: var(--border-color)"
        >
          <p class="text-sm" style="color: var(--text-muted)">
            Live log viewer (M1-T9)
          </p>
        </div>
      </template>
    </Card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";

definePageMeta({
  layout: "dashboard",
});

const route = useRoute();
const agentId = computed(() => route.params.id as string);

const agentName = ref("cyan-koala-42");
const hostname = ref("gpu-node-01");
const agentStatus = ref("online");
const gpuSummary = computed(() => "4× NVIDIA A100-SXM4-80GB");

const statusSeverity = computed<"success" | "warn" | "secondary">(() => {
  switch (agentStatus.value) {
    case "online":
      return "success";
    case "degraded":
      return "warn";
    default:
      return "secondary";
  }
});

const metricCards = computed(() => [
  { label: "GPU Util", value: "73.5%", unit: "", color: "var(--accent)" },
  { label: "VRAM", value: "152.3 / 324.8", unit: "GB", color: "#3b82f6" },
  { label: "Running", value: "2", unit: "models", color: "var(--success)" },
  { label: "Uptime", value: "78.5h", unit: "", color: "var(--text-secondary)" },
]);
</script>
