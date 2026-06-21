<script setup>
import { computed, ref } from "vue";
import CaptureGrid from "../components/CaptureGrid.vue";
import CaptureTable from "../components/CaptureTable.vue";
import Lightbox from "../components/Lightbox.vue";
import { useSkyHub } from "../composables/useSkyHub";

const { captures, loadCaptures } = useSkyHub();
const selectedCapture = ref(null);
const viewMode = ref("grid");
const sortKey = ref("modified_at");
const sortDirection = ref("desc");

const sortedCaptures = computed(() => {
  const direction = sortDirection.value === "asc" ? 1 : -1;

  return [...captures.value].sort((a, b) => {
    const aValue = a[sortKey.value] ?? "";
    const bValue = b[sortKey.value] ?? "";

    if (sortKey.value === "size_bytes") {
      return ((Number(aValue) || 0) - (Number(bValue) || 0)) * direction;
    }

    return String(aValue).localeCompare(String(bValue)) * direction;
  });
});

const groupedCaptures = computed(() => {
  const groups = new Map();

  for (const capture of sortedCaptures.value) {
    const dateGroup = groups.get(capture.archive_date) || {
      archive_date: capture.archive_date,
      day: [],
      night: []
    };

    dateGroup[capture.period]?.push(capture);
    groups.set(capture.archive_date, dateGroup);
  }

  return [...groups.values()].sort((a, b) => b.archive_date.localeCompare(a.archive_date));
});

function openCapture(capture) {
  selectedCapture.value = capture;
}

function setSort(nextSortKey) {
  if (sortKey.value === nextSortKey) {
    sortDirection.value = sortDirection.value === "asc" ? "desc" : "asc";
    return;
  }

  sortKey.value = nextSortKey;
  sortDirection.value = "desc";
}

loadCaptures().catch(() => {});
</script>

<template>
  <main class="workspace">
    <section class="page-heading">
      <div>
        <h1>Capture Explorer</h1>
        <p>Browse uploaded captures by archive date and day/night period.</p>
      </div>
      <div class="page-actions">
        <div class="segmented">
          <button type="button" :class="{ active: viewMode === 'grid' }" @click="viewMode = 'grid'">
            Grid
          </button>
          <button type="button" :class="{ active: viewMode === 'table' }" @click="viewMode = 'table'">
            Table
          </button>
        </div>
        <button type="button" @click="loadCaptures">Refresh</button>
      </div>
    </section>

    <div v-if="viewMode === 'table' && captures.length" class="panel">
      <div class="table-tools">
        <span class="muted">{{ captures.length }} captures</span>
        <div class="actions compact">
          <button type="button" @click="setSort('modified_at')">
            Time {{ sortKey === "modified_at" ? sortDirection : "" }}
          </button>
          <button type="button" @click="setSort('period')">
            Period {{ sortKey === "period" ? sortDirection : "" }}
          </button>
          <button type="button" @click="setSort('size_bytes')">
            Size {{ sortKey === "size_bytes" ? sortDirection : "" }}
          </button>
        </div>
      </div>
      <CaptureTable :captures="sortedCaptures" @select="openCapture" />
    </div>

    <div v-else-if="groupedCaptures.length" class="day-stack">
      <section v-for="group in groupedCaptures" :key="group.archive_date" class="panel">
        <h2>{{ group.archive_date }}</h2>
        <div class="content period-stack">
          <section v-if="group.night.length">
            <h3>Night</h3>
            <CaptureGrid :captures="group.night" @select="openCapture" />
          </section>
          <section v-if="group.day.length">
            <h3>Day</h3>
            <CaptureGrid :captures="group.day" @select="openCapture" />
          </section>
        </div>
      </section>
    </div>
    <section v-else class="panel">
      <div class="content muted">No uploaded captures yet.</div>
    </section>

    <Lightbox :capture="selectedCapture" @close="selectedCapture = null" />
  </main>
</template>
