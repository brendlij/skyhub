<script setup>
defineProps({
  imageUrl: {
    type: String,
    default: null
  }
});
</script>

<template>
  <div class="image-frame">
    <img v-if="imageUrl" :src="imageUrl" alt="Latest capture" />
    <div v-else class="empty-preview">Waiting for the first uploaded capture.</div>
  </div>
</template>
