<script setup>
import { captureUrl, formatCaptureName } from "../api/skyhub";

defineProps({
  captures: {
    type: Array,
    required: true
  }
});

defineEmits(["select"]);
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
      <img :src="captureUrl(capture)" alt="" loading="lazy" />
      <strong>{{ formatCaptureName(capture) }}</strong>
      <span>{{ capture.filename }}</span>
    </button>
  </div>
  <div v-else class="muted">No uploaded captures yet.</div>
</template>
