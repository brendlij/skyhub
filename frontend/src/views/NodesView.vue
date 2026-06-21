<script setup>
import NodeList from "../components/NodeList.vue";
import { useSkyHub } from "../composables/useSkyHub";

const { deleteNode, nodes, selectedNodeId, selectNode } = useSkyHub();
</script>

<template>
  <main class="workspace">
    <section class="page-heading">
      <div>
        <h1>Nodes</h1>
        <p>Connected and remembered camera nodes.</p>
      </div>
    </section>

    <section class="panel">
      <h2>Camera Nodes</h2>
      <NodeList
        :nodes="nodes"
        :selected-node-id="selectedNodeId"
        @select="selectNode"
        @delete="deleteNode"
      />
    </section>
  </main>
</template>
