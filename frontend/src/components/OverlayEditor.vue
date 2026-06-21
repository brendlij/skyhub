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

function previewText(entity) {
  if (entity.type === "datetime") return "2026-06-21 23:42:10";
  if (entity.type === "date") return "2026-06-21";
  if (entity.type === "time") return "23:42:10";
  if (entity.type === "period") return "NIGHT";
  if (entity.type === "node_id") return "pi5-hqcam";
  return entity.text || entity.label || "Custom text";
}

function entityStyle(entity) {
  const fontSize = Math.max(8, Number(entity.font_size) || 24) * previewRect.value.scale;
  const paddingX = Math.max(2, fontSize * 0.25);
  const paddingY = Math.max(1, fontSize * 0.18);
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
    padding: `${paddingY}px ${paddingX}px`,
    borderRadius: `${Math.max(2, fontSize * 0.18)}px`
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

function updateEntityPosition(event) {
  if (!draggingEntity.value || !stage.value) return;

  const rect = stage.value.getBoundingClientRect();
  const imageRect = previewRect.value;
  draggingEntity.value.x = Math.min(1, Math.max(0, (event.clientX - rect.left - imageRect.left) / imageRect.width));
  draggingEntity.value.y = Math.min(1, Math.max(0, (event.clientY - rect.top - imageRect.top) / imageRect.height));
}

function startDrag(entity, event) {
  draggingEntity.value = entity;
  updateEntityPosition(event);
  window.addEventListener("pointermove", updateEntityPosition);
  window.addEventListener("pointerup", stopDrag, { once: true });
}

function stopDrag() {
  window.removeEventListener("pointermove", updateEntityPosition);
  draggingEntity.value = null;
}

function addTextEntity() {
  props.overlays.entities.push({
    id: `text-${Date.now()}`,
    type: "text",
    label: "Custom text",
    enabled: true,
    x: 0.5,
    y: 0.5,
    anchor: "center",
    font_size: 28,
    color: "#ffffff",
    background: "#000000",
    background_opacity: 0.35,
    text: "SkyHub"
  });
}

function removeEntity(entityId) {
  const index = props.overlays.entities.findIndex((entity) => entity.id === entityId);

  if (index >= 0) {
    props.overlays.entities.splice(index, 1);
  }
}

onMounted(() => {
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
</script>

<template>
  <div class="overlay-editor">
    <div class="overlay-toolbar">
      <label class="check">
        <input v-model="overlays.enabled" type="checkbox" />
        Enable overlays on saved captures
      </label>
      <button type="button" @click="addTextEntity">Add Text</button>
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
        @pointerdown.prevent="startDrag(entity, $event)"
      >
        {{ previewText(entity) }}
      </button>
    </div>

    <div class="overlay-list">
      <section v-for="entity in overlays.entities" :key="entity.id" class="overlay-row">
        <div class="overlay-row-head">
          <label class="check">
            <input v-model="entity.enabled" type="checkbox" />
            {{ entity.label || entity.type }}
          </label>
          <button v-if="entity.type === 'text'" type="button" @click="removeEntity(entity.id)">Remove</button>
        </div>
        <div class="overlay-grid">
          <label>
            Type
            <select v-model="entity.type">
              <option value="datetime">Date + time</option>
              <option value="date">Date</option>
              <option value="time">Time</option>
              <option value="period">Period</option>
              <option value="node_id">Node ID</option>
              <option value="text">Custom text</option>
            </select>
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
          <label v-if="entity.type === 'text'">
            Text
            <input v-model="entity.text" />
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
