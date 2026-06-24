<script setup>
import { RouterLink, RouterView } from "vue-router";
import { useSkyHub } from "./composables/useSkyHub";

const { nodes, selectedNode, selectedNodeId, selectNode } = useSkyHub();
</script>

<template>
  <div class="shell">
    <header class="topbar">
      <RouterLink class="brand" to="/monitor">
        <strong>SkyHub</strong>
      </RouterLink>

      <nav class="main-nav" aria-label="Main navigation">
        <RouterLink to="/monitor">Monitor</RouterLink>
        <RouterLink to="/captures">Captures</RouterLink>
        <RouterLink to="/overlays">Overlays</RouterLink>
        <RouterLink to="/settings">Settings</RouterLink>
        <RouterLink to="/nodes">Nodes</RouterLink>
      </nav>

      <div class="top-actions">
        <label v-if="nodes.length" class="node-select">
          Node
          <select v-model="selectedNodeId" @change="selectNode(selectedNodeId)">
            <option v-for="node in nodes" :key="node.node_id" :value="node.node_id">
              {{ node.node_id }}
            </option>
          </select>
        </label>
        <span v-if="selectedNode" class="status" :class="{ online: selectedNode.online }">
          {{ selectedNode.online ? "online" : "offline" }}
        </span>
      </div>
    </header>

    <RouterView />
  </div>
</template>
