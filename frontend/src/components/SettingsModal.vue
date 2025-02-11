<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="isOpen" class="modal-overlay">
        <div class="modal-container" @click.stop>
          <button class="close-button absolute-close" @click="close" aria-label="Close settings">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
          <div class="modal-content">
            <div class="settings-layout">
              <!-- Left Panel - Inference Settings -->
              <div class="inference-panel">
                <h3>Inference Settings</h3>
                <div class="setting-item">
                  <label for="area">Area</label>
                  <select id="area" v-model="inferenceSettings.area">
                    <option value="wagga">Wagga Wagga</option>
                  </select>
                </div>
                <div class="setting-item">
                  <label for="window">Inference Window</label>
                  <select id="window" v-model="inferenceSettings.window">
                    <option value="24">24 Hours</option>
                    <option value="48">48 Hours</option>
                    <option value="72">72 Hours</option>
                  </select>
                </div>
                <div class="inference-buttons">
                  <button class="primary-button" @click="startInference">Start Inference</button>
                  <button class="secondary-button" @click="close">Cancel</button>
                </div>
              </div>

              <!-- Right Panel - Real-time Data -->
              <div class="map-settings-panel">
                <div class="settings-section">
                  <h3>Real-time Data</h3>
                  <div class="graph-container">
                    <div class="graph-item">
                      <div class="graph-header">
                        <h4>River Gauge</h4>
                        <span class="gauge-id">#410001</span>
                      </div>
                      <div class="graph-content">
                        <RiverGaugeChart :gauging-data="gaugingData" />
                      </div>
                    </div>
                    <div class="graph-item">
                      <h4>Rainfall Forecast</h4>
                      <div class="graph-placeholder">
                        <div class="graph-axis y-axis">
                          <span>50mm</span>
                          <span>40mm</span>
                          <span>30mm</span>
                          <span>20mm</span>
                          <span>10mm</span>
                          <span>0mm</span>
                        </div>
                        <div class="graph-content rainfall-forecast">
                          <!-- Placeholder for rainfall forecast graph -->
                          <div class="graph-bars">
                            <div class="bar" style="height: 40%"></div>
                            <div class="bar" style="height: 60%"></div>
                            <div class="bar" style="height: 30%"></div>
                            <div class="bar" style="height: 80%"></div>
                            <div class="bar" style="height: 20%"></div>
                          </div>
                        </div>
                        <div class="graph-axis x-axis">
                          <span>Day 1</span>
                          <span>Day 2</span>
                          <span>Day 3</span>
                          <span>Day 4</span>
                          <span>Day 5</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, defineProps, defineEmits, onMounted } from 'vue';
import RiverGaugeChart from './RiverGaugeChart.vue';
import { fetchGaugingData } from '../services/api.js';
import type { GaugingData } from '../services/api';

type Settings = {
  animationSpeed: string;
  mapStyle: string;
  showLegend: boolean;
  showCoordinates: boolean;
};

type InferenceSettings = {
  area: string;
  window: string;
};

const props = defineProps<{
  isOpen: boolean
}>();

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'update-settings', settings: Settings): void
  (e: 'start-inference', inferenceSettings: InferenceSettings): void
}>();

const settings = ref<Settings>({
  animationSpeed: '1',
  mapStyle: 'satellite',
  showLegend: true,
  showCoordinates: true
});

const inferenceSettings = ref<InferenceSettings>({
  area: 'wagga',
  window: '24'
});

const gaugingData = ref<GaugingData | null>(null);
const isLoading = ref(false);
const error = ref<string | null>(null);

const fetchGaugeData = async () => {
  isLoading.value = true;
  error.value = null;
  try {
    // Get date 7 days ago and format as dd-Mon-yyyy HH:mm
    const date = new Date();
    date.setDate(date.getDate() - 365);
    
    // Format the date components
    const day = date.getDate().toString().padStart(2, '0');
    const month = date.toLocaleString('en-US', { month: 'short' });
    const year = date.getFullYear();
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    
    const startDate = `${day}-${month}-${year} ${hours}:${minutes}`;

    gaugingData.value = await fetchGaugingData(startDate);
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to fetch gauge data';
    console.error('Error fetching gauge data:', e);
  } finally {
    isLoading.value = false;
  }
};

onMounted(() => {
  fetchGaugeData();
});

const close = () => {
  emit('close');
};

const saveSettings = () => {
  emit('update-settings', settings.value);
  close();
};

const startInference = () => {
  emit('start-inference', inferenceSettings.value);
  close();
};
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 2000;
  backdrop-filter: blur(4px);
}

.modal-container {
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-radius: 12px;
  width: 90%;
  max-width: 900px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
  position: relative;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.absolute-close {
  position: absolute;
  top: 0.75rem;
  right: 0.75rem;
  z-index: 10;
}

.modal-content {
  padding: 0;
}

.settings-layout {
  display: flex;
  min-height: 360px;
}

.inference-panel {
  flex: 1;
  padding: 1.5rem;
  background: rgba(249, 250, 251, 0.7);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border-right: 1px solid rgba(229, 231, 235, 0.4);
  display: flex;
  flex-direction: column;
}

.map-settings-panel {
  flex: 2;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.5);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.settings-section {
  margin-bottom: 2rem;
}

.settings-section h3 {
  font-size: 1rem;
  font-weight: 600;
  color: #374151;
  margin-bottom: 0.75rem;
}

.setting-item {
  margin-bottom: 1rem;
}

.setting-item label {
  display: block;
  font-size: 0.875rem;
  font-weight: 500;
  color: #4b5563;
  margin-bottom: 0.5rem;
}

.setting-item select {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid rgba(209, 213, 219, 0.4);
  border-radius: 6px;
  background-color: rgba(255, 255, 255, 0.9);
  font-size: 0.875rem;
  color: #1a1a1a;
  transition: all 0.2s;
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}

.setting-item select:focus {
  outline: none;
  border-color: rgba(37, 99, 235, 0.4);
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}

.checkbox-label input[type="checkbox"] {
  width: 1rem;
  height: 1rem;
  border-radius: 4px;
  border: 1px solid #d1d5db;
  cursor: pointer;
}

.inference-buttons {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.map-settings-footer {
  display: none;
}

.primary-button, .secondary-button {
  padding: 0.5rem 1rem;
  border-radius: 6px;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  width: 100%;
}

.primary-button {
  background: rgba(30, 61, 120, 0.9);
  color: white;
  border: none;
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}

.primary-button:hover {
  background: rgba(21, 44, 87, 0.95);
}

.secondary-button {
  background: rgba(255, 255, 255, 0.7);
  color: #4b5563;
  border: 1px solid rgba(209, 213, 219, 0.4);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}

.secondary-button:hover {
  background: rgba(243, 244, 246, 0.8);
}

.close-button {
  background: transparent;
  border: none;
  padding: 0.5rem;
  cursor: pointer;
  color: rgba(107, 114, 128, 0.8);
  border-radius: 6px;
  transition: all 0.2s;
}

.close-button:hover {
  background: rgba(243, 244, 246, 0.3);
  color: rgba(26, 26, 26, 0.9);
}

/* Transition animations */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.graph-container {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.graph-item {
  background: rgba(255, 255, 255, 0.7);
  border-radius: 8px;
  padding: 0.75rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.graph-item h4 {
  font-size: 0.875rem;
  font-weight: 600;
  color: #374151;
  margin: 0 0 0.75rem 0;
}

.graph-placeholder {
  display: flex;
  gap: 0.5rem;
  height: 140px;
  position: relative;
}

.graph-axis {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  font-size: 0.7rem;
  color: #6b7280;
}

.y-axis {
  padding-right: 0.5rem;
  border-right: 1px solid rgba(209, 213, 219, 0.4);
  width: 2.5rem;
}

.x-axis {
  position: absolute;
  bottom: -1.25rem;
  left: 3rem;
  right: 0;
  display: flex;
  justify-content: space-between;
  padding-top: 0.25rem;
  border-top: 1px solid rgba(209, 213, 219, 0.4);
  font-size: 0.7rem;
}

.graph-content {
  flex: 1;
  position: relative;
  padding: 0.5rem 0;
}

.river-gauge {
  background: linear-gradient(180deg, 
    rgba(30, 61, 120, 0.1) 0%,
    rgba(30, 61, 120, 0.05) 100%);
}

.graph-line {
  position: absolute;
  top: 50%;
  left: 0;
  right: 0;
  height: 2px;
  background: #1E3D78;
  opacity: 0.7;
  transform: translateY(-50%);
}

.rainfall-forecast .graph-bars {
  display: flex;
  justify-content: space-around;
  align-items: flex-end;
  height: 100%;
  padding: 0 1rem;
}

.rainfall-forecast .bar {
  width: 1.5rem;
  background: #1E3D78;
  opacity: 0.7;
  border-radius: 3px 3px 0 0;
  transition: height 0.3s ease;
}

.graph-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.gauge-id {
  font-size: 0.875rem;
  font-weight: 500;
  color: #4b5563;
}
</style> 