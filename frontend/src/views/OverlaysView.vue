<script setup>
import { computed } from "vue";
import OverlayEditor from "../components/OverlayEditor.vue";
import { captureUrl } from "../api/skyhub";
import { useSkyHub } from "../composables/useSkyHub";

const {
  latest,
  message,
  overlaySettings,
  saveOverlays
} = useSkyHub();

const rawPreviewUrl = computed(() => (
  latest.value ? captureUrl(latest.value, { raw: true }) : null
));
</script>

<template>
  <main class="workspace">
    <section class="page-heading">
      <div>
        <h1>Overlays</h1>
      </div>
      <button
        type="button"
        class="primary"
        :disabled="!overlaySettings"
        @click="saveOverlays"
      >
        Save
      </button>
    </section>

    <section class="panel">
      <h2>Editor</h2>
      <div class="content" v-if="overlaySettings">
        <OverlayEditor :overlays="overlaySettings" :image-url="rawPreviewUrl" />
        <div class="message">{{ message }}</div>
      </div>
      <div class="content muted" v-else>No node selected</div>
    </section>
  </main>
</template>
