<script setup>
import { computed } from "vue";
import CaptureImage from "../components/CaptureImage.vue";
import { formatBytes, formatDateTime } from "../api/skyhub";
import { useSkyHub } from "../composables/useSkyHub";

const {
  latest,
  latestImageUrl,
  environmentTelemetry,
  heaterState,
  loading,
  message,
  nodes,
  selectedNode,
  settings,
  storageStats,
  refreshDashboard,
  setHeaterEnabled,
  startCapture,
  stopCapture
} = useSkyHub();

const onlineCount = computed(() => nodes.value.filter((node) => node.online).length);
const captureState = computed(() => settings.value?.capture_enabled ? "Capturing" : "Idle");
const heaterSummary = computed(() => {
  if (!heaterState.value) return "Unknown";

  return heaterState.value.actual_enabled ? "On" : "Off";
});
const heaterDetails = computed(() => {
  if (!heaterState.value) return "No state yet";

  const desired = heaterState.value.desired_enabled ? "desired on" : "desired off";
  const pin = heaterState.value.gpio_pin ? `GPIO ${heaterState.value.gpio_pin}` : heaterState.value.driver || "heater";

  return `${desired} - ${pin}`;
});
const environmentSummary = computed(() => {
  if (!environmentTelemetry.value) return "No data";

  return `${environmentTelemetry.value.temperature_c.toFixed(1)} C / ${environmentTelemetry.value.humidity_percent.toFixed(0)} %`;
});

const environmentDetails = computed(() => {
  if (!environmentTelemetry.value) return "BME280 not reporting yet";

  const parts = [];

  if (Number.isFinite(environmentTelemetry.value.dew_point_c)) {
    parts.push(`Dew ${environmentTelemetry.value.dew_point_c.toFixed(1)} C`);
  }

  if (Number.isFinite(environmentTelemetry.value.pressure_hpa)) {
    parts.push(`${environmentTelemetry.value.pressure_hpa.toFixed(0)} hPa`);
  }

  parts.push(formatDateTime(environmentTelemetry.value.captured_at || environmentTelemetry.value.updated_at));

  return parts.join(" - ");
});
</script>

<template>
  <main class="workspace monitor-layout">
    <section class="panel hero-panel">
      <div class="content preview">
        <div class="capture-toolbar">
          <div>
            <h2>Live Monitor</h2>
            <div v-if="latest" class="muted">
              {{ latest.archive_date }}/{{ latest.period }} - {{ latest.filename }}
            </div>
            <div v-else class="muted">No captures</div>
          </div>
          <div class="actions compact">
            <button type="button" @click="refreshDashboard">Refresh</button>
            <button type="button" class="primary" :disabled="!selectedNode" @click="startCapture">
              Start
            </button>
            <button type="button" class="danger" :disabled="!selectedNode" @click="stopCapture">
              Stop
            </button>
          </div>
        </div>

        <CaptureImage :image-url="latestImageUrl" />
        <div class="message">{{ loading ? "Refreshing..." : message }}</div>
      </div>
    </section>

    <aside class="monitor-summary">
      <section class="panel stat-card">
        <span>CAPTURE</span>
        <strong>{{ captureState }}</strong>
        <small v-if="settings?.current_sequence_id">{{ settings.current_sequence_id }}</small>
      </section>
      <section class="panel stat-card">
        <span>NODE</span>
        <strong>{{ selectedNode?.node_id || "None" }}</strong>
        <small>{{ selectedNode?.last_message_type || "No messages yet" }}</small>
      </section>
      <section class="panel stat-card">
        <span>NODES</span>
        <strong>{{ onlineCount }} / {{ nodes.length }}</strong>
        <small>{{ settings?.interval_seconds || "-" }}s interval</small>
      </section>
      <section class="panel stat-card">
        <span>ENV</span>
        <strong>{{ environmentSummary }}</strong>
        <small>{{ environmentDetails }}</small>
      </section>
      <section class="panel stat-card">
        <span>HEATER</span>
        <strong>{{ heaterSummary }}</strong>
        <small>{{ heaterDetails }}</small>
        <div class="stat-actions">
          <button
            type="button"
            :class="{ primary: heaterState?.desired_enabled }"
            :disabled="!selectedNode"
            @click="setHeaterEnabled(!heaterState?.desired_enabled)"
          >
            {{ heaterState?.desired_enabled ? "Turn off" : "Turn on" }}
          </button>
        </div>
      </section>
      <section class="panel stat-card">
        <span>CAPTURES</span>
        <strong>{{ formatBytes(storageStats?.captures_bytes) }}</strong>
        <small>{{ formatBytes(storageStats?.disk_free_bytes) }} free</small>
      </section>
    </aside>
  </main>
</template>

