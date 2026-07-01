<script setup>
import { computed, ref, watch } from "vue";
import CaptureGrid from "../components/CaptureGrid.vue";
import Lightbox from "../components/Lightbox.vue";
import { useSkyHub } from "../composables/useSkyHub";

const { captures, loadCaptures } = useSkyHub();
const selectedCapture = ref(null);
const selectedDate = ref(null);
const selectedPeriod = ref("night");

const sortedCaptures = computed(() => {
  return [...captures.value].sort((a, b) => {
    return String(b.modified_at || "").localeCompare(String(a.modified_at || ""));
  });
});

const dateGroups = computed(() => {
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

const selectedGroup = computed(() => (
  dateGroups.value.find((group) => group.archive_date === selectedDate.value) || null
));

const visibleCaptures = computed(() => {
  if (!selectedGroup.value) return [];

  return selectedGroup.value[selectedPeriod.value] || [];
});

const availablePeriodCounts = computed(() => ({
  night: selectedGroup.value?.night.length || 0,
  day: selectedGroup.value?.day.length || 0
}));

const selectedCaptureIndex = computed(() => {
  if (!selectedCapture.value) return -1;

  return visibleCaptures.value.findIndex((capture) => capture.path === selectedCapture.value.path);
});

const hasPreviousCapture = computed(() => selectedCaptureIndex.value > 0);
const hasNextCapture = computed(() => (
  selectedCaptureIndex.value >= 0 && selectedCaptureIndex.value < visibleCaptures.value.length - 1
));

function formatArchiveDate(archiveDate) {
  const date = new Date(`${archiveDate}T12:00:00`);

  return new Intl.DateTimeFormat(undefined, {
    weekday: "long",
    year: "numeric",
    month: "short",
    day: "numeric"
  }).format(date);
}

function openCapture(capture) {
  selectedCapture.value = capture;
}

function previousCapture() {
  if (!hasPreviousCapture.value) return;

  selectedCapture.value = visibleCaptures.value[selectedCaptureIndex.value - 1];
}

function nextCapture() {
  if (!hasNextCapture.value) return;

  selectedCapture.value = visibleCaptures.value[selectedCaptureIndex.value + 1];
}

function chooseDate(archiveDate) {
  selectedDate.value = archiveDate;
  selectedCapture.value = null;
}

function choosePeriod(period) {
  selectedPeriod.value = period;
  selectedCapture.value = null;
}

function refreshCaptures() {
  return loadCaptures(500);
}

watch(dateGroups, (groups) => {
  if (!groups.length) {
    selectedDate.value = null;
    return;
  }

  if (!selectedDate.value || !groups.some((group) => group.archive_date === selectedDate.value)) {
    selectedDate.value = groups[0].archive_date;
  }
}, { immediate: true });

watch(selectedGroup, (group) => {
  if (!group) return;

  if (!(group[selectedPeriod.value] || []).length) {
    selectedPeriod.value = group.night.length ? "night" : "day";
  }
}, { immediate: true });

refreshCaptures().catch(() => {});
</script>

<template>
  <main class="workspace">
    <section class="page-heading">
      <div>
        <h1>Captures</h1>
      </div>
      <div class="page-actions">
        <button type="button" @click="refreshCaptures">Refresh</button>
      </div>
    </section>

    <section v-if="dateGroups.length" class="capture-browser">
      <aside class="panel capture-date-panel">
        <h2>Dates</h2>
        <div class="capture-date-list">
          <button
            v-for="group in dateGroups"
            :key="group.archive_date"
            type="button"
            class="capture-date"
            :class="{ active: selectedDate === group.archive_date }"
            @click="chooseDate(group.archive_date)"
          >
            <strong>{{ formatArchiveDate(group.archive_date) }}</strong>
            <span>{{ group.archive_date }}</span>
            <small>{{ group.night.length }} night / {{ group.day.length }} day</small>
          </button>
        </div>
      </aside>

      <section class="panel capture-period-panel">
        <h2>{{ selectedDate ? formatArchiveDate(selectedDate) : "Captures" }}</h2>
        <div class="content period-stack">
          <div class="capture-period-toolbar">
            <div class="segmented">
              <button
                type="button"
                :class="{ active: selectedPeriod === 'night' }"
                :disabled="!availablePeriodCounts.night"
                @click="choosePeriod('night')"
              >
                Night {{ availablePeriodCounts.night }}
              </button>
              <button
                type="button"
                :class="{ active: selectedPeriod === 'day' }"
                :disabled="!availablePeriodCounts.day"
                @click="choosePeriod('day')"
              >
                Day {{ availablePeriodCounts.day }}
              </button>
            </div>
            <span class="muted">{{ visibleCaptures.length }} pictures</span>
          </div>

          <CaptureGrid :captures="visibleCaptures" @select="openCapture" />
        </div>
      </section>
    </section>
    <section v-else class="panel">
      <div class="content muted">No captures</div>
    </section>

    <Lightbox
      :capture="selectedCapture"
      :has-previous="hasPreviousCapture"
      :has-next="hasNextCapture"
      @close="selectedCapture = null"
      @previous="previousCapture"
      @next="nextCapture"
    />
  </main>
</template>
