<script setup>
import { computed } from "vue";
import CaptureImage from "../components/CaptureImage.vue";
import { useSkyHub } from "../composables/useSkyHub";

const {
  latest,
  latestImageUrl,
  loading,
  message,
  nodes,
  selectedNode,
  settings,
  refreshDashboard,
  startCapture,
  stopCapture
} = useSkyHub();

const onlineCount = computed(() => nodes.value.filter((node) => node.online).length);
const captureState = computed(() => settings.value?.capture_enabled ? "Capturing" : "Idle");
</script>

<template>
  <main class="workspace monitor-layout">
    <section class="panel hero-panel">
      <div class="content preview">
        <div class="capture-toolbar">
          <div>
            <h2>Live Monitor</h2>
            <div v-if="latest" class="muted">
              Latest: {{ latest.archive_date }}/{{ latest.period }} - {{ latest.filename }}
            </div>
            <div v-else class="muted">No captures for this node yet</div>
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
        <span>Capture</span>
        <strong>{{ captureState }}</strong>
        <small v-if="settings?.current_sequence_id">{{ settings.current_sequence_id }}</small>
      </section>
      <section class="panel stat-card">
        <span>Node</span>
        <strong>{{ selectedNode?.node_id || "None" }}</strong>
        <small>{{ selectedNode?.last_message_type || "No messages yet" }}</small>
      </section>
      <section class="panel stat-card">
        <span>Online nodes</span>
        <strong>{{ onlineCount }} / {{ nodes.length }}</strong>
        <small>{{ settings?.interval_seconds || "-" }}s interval</small>
      </section>
    </aside>
  </main>
</template>
