<script setup>
import OverlayEditor from "../components/OverlayEditor.vue";
import { useSkyHub } from "../composables/useSkyHub";

const {
  latestImageUrl,
  message,
  overlaySettings,
  saveOverlays,
  saveSettings,
  settings
} = useSkyHub();
</script>

<template>
  <main class="workspace">
    <section class="page-heading">
      <div>
        <h1>Settings</h1>
        <p>Server settings will live here too; node camera settings are active now.</p>
      </div>
    </section>

    <div class="settings-layout">
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
        <div class="content muted" v-else>Select a node to edit settings.</div>
      </section>

      <section class="panel">
        <h2>Overlays</h2>
        <div class="content" v-if="overlaySettings">
          <OverlayEditor :overlays="overlaySettings" :image-url="latestImageUrl" />
          <button type="button" class="primary save" @click="saveOverlays">
            Save Overlay Settings
          </button>
        </div>
        <div class="content muted" v-else>Select a node to edit overlays.</div>
      </section>

      <section class="panel">
        <h2>Server</h2>
        <div class="content server-placeholder">
          <strong>Coming next</strong>
          <p>Location, timezone, archive retention, and upload policy should be DB-backed server settings.</p>
        </div>
      </section>
    </div>
  </main>
</template>
