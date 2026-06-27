<script setup>
import { formatBytes } from "../api/skyhub";
import { useSkyHub } from "../composables/useSkyHub";

const {
  heaterState,
  message,
  saveSettings,
  setHeaterEnabled,
  settings,
  storageStats
} = useSkyHub();
</script>

<template>
  <main class="workspace">
    <section class="page-heading">
      <div>
        <h1>Settings</h1>
      </div>
    </section>

    <div class="settings-layout settings-layout-compact">
      <section class="panel">
        <h2>Node Camera</h2>
        <div class="content" v-if="settings">
          <div class="settings-grid">
            <label>
              Interval seconds
              <input v-model.number="settings.interval_seconds" type="number" min="1" />
            </label>
            <label>
              Width
              <input v-model.number="settings.width" type="number" min="1" />
            </label>
            <label>
              Height
              <input v-model.number="settings.height" type="number" min="1" />
            </label>
            <label>
              Format
              <input v-model="settings.format" />
            </label>
          </div>

          <div class="settings-section">
            <h3>Day</h3>
            <div class="settings-grid">
              <label class="check">
                <input v-model="settings.day_auto_exposure" type="checkbox" />
                Auto exposure
              </label>
              <label>
                Exposure ms
                <input v-model.number="settings.day_exposure_ms" type="number" min="1" />
              </label>
              <label class="check">
                <input v-model="settings.day_auto_gain" type="checkbox" />
                Auto gain
              </label>
              <label>
                Gain
                <input v-model.number="settings.day_gain" type="number" step="0.1" min="0" />
              </label>
            </div>
          </div>

          <div class="settings-section">
            <h3>Night</h3>
            <div class="settings-grid">
              <label class="check">
                <input v-model="settings.night_auto_exposure" type="checkbox" />
                Auto exposure
              </label>
              <label>
                Exposure ms
                <input v-model.number="settings.night_exposure_ms" type="number" min="1" />
              </label>
              <label class="check">
                <input v-model="settings.night_auto_gain" type="checkbox" />
                Auto gain
              </label>
              <label>
                Gain
                <input v-model.number="settings.night_gain" type="number" step="0.1" min="0" />
              </label>
            </div>
          </div>

          <button type="button" class="primary save" @click="saveSettings">
            Save Node Settings
          </button>
          <div class="message">{{ message }}</div>
        </div>
        <div class="content muted" v-else>No node selected</div>
      </section>

      <section class="panel">
        <h2>Manual Heater</h2>
        <div class="content server-placeholder">
          <div v-if="heaterState" class="storage-grid">
            <div>
              <span>Desired</span>
              <strong>{{ heaterState.desired_enabled ? "On" : "Off" }}</strong>
            </div>
            <div>
              <span>Actual</span>
              <strong>{{ heaterState.actual_enabled ? "On" : "Off" }}</strong>
            </div>
            <div>
              <span>Driver</span>
              <strong>{{ heaterState.driver || "-" }}</strong>
            </div>
            <div>
              <span>GPIO</span>
              <strong>{{ heaterState.gpio_pin || "-" }}</strong>
            </div>
          </div>
          <div class="actions">
            <button type="button" class="primary" :disabled="!heaterState" @click="setHeaterEnabled(true)">
              Turn on
            </button>
            <button type="button" :disabled="!heaterState" @click="setHeaterEnabled(false)">
              Turn off
            </button>
          </div>
        </div>
      </section>

      <section class="panel">
        <h2>Storage</h2>
        <div class="content server-placeholder">
          <div v-if="storageStats" class="storage-grid">
            <div>
              <span>Captures</span>
              <strong>{{ formatBytes(storageStats.captures_bytes) }}</strong>
            </div>
            <div>
              <span>Database</span>
              <strong>{{ formatBytes(storageStats.database_bytes) }}</strong>
            </div>
            <div>
              <span>Thumbnails</span>
              <strong>{{ formatBytes(storageStats.thumbnails_bytes) }}</strong>
            </div>
            <div>
              <span>Data total</span>
              <strong>{{ formatBytes(storageStats.data_bytes) }}</strong>
            </div>
            <div>
              <span>Disk free</span>
              <strong>{{ formatBytes(storageStats.disk_free_bytes) }}</strong>
            </div>
          </div>
          <p v-if="storageStats">{{ storageStats.data_dir }}</p>
        </div>
      </section>
    </div>
  </main>
</template>
