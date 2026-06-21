<script setup>
import { computed } from "vue";
import { captureUrl, formatCaptureName } from "../api/skyhub";

const props = defineProps({
  capture: {
    type: Object,
    default: null
  }
});

defineEmits(["close"]);

const imageUrl = computed(() => (props.capture ? captureUrl(props.capture) : null));
</script>

<template>
  <div v-if="capture" class="lightbox" role="dialog" aria-modal="true" @click.self="$emit('close')">
    <div class="lightbox-panel">
      <div class="lightbox-header">
        <div>
          <strong>{{ formatCaptureName(capture) }}</strong>
          <span>{{ capture.filename }}</span>
        </div>
        <button type="button" @click="$emit('close')">Close</button>
      </div>
      <img :src="imageUrl" alt="Selected capture" />
    </div>
  </div>
</template>
