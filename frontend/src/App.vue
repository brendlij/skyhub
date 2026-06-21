<script setup>
import { computed, onMounted, ref } from "vue";

const fields = [
  "interval_seconds",
  "width",
  "height",
  "format",
  "day_auto_exposure",
  "day_exposure_ms",
  "day_auto_gain",
  "day_gain",
  "night_auto_exposure",
  "night_exposure_ms",
  "night_auto_gain",
  "night_gain"
];

const nodes = ref([]);
const selectedNodeId = ref(null);
const settings = ref(null);
const latest = ref(null);
const message = ref("");
const loading = ref(false);

const selectedNode = computed(() =>
  nodes.value.find((node) => node.node_id === selectedNodeId.value)
);

const latestUrl = computed(() => {
  if (!latest.value) return null;
  return `/api/captures/${latest.value.node_id}/${latest.value.archive_date}/${latest.value.period}/${latest.value.filename}?t=${Date.now()}`;
});

function setMessage(text) {
  message.value = text || "";
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }

  return response.json();
}

async function loadNodes() {
  const data = await requestJson("/api/nodes");
  nodes.value = data.nodes;

  const onlineNode = nodes.value.find((node) => node.online);
  const current = nodes.value.find((node) => node.node_id === selectedNodeId.value);

  if ((!selectedNodeId.value || !current || (!current.online && onlineNode)) && (onlineNode || nodes.value.length)) {
    selectedNodeId.value = (onlineNode || nodes.value[0]).node_id;
  }
}

async function loadSettings() {
  if (!selectedNodeId.value) {
    settings.value = null;
    return;
  }

  const data = await requestJson(`/api/nodes/${selectedNodeId.value}/settings`);
  settings.value = {
    interval_seconds: data.interval_seconds,
    width: data.width,
    height: data.height,
    format: data.format,
    day_auto_exposure: data.day.auto_exposure,
    day_exposure_ms: data.day.exposure_ms,
    day_auto_gain: data.day.auto_gain,
    day_gain: data.day.gain,
    night_auto_exposure: data.night.auto_exposure,
    night_exposure_ms: data.night.exposure_ms,
    night_auto_gain: data.night.auto_gain,
    night_gain: data.night.gain
  };
}

async function loadLatest() {
  latest.value = null;

  if (!selectedNodeId.value) return;

  try {
    latest.value = await requestJson(`/api/captures/latest?node_id=${encodeURIComponent(selectedNodeId.value)}`);
  } catch {
    latest.value = null;
  }
}

async function refreshDashboard() {
  loading.value = true;

  try {
    await loadNodes();
    await Promise.all([loadSettings(), loadLatest()]);
  } finally {
    loading.value = false;
  }
}

async function selectNode(nodeId) {
  selectedNodeId.value = nodeId;
  await Promise.all([loadSettings(), loadLatest()]);
}

async function deleteNode(nodeId) {
  await requestJson(`/api/nodes/${nodeId}`, { method: "DELETE" });

  if (selectedNodeId.value === nodeId) {
    selectedNodeId.value = null;
  }

  setMessage(`Deleted ${nodeId}`);
  await refreshDashboard();
}

function payloadValue(value) {
  return value === "" ? null : value;
}

async function saveSettings() {
  if (!selectedNodeId.value || !settings.value) return;

  const body = {};

  for (const field of fields) {
    body[field] = payloadValue(settings.value[field]);
  }

  if (!body.format) {
    body.format = "jpg";
  }

  const result = await requestJson(`/api/nodes/${selectedNodeId.value}/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });

  setMessage(result.node_notified ? "Settings saved and sent to node" : "Settings saved");
}

async function startCapture() {
  if (!selectedNodeId.value) return;

  const result = await requestJson(`/api/nodes/${selectedNodeId.value}/sequence/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}"
  });

  setMessage(`Started ${result.sequence_id}`);
}

async function stopCapture() {
  if (!selectedNodeId.value) return;

  await requestJson(`/api/nodes/${selectedNodeId.value}/sequence/stop`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}"
  });

  setMessage("Stop sent");
  window.setTimeout(loadLatest, 1000);
}

onMounted(() => {
  refreshDashboard().catch((error) => setMessage(error.message));
  window.setInterval(() => refreshDashboard().catch(() => {}), 10000);
});
</script>

<template>
  <div class="shell">
    <header class="topbar">
      <h1>SkyHub</h1>
      <a href="/docs">API docs</a>
    </header>

    <main class="layout">
      <aside class="panel nodes-panel">
        <h2>Nodes</h2>
        <div class="nodes">
          <template v-if="nodes.length">
            <div v-for="node in nodes" :key="node.node_id" class="node-wrap">
              <button
                class="node"
                :class="{ active: node.node_id === selectedNodeId }"
                type="button"
                @click="selectNode(node.node_id)"
              >
                <strong>{{ node.node_id }}</strong>
                <span class="status" :class="{ online: node.online }">
                  {{ node.online ? "online" : "offline" }}
                </span>
                <small>{{ node.last_message_type || "no messages yet" }}</small>
              </button>
              <button
                v-if="!node.online"
                class="delete-node"
                type="button"
                @click="deleteNode(node.node_id)"
              >
                Delete {{ node.node_id }}
              </button>
            </div>
          </template>
          <p v-else class="muted">No nodes yet.</p>
        </div>
      </aside>

      <div class="main-stack">
        <section class="panel">
          <h2>Control</h2>
          <div class="content">
            <div class="selected">
              Selected: {{ selectedNodeId || "none" }}
              <span v-if="selectedNode" class="status" :class="{ online: selectedNode.online }">
                {{ selectedNode.online ? "online" : "offline" }}
              </span>
            </div>
            <div class="actions">
              <button type="button" @click="refreshDashboard">Refresh</button>
              <button type="button" class="primary" :disabled="!selectedNodeId" @click="startCapture">
                Start
              </button>
              <button type="button" class="danger" :disabled="!selectedNodeId" @click="stopCapture">
                Stop
              </button>
            </div>
            <div class="message">{{ loading ? "Refreshing..." : message }}</div>
          </div>
        </section>

        <section class="panel">
          <h2>Settings</h2>
          <div class="content" v-if="settings">
            <div class="settings-grid">
              <label>
                Interval seconds
                <input v-model.number="settings.interval_seconds" type="number" min="1" />
              </label>
              <label>
                Width
                <input v-model.number="settings.width" type="number" min="1" />
              </label>
              <label>
                Height
                <input v-model.number="settings.height" type="number" min="1" />
              </label>
              <label>
                Format
                <input v-model="settings.format" />
              </label>
              <label class="check">
                <input v-model="settings.day_auto_exposure" type="checkbox" />
                Day auto exposure
              </label>
              <label>
                Day exposure ms
                <input v-model.number="settings.day_exposure_ms" type="number" min="1" />
              </label>
              <label class="check">
                <input v-model="settings.day_auto_gain" type="checkbox" />
                Day auto gain
              </label>
              <label>
                Day gain
                <input v-model.number="settings.day_gain" type="number" step="0.1" min="0" />
              </label>
              <label class="check">
                <input v-model="settings.night_auto_exposure" type="checkbox" />
                Night auto exposure
              </label>
              <label>
                Night exposure ms
                <input v-model.number="settings.night_exposure_ms" type="number" min="1" />
              </label>
              <label class="check">
                <input v-model="settings.night_auto_gain" type="checkbox" />
                Night auto gain
              </label>
              <label>
                Night gain
                <input v-model.number="settings.night_gain" type="number" step="0.1" min="0" />
              </label>
            </div>
            <button type="button" class="primary save" @click="saveSettings">
              Save Settings
            </button>
          </div>
          <div class="content muted" v-else>Select a node to edit settings.</div>
        </section>

        <section class="panel">
          <h2>Latest Capture</h2>
          <div class="content preview">
            <div v-if="latest" class="muted">
              {{ latest.archive_date }}/{{ latest.period }} -
              {{ latest.filename }} -
              {{ latest.size_bytes }} bytes
            </div>
            <div v-else class="muted">No captures for this node yet</div>
            <img v-if="latestUrl" :src="latestUrl" alt="Latest capture" />
          </div>
        </section>
      </div>
    </main>
  </div>
</template>
