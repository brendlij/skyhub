<script setup>
import { computed, onBeforeUnmount, watch } from "vue";
import { captureUrl, formatCaptureName } from "../api/skyhub";

const props = defineProps({
  capture: {
    type: Object,
    default: null
  },
  hasPrevious: {
    type: Boolean,
    default: false
  },
  hasNext: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(["close", "previous", "next"]);

const imageUrl = computed(() => (props.capture ? captureUrl(props.capture) : null));

function handleKeydown(event) {
  if (!props.capture) return;

  if (event.key === "Escape") {
    emit("close");
  } else if (event.key === "ArrowLeft" && props.hasPrevious) {
    emit("previous");
  } else if (event.key === "ArrowRight" && props.hasNext) {
    emit("next");
  }
}

watch(
  () => props.capture,
  (capture) => {
    if (capture) {
      window.addEventListener("keydown", handleKeydown);
    } else {
      window.removeEventListener("keydown", handleKeydown);
    }
  },
  { immediate: true }
);

onBeforeUnmount(() => {
  window.removeEventListener("keydown", handleKeydown);
});
</script>

<template>
  <div v-if="capture" class="lightbox" role="dialog" aria-modal="true" @click.self="$emit('close')">
    <div class="lightbox-panel">
      <div class="lightbox-header">
        <div>
          <strong>{{ formatCaptureName(capture) }}</strong>
          <span>{{ capture.filename }}</span>
        </div>
        <div class="lightbox-actions">
          <button type="button" :disabled="!hasPrevious" @click="$emit('previous')">Prev</button>
          <button type="button" :disabled="!hasNext" @click="$emit('next')">Next</button>
          <button type="button" @click="$emit('close')">Close</button>
        </div>
      </div>
      <div class="lightbox-stage">
        <button
          class="lightbox-nav previous"
          type="button"
          :disabled="!hasPrevious"
          aria-label="Previous capture"
          @click="$emit('previous')"
        >
          ‹
        </button>
        <img
          :src="imageUrl"
          :width="capture.width || undefined"
          :height="capture.height || undefined"
          alt="Selected capture"
        />
        <button
          class="lightbox-nav next"
          type="button"
          :disabled="!hasNext"
          aria-label="Next capture"
          @click="$emit('next')"
        >
          ›
        </button>
      </div>
    </div>
  </div>
</template>
