<script setup>
import {
  captureUrl,
  formatBytes,
  formatCaptureName,
  formatDateTime
} from "../api/skyhub";

defineProps({
  captures: {
    type: Array,
    required: true
  }
});

defineEmits(["select"]);
</script>

<template>
  <div v-if="captures.length" class="capture-table-wrap">
    <table class="capture-table">
      <thead>
        <tr>
          <th>Preview</th>
          <th>Capture</th>
          <th>Time</th>
          <th>Node</th>
          <th>Period</th>
          <th>Size</th>
          <th>Filename</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="capture in captures" :key="capture.path">
          <td>
            <button class="table-preview" type="button" @click="$emit('select', capture)">
              <img :src="captureUrl(capture)" alt="" loading="lazy" />
            </button>
          </td>
          <td>
            <strong>{{ formatCaptureName(capture) }}</strong>
          </td>
          <td>{{ formatDateTime(capture.modified_at) }}</td>
          <td>{{ capture.node_id }}</td>
          <td>
            <span class="period-pill">{{ capture.period }}</span>
          </td>
          <td>{{ formatBytes(capture.size_bytes) }}</td>
          <td class="filename-cell">{{ capture.filename }}</td>
          <td>
            <button type="button" @click="$emit('select', capture)">Open</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
  <div v-else class="muted">No uploaded captures yet.</div>
</template>
