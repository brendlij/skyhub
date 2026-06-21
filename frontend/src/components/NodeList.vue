<script setup>
defineProps({
  nodes: {
    type: Array,
    required: true
  },
  selectedNodeId: {
    type: String,
    default: null
  }
});

defineEmits(["select", "delete"]);
</script>

<template>
  <div class="nodes">
    <template v-if="nodes.length">
      <div v-for="node in nodes" :key="node.node_id" class="node-wrap">
        <button
          class="node"
          :class="{ active: node.node_id === selectedNodeId }"
          type="button"
          @click="$emit('select', node.node_id)"
        >
          <strong>{{ node.node_id }}</strong>
          <span class="status" :class="{ online: node.online }">
            {{ node.online ? "online" : "offline" }}
          </span>
          <small>{{ node.last_message_type || "no messages yet" }}</small>
        </button>
        <button
          v-if="!node.online"
          class="delete-node"
          type="button"
          @click="$emit('delete', node.node_id)"
        >
          Delete {{ node.node_id }}
        </button>
      </div>
    </template>
    <p v-else class="muted">No nodes yet.</p>
  </div>
</template>
