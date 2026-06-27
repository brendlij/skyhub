<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({
  overlays: {
    type: Object,
    required: true
  },
  imageUrl: {
    type: String,
    default: null
  }
});

const draggingEntity = ref(null);
const dragOffset = ref({ x: 0, y: 0 });
const selectedEntityId = ref(null);
const stage = ref(null);
const previewImage = ref(null);
const previewRect = ref({
  left: 0,
  top: 0,
  width: 1,
  height: 1,
  scale: 1
});
let resizeObserver = null;

const enabledEntities = computed(() => props.overlays.entities || []);
const variables = [
  { token: "$capture.datetime", label: "Date time" },
  { token: "$capture.date", label: "Date" },
  { token: "$capture.time", label: "Time" },
  { token: "$capture.period", label: "Period" },
  { token: "$node.id", label: "Node" },
  { token: "$bme280.temperature", label: "Temp" },
  { token: "$bme280.humidity", label: "Humidity" },
  { token: "$bme280.pressure", label: "Pressure" },
  { token: "$bme280.dew_point", label: "Dew point" },
  { token: "$heater.state", label: "Heater" },
  { token: "$picamera2.state", label: "Camera" }
];

const previewValues = {
  "$capture.datetime": "2026-06-21 23:42:10",
  "$capture.date": "2026-06-21",
  "$capture.time": "23:42:10",
  "$capture.period": "NIGHT",
  "$node.id": "pi5-hqcam",
  "$node.node_id": "pi5-hqcam",
  "$bme280.temperature": "12.4",
  "$bme280.temperature_c": "12.4",
  "$bme280.humidity": "78",
  "$bme280.humidity_percent": "78",
  "$bme280.pressure": "1008",
  "$bme280.pressure_hpa": "1008",
  "$bme280.dew_point": "8.7",
  "$bme280.dew_point_c": "8.7",
  "$heater.state": "off",
  "$heater.actual": "off",
  "$heater.desired": "off",
  "$heater.gpio": "23",
  "$heater.driver": "gpiozero",
  "$picamera2.state": "capturing"
};

function legacyTemplate(entity) {
  if (entity.text) return entity.text;
  if (entity.type === "datetime") return "$capture.datetime";
  if (entity.type === "date") return "$capture.date";
  if (entity.type === "time") return "$capture.time";
  if (entity.type === "period") return "$capture.period";
  if (entity.type === "node_id") return "$node.id";
  return entity.label || "SkyHub";
}

function previewText(entity) {
  return legacyTemplate(entity).replace(/\$[A-Za-z][A-Za-z0-9_.]*/g, (token) => previewValues[token] ?? "");
}

function entityStyle(entity) {
  const nativeFontSize = Math.max(8, Number(entity.font_size) || 24);
  const nativePadding = Math.max(5, nativeFontSize * 0.22);
  const fontSize = nativeFontSize * previewRect.value.scale;
  const padding = nativePadding * previewRect.value.scale;
  const translateX = entity.anchor?.includes("right")
    ? "-100%"
    : entity.anchor === "center"
      ? "-50%"
      : "0";
  const translateY = entity.anchor?.includes("bottom")
    ? "-100%"
    : entity.anchor === "center"
      ? "-50%"
      : "0";

  return {
    left: `${previewRect.value.left + (entity.x || 0) * previewRect.value.width}px`,
    top: `${previewRect.value.top + (entity.y || 0) * previewRect.value.height}px`,
    transform: `translate(${translateX}, ${translateY})`,
    color: entity.color,
    background: hexWithOpacity(entity.background, entity.background_opacity),
    fontSize: `${fontSize}px`,
    padding: `${padding}px`,
    borderRadius: `${Math.max(4, nativePadding) * previewRect.value.scale}px`
  };
}

function updatePreviewRect() {
  if (!stage.value) return;

  const stageRect = stage.value.getBoundingClientRect();
  const image = previewImage.value;

  if (!image?.naturalWidth || !image?.naturalHeight) {
    previewRect.value = {
      left: 0,
      top: 0,
      width: stageRect.width || 1,
      height: stageRect.height || 1,
      scale: 1
    };
    return;
  }

  const imageAspect = image.naturalWidth / image.naturalHeight;
  const stageAspect = stageRect.width / stageRect.height;
  let width = stageRect.width;
  let height = stageRect.height;
  let left = 0;
  let top = 0;

  if (stageAspect > imageAspect) {
    width = stageRect.height * imageAspect;
    left = (stageRect.width - width) / 2;
  } else {
    height = stageRect.width / imageAspect;
    top = (stageRect.height - height) / 2;
  }

  previewRect.value = {
    left,
    top,
    width,
    height,
    scale: width / image.naturalWidth
  };
}

function hexWithOpacity(hex, opacity) {
  const value = String(hex || "#000000").replace("#", "");
  const red = parseInt(value.slice(0, 2), 16) || 0;
  const green = parseInt(value.slice(2, 4), 16) || 0;
  const blue = parseInt(value.slice(4, 6), 16) || 0;
  return `rgba(${red}, ${green}, ${blue}, ${Number(opacity ?? 0.35)})`;
}

function pointerToImagePosition(event) {
  if (!draggingEntity.value || !stage.value) return;

  const rect = stage.value.getBoundingClientRect();
  const imageRect = previewRect.value;

  if (!imageRect.width || !imageRect.height) return;

  return {
    x: (event.clientX - rect.left - imageRect.left) / imageRect.width,
    y: (event.clientY - rect.top - imageRect.top) / imageRect.height
  };
}

function updateEntityPosition(event) {
  if (!draggingEntity.value) return;

  const pointer = pointerToImagePosition(event);

  if (!pointer) return;

  draggingEntity.value.x = Math.min(1, Math.max(0, pointer.x - dragOffset.value.x));
  draggingEntity.value.y = Math.min(1, Math.max(0, pointer.y - dragOffset.value.y));
}

function startDrag(entity, event) {
  draggingEntity.value = entity;
  const pointer = pointerToImagePosition(event);

  dragOffset.value = pointer
    ? {
        x: pointer.x - (Number(entity.x) || 0),
        y: pointer.y - (Number(entity.y) || 0)
      }
    : { x: 0, y: 0 };
  event.currentTarget?.setPointerCapture?.(event.pointerId);
  window.addEventListener("pointermove", updateEntityPosition);
  window.addEventListener("pointerup", stopDrag, { once: true });
}

function stopDrag() {
  window.removeEventListener("pointermove", updateEntityPosition);
  draggingEntity.value = null;
  dragOffset.value = { x: 0, y: 0 };
}

function addTextEntity() {
  const entity = {
    id: `text-${Date.now()}`,
    type: "text",
    label: "Overlay",
    enabled: true,
    x: 0.5,
    y: 0.5,
    anchor: "center",
    font_size: 28,
    color: "#ffffff",
    background: "#000000",
    background_opacity: 0.35,
    text: "$capture.datetime"
  };

  props.overlays.entities.push(entity);
  selectedEntityId.value = entity.id;
}

function removeEntity(entityId) {
  const index = props.overlays.entities.findIndex((entity) => entity.id === entityId);

  if (index >= 0) {
    props.overlays.entities.splice(index, 1);
  }

  if (selectedEntityId.value === entityId) {
    selectedEntityId.value = props.overlays.entities[0]?.id || null;
  }
}

function selectEntity(entity) {
  selectedEntityId.value = entity.id;
  entity.type = "text";
  entity.text = legacyTemplate(entity);
}

function selectedEntity() {
  return props.overlays.entities.find((entity) => entity.id === selectedEntityId.value) || props.overlays.entities[0];
}

function insertVariable(token) {
  let entity = selectedEntity();

  if (!entity) {
    addTextEntity();
    entity = selectedEntity();
  }

  if (!entity) return;

  selectEntity(entity);
  entity.text = [entity.text || "", token].filter(Boolean).join(" ");
}

function normalizeEntities() {
  for (const entity of props.overlays.entities || []) {
    entity.type = "text";
    entity.text = legacyTemplate(entity);
    entity.label = entity.label || "Overlay";
  }

  if (!selectedEntityId.value && props.overlays.entities?.length) {
    selectedEntityId.value = props.overlays.entities[0].id;
  }
}

onMounted(() => {
  normalizeEntities();
  updatePreviewRect();

  if (stage.value && "ResizeObserver" in window) {
    resizeObserver = new ResizeObserver(updatePreviewRect);
    resizeObserver.observe(stage.value);
  } else {
    window.addEventListener("resize", updatePreviewRect);
  }
});

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  window.removeEventListener("resize", updatePreviewRect);
  window.removeEventListener("pointermove", updateEntityPosition);
});

watch(() => props.imageUrl, () => {
  requestAnimationFrame(updatePreviewRect);
});

watch(() => props.overlays.entities, normalizeEntities, { immediate: true });
</script>

<template>
  <div class="overlay-editor">
    <div class="overlay-toolbar">
      <label class="check">
        <input v-model="overlays.enabled" type="checkbox" />
        Enable overlays on saved captures
      </label>
      <button type="button" @click="addTextEntity">Add Overlay</button>
    </div>

    <div class="overlay-variables">
      <button
        v-for="variable in variables"
        :key="variable.token"
        type="button"
        @click="insertVariable(variable.token)"
      >
        {{ variable.label }}
      </button>
    </div>

    <div ref="stage" class="overlay-stage">
      <img v-if="imageUrl" ref="previewImage" :src="imageUrl" alt="" @load="updatePreviewRect" />
      <div v-else class="overlay-placeholder">Preview uses the latest capture when one exists.</div>
      <button
        v-for="entity in enabledEntities"
        v-show="entity.enabled"
        :key="entity.id"
        class="overlay-entity"
        type="button"
        :style="entityStyle(entity)"
        @pointerdown.prevent="selectEntity(entity); startDrag(entity, $event)"
      >
        {{ previewText(entity) }}
      </button>
    </div>

    <div class="overlay-list">
      <section
        v-for="entity in overlays.entities"
        :key="entity.id"
        class="overlay-row"
        :class="{ active: entity.id === selectedEntityId }"
        @focusin="selectEntity(entity)"
        @click="selectEntity(entity)"
      >
        <div class="overlay-row-head">
          <label class="check">
            <input v-model="entity.enabled" type="checkbox" />
            {{ entity.label || entity.type }}
          </label>
          <button type="button" @click="removeEntity(entity.id)">Remove</button>
        </div>
        <div class="overlay-grid">
          <label>
            Name
            <input v-model="entity.label" @focus="selectEntity(entity)" />
          </label>
          <label>
            Anchor
            <select v-model="entity.anchor">
              <option value="top-left">Top left</option>
              <option value="top-right">Top right</option>
              <option value="bottom-left">Bottom left</option>
              <option value="bottom-right">Bottom right</option>
              <option value="center">Center</option>
            </select>
          </label>
          <label class="overlay-template">
            Template
            <textarea
              v-model="entity.text"
              rows="2"
              placeholder="$capture.datetime  $bme280.temperature C"
              @focus="selectEntity(entity)"
            />
          </label>
          <label>
            Size
            <input v-model.number="entity.font_size" type="number" min="8" max="160" />
          </label>
          <label>
            Text color
            <input v-model="entity.color" type="color" />
          </label>
          <label>
            Background
            <input v-model="entity.background" type="color" />
          </label>
          <label>
            Background opacity
            <input v-model.number="entity.background_opacity" type="number" min="0" max="1" step="0.05" />
          </label>
        </div>
      </section>
    </div>
  </div>
</template>
