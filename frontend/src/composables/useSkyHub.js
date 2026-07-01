import { computed, ref } from "vue";
import { captureUrl, preloadImage, requestJson } from "../api/skyhub";

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
const latestImageUrl = ref(null);
const captures = ref([]);
const overlaySettings = ref(null);
const deviceSettings = ref(null);
const environmentTelemetry = ref(null);
const heaterState = ref(null);
const storageStats = ref(null);
const storageSettings = ref(null);
const message = ref("");
const loading = ref(false);
let initialized = false;
let dashboardSocket = null;
let reconnectTimer = null;
let captureLimit = 96;

const selectedNode = computed(() =>
  nodes.value.find((node) => node.node_id === selectedNodeId.value)
);

function setMessage(text) {
  message.value = text || "";
}

function settingsFromApi(data) {
  return {
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
    night_gain: data.night.gain,
    capture_enabled: data.capture_enabled,
    current_sequence_id: data.current_sequence_id
  };
}

function deviceSettingsFromApi(data) {
  return {
    ...data,
    devices: {
      environment: {
        driver: "bme280",
        interval_seconds: 30,
        bme280_i2c_bus: 1,
        bme280_i2c_address: "0x77",
        ...(data.devices?.environment || {})
      },
      heater: {
        driver: "gpiozero",
        gpio_pin: 23,
        active_high: true,
        mode: "manual",
        pwm: {
          enabled: false,
          duty_cycle: 1.0,
          ...(data.devices?.heater?.pwm || {})
        },
        ...(data.devices?.heater || {})
      }
    }
  };
}

function payloadValue(value) {
  return value === "" ? null : value;
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

  settings.value = settingsFromApi(
    await requestJson(`/api/nodes/${selectedNodeId.value}/settings`)
  );
}

async function loadOverlays() {
  if (!selectedNodeId.value) {
    overlaySettings.value = null;
    return;
  }

  overlaySettings.value = await requestJson(`/api/nodes/${selectedNodeId.value}/overlays`);
}

async function loadDeviceSettings() {
  if (!selectedNodeId.value) {
    deviceSettings.value = null;
    return;
  }

  deviceSettings.value = deviceSettingsFromApi(
    await requestJson(`/api/nodes/${selectedNodeId.value}/devices`)
  );
}

async function loadEnvironmentTelemetry() {
  if (!selectedNodeId.value) {
    environmentTelemetry.value = null;
    return;
  }

  try {
    environmentTelemetry.value = await requestJson(`/api/nodes/${selectedNodeId.value}/environment`);
  } catch {
    environmentTelemetry.value = null;
  }
}

async function loadHeaterState() {
  if (!selectedNodeId.value) {
    heaterState.value = null;
    return;
  }

  heaterState.value = await requestJson(`/api/nodes/${selectedNodeId.value}/heater`);
}

async function loadStorageStats() {
  storageStats.value = await requestJson("/api/storage");
}

async function loadStorageSettings() {
  storageSettings.value = await requestJson("/api/storage/settings");
}

async function loadLatest() {
  if (!selectedNodeId.value) {
    latest.value = null;
    latestImageUrl.value = null;
    return;
  }

  try {
    const nextLatest = await requestJson(`/api/captures/latest?node_id=${encodeURIComponent(selectedNodeId.value)}`);
    const currentKey = latest.value
      ? `${latest.value.node_id}/${latest.value.archive_date}/${latest.value.period}/${latest.value.filename}`
      : null;
    const nextKey = `${nextLatest.node_id}/${nextLatest.archive_date}/${nextLatest.period}/${nextLatest.filename}`;

    if (currentKey !== nextKey) {
      const nextUrl = captureUrl(nextLatest);
      await preloadImage(nextUrl);
      latest.value = nextLatest;
      latestImageUrl.value = nextUrl;
    }
  } catch {
    latest.value = null;
    latestImageUrl.value = null;
  }
}

async function loadCaptures(limit = 96) {
  if (!selectedNodeId.value) return;

  captureLimit = limit;
  const data = await requestJson(`/api/captures?node_id=${encodeURIComponent(selectedNodeId.value)}&limit=${limit}`);
  captures.value = data.captures;
}

async function refreshDashboard() {
  loading.value = true;

  try {
    await loadNodes();
    await Promise.all([
      loadSettings(),
      loadOverlays(),
      loadDeviceSettings(),
      loadEnvironmentTelemetry(),
      loadHeaterState(),
      loadLatest(),
      loadCaptures(captureLimit),
      loadStorageStats(),
      loadStorageSettings()
    ]);
  } finally {
    loading.value = false;
  }
}

async function selectNode(nodeId) {
  selectedNodeId.value = nodeId;
  await Promise.all([loadSettings(), loadOverlays(), loadDeviceSettings(), loadEnvironmentTelemetry(), loadHeaterState(), loadLatest(), loadCaptures(captureLimit)]);
}

async function deleteNode(nodeId) {
  await requestJson(`/api/nodes/${nodeId}`, { method: "DELETE" });

  if (selectedNodeId.value === nodeId) {
    selectedNodeId.value = null;
  }

  setMessage(`Deleted ${nodeId}`);
  await refreshDashboard();
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

  settings.value = settingsFromApi(result.settings);
  setMessage(result.node_notified ? "Settings saved and sent to node" : "Settings saved");
}

async function saveOverlays() {
  if (!selectedNodeId.value || !overlaySettings.value) return;

  overlaySettings.value = await requestJson(`/api/nodes/${selectedNodeId.value}/overlays`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      enabled: overlaySettings.value.enabled,
      entities: overlaySettings.value.entities
    })
  });
  setMessage("Overlay settings saved");
}

async function saveDeviceSettings() {
  if (!selectedNodeId.value || !deviceSettings.value) return;

  const result = await requestJson(`/api/nodes/${selectedNodeId.value}/devices`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      devices: deviceSettings.value.devices
    })
  });

  deviceSettings.value = deviceSettingsFromApi(result.device_settings);
  setMessage(result.node_notified ? "Device settings saved and sent to node" : "Device settings saved");
}

async function saveStorageSettings() {
  if (!storageSettings.value) return;

  const result = await requestJson("/api/storage/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      day_capture_enabled: storageSettings.value.day_capture_enabled,
      night_capture_enabled: storageSettings.value.night_capture_enabled,
      retention_days: storageSettings.value.retention_days || null,
      max_storage_gb: storageSettings.value.max_storage_gb || null
    })
  });

  storageSettings.value = result.storage_settings;
  await loadStorageStats();
  setMessage("Storage policy saved");
}

async function startCapture() {
  if (!selectedNodeId.value) return;

  const result = await requestJson(`/api/nodes/${selectedNodeId.value}/sequence/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}"
  });

  setMessage(result.status === "queued" ? "Capture queued for node" : `Started ${result.sequence_id}`);
  await loadSettings();
}

async function stopCapture() {
  if (!selectedNodeId.value) return;

  await requestJson(`/api/nodes/${selectedNodeId.value}/sequence/stop`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}"
  });

  setMessage("Stop sent");
  await loadSettings();
}

async function setHeaterEnabled(enabled) {
  if (!selectedNodeId.value) return;

  const result = await requestJson(`/api/nodes/${selectedNodeId.value}/heater`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled })
  });

  heaterState.value = result.heater;
  setMessage(result.node_notified ? "Heater updated" : "Heater setting saved");
}

function dashboardWebSocketUrl() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/dashboard`;
}

async function applyCaptureUploaded(event) {
  if (!event.capture || event.node_id !== selectedNodeId.value) return;

  const exists = captures.value.some((capture) => capture.path === event.capture.path);

  if (!exists) {
    captures.value = [event.capture, ...captures.value].slice(0, captureLimit);
  }

  const nextUrl = captureUrl(event.capture);

  try {
    await preloadImage(nextUrl);
    latest.value = event.capture;
    latestImageUrl.value = nextUrl;
  } catch {
    await loadLatest();
  }
}

function handleDashboardEvent(event) {
  if (event.type === "capture.uploaded") {
    applyCaptureUploaded(event).catch(() => {});
    loadStorageStats().catch(() => {});
    return;
  }

  if (event.type === "storage.settings.updated") {
    storageSettings.value = event.storage_settings;
    loadStorageStats().catch(() => {});
    return;
  }

  if (event.type === "settings.updated" && event.node_id === selectedNodeId.value) {
    settings.value = settingsFromApi(event.settings);
    return;
  }

  if (event.type === "overlay.updated" && event.node_id === selectedNodeId.value) {
    overlaySettings.value = event.overlays;
    return;
  }

  if (event.type === "device.settings.updated" && event.node_id === selectedNodeId.value) {
    deviceSettings.value = deviceSettingsFromApi(event.device_settings);
    return;
  }

  if (event.type === "device.configured" && event.node_id === selectedNodeId.value) {
    if (event.heater) heaterState.value = event.heater;
    return;
  }

  if (event.type === "capture.state.updated" && event.node_id === selectedNodeId.value) {
    loadSettings().catch(() => {});
    return;
  }

  if (event.type === "environment.updated" && event.node_id === selectedNodeId.value) {
    environmentTelemetry.value = event.telemetry;
    return;
  }

  if (event.type === "heater.updated" && event.node_id === selectedNodeId.value) {
    heaterState.value = event.heater;
    return;
  }

  if (event.type === "node.updated" || event.type === "node.deleted") {
    loadNodes().catch(() => {});
  }
}

function connectDashboardSocket() {
  if (dashboardSocket && dashboardSocket.readyState < WebSocket.CLOSING) return;

  dashboardSocket = new WebSocket(dashboardWebSocketUrl());

  dashboardSocket.onmessage = (socketEvent) => {
    try {
      handleDashboardEvent(JSON.parse(socketEvent.data));
    } catch {
      // Ignore malformed dashboard events.
    }
  };

  dashboardSocket.onclose = () => {
    dashboardSocket = null;

    if (reconnectTimer === null) {
      reconnectTimer = window.setTimeout(() => {
        reconnectTimer = null;
        connectDashboardSocket();
      }, 2000);
    }
  };
}

function ensureRealtimeRefresh() {
  if (initialized) return;

  initialized = true;

  refreshDashboard().catch((error) => setMessage(error.message));
  connectDashboardSocket();
}

export function useSkyHub() {
  ensureRealtimeRefresh();

  return {
    nodes,
    selectedNodeId,
    selectedNode,
    settings,
    latest,
    latestImageUrl,
    captures,
    overlaySettings,
    deviceSettings,
    environmentTelemetry,
    heaterState,
    storageStats,
    storageSettings,
    message,
    loading,
    captureUrl,
    deleteNode,
    loadCaptures,
    loadDeviceSettings,
    loadEnvironmentTelemetry,
    loadHeaterState,
    loadOverlays,
    loadStorageSettings,
    loadStorageStats,
    refreshDashboard,
    saveSettings,
    saveDeviceSettings,
    saveOverlays,
    saveStorageSettings,
    selectNode,
    setHeaterEnabled,
    setMessage,
    startCapture,
    stopCapture
  };
}
