<script setup>
import { captureUrl, formatCaptureName } from "../api/skyhub";

defineProps({
  captures: {
    type: Array,
    required: true
  }
});

defineEmits(["select"]);

function imageStyle(capture) {
  if (!capture.width || !capture.height) return {};

  return {
    aspectRatio: `${capture.width} / ${capture.height}`
  };
}
</script>

<template>
  <div v-if="captures.length" class="capture-grid">
    <button
      v-for="capture in captures"
      :key="capture.path"
      class="capture-tile"
      type="button"
      @click="$emit('select', capture)"
    >
      <img :src="captureUrl(capture, { thumb: true })" :style="imageStyle(capture)" alt="" loading="lazy" />
      <strong>{{ formatCaptureName(capture) }}</strong>
      <small v-if="capture.width && capture.height">{{ capture.width }} x {{ capture.height }}</small>
      <span>{{ capture.filename }}</span>
    </button>
  </div>
  <div v-else class="muted">No uploaded captures yet.</div>
</template>
