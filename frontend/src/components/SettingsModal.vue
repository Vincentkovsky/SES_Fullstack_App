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
              <!-- Left Panel - Settings with tabs -->
              <div class="inference-panel">
                <!-- Removed the panel-header with Inference Settings title -->
                
                <!-- Tabs for inference mode -->
                <div class="tabs">
                  <button 
                    class="tab-button" 
                    :class="{ active: activeTab === 'live' }"
                    @click="activeTab = 'live'"
                  >
                    Live Inference
                  </button>
                  <button 
                    class="tab-button" 
                    :class="{ active: activeTab === 'historical' }"
                    @click="activeTab = 'historical'"
                  >
                    Historical Floods
                  </button>
                </div>
                
                <!-- Live Tab Content -->
                <div v-if="activeTab === 'live'" class="tab-content">
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
                </div>
                
                <!-- Historical Tab Content -->
                <div v-if="activeTab === 'historical'" class="tab-content">
                  <div class="setting-item">
                    <label for="historical-simulation">Historical Floods</label>
                    <select id="historical-simulation" v-model="selectedHistoricalSimulation">
                      <option value="">Select a flood event</option>
                      <option v-for="simulation in historicalSimulations" :key="simulation" :value="simulation">
                        {{ simulation }}
                      </option>
                    </select>
                  </div>
                </div>
                
                <div class="inference-buttons">
                  <button class="primary-button" @click="activeTab === 'live' ? startInference() : loadHistoricalSimulation()">
                    Start Inference
                  </button>
                  <button class="secondary-button" @click="close">Cancel</button>
                </div>
              </div>

              <!-- Right Panel - Maps and Data -->
              <div class="map-settings-panel">
                <div class="settings-section">
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
                      <h4>Rainfall Data</h4>
                      <div class="graph-content">
                        <RainfallMap 
                          :timestamp="currentTimestamp"
                          :simulation="selectedHistoricalSimulation"
                        />
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
import { ref, defineProps, defineEmits, onMounted, watch, computed } from 'vue';
import RiverGaugeChart from './RiverGaugeChart.vue';
import RainfallMap from './RainfallMap.vue';
import { fetchGaugingData, fetchHistoricalSimulations, fetchRainfallTilesList } from '../services/api';
import type { GaugingData } from '../services/api';

// Types
type Settings = {
  animationSpeed: string;
  mapStyle: string;
  showLegend: boolean;
  showCoordinates: boolean;
  showRainfallLayer: boolean;
};

type InferenceSettings = {
  area: string;
  window: string;
};

// Props and Emits
const props = defineProps<{
  isOpen: boolean;
  timestamps: string[];
  modelValue?: boolean; // For mode (true = Live Mode, false = Local Mode)
}>();

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'update-settings', settings: Settings): void
  (e: 'start-inference', inferenceSettings: InferenceSettings): void
  (e: 'select-historical-simulation', simulation: string): void
  (e: 'update:modelValue', value: boolean): void
}>();

// State
const activeTab = ref('live'); // New state for active tab
const isLoading = ref(false);
const error = ref<string | null>(null);
const currentTimestamp = ref<string>('');
const historicalSimulations = ref<string[]>([]);
const selectedHistoricalSimulation = ref<string>('');
const gaugingData = ref<GaugingData | null>(null);
const rainfallData = ref<string[]>([]);
const hasRainfallData = ref(false);

const settings = ref<Settings>({
  animationSpeed: '1',
  mapStyle: 'satellite',
  showLegend: true,
  showCoordinates: true,
  showRainfallLayer: true
});

const inferenceSettings = ref<InferenceSettings>({
  area: 'wagga',
  window: '24'
});

// Utility functions
const formatDate = (date: Date): string => {
  const day = date.getDate().toString().padStart(2, '0');
  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const month = monthNames[date.getMonth()];
  const year = date.getFullYear();
  const hours = date.getHours().toString().padStart(2, '0');
  const minutes = date.getMinutes().toString().padStart(2, '0');
  
  return `${day}-${month}-${year} ${hours}:${minutes}`;
};

const getDateFromTimestamp = (timestamp: string): Date | null => {
  const match = timestamp.match(/waterdepth_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})/);
  if (match) {
    const [_, year, month, day, hour, minute] = match;
    return new Date(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute));
  }
  return null;
};

// Data fetching functions
const fetchHistoricalSimulationsData = async () => {
  try {
    console.log('Fetching historical simulations...');
    const data = await fetchHistoricalSimulations();
    historicalSimulations.value = data;
    console.log('Historical simulations fetched:', data);
  } catch (error) {
    console.error('Error fetching historical simulations:', error);
    throw error; // Re-throw to be handled by caller
  }
};

const fetchGaugeData = async (startDate: string, endDate: string) => {
  try {
    console.log('Fetching gauge data...', { startDate, endDate });
    const response = await fetchGaugingData(startDate, endDate);
    gaugingData.value = response;
    console.log('Gauge data fetched:', response);
  } catch (error) {
    console.error('Error fetching gauge data:', error);
    throw error; // Re-throw to be handled by caller
  }
};

// Computed properties
const hasRainfallDataForSelection = computed(() => {
  return rainfallData.value.length > 0;
});

// Action handlers
const loadHistoricalSimulation = async () => {
  if (selectedHistoricalSimulation.value) {
    try {
      // Check for rainfall data availability
      console.log(`Checking rainfall data for simulation ${selectedHistoricalSimulation.value}`);
      const rainfallTimestamps = await fetchRainfallTilesList(selectedHistoricalSimulation.value);
      hasRainfallData.value = rainfallTimestamps.length > 0;
      rainfallData.value = rainfallTimestamps;
      
      if (hasRainfallData.value) {
        console.log(`Loaded ${rainfallTimestamps.length} rainfall timestamps for simulation ${selectedHistoricalSimulation.value}`);
      } else {
        console.warn(`No rainfall timestamps found for simulation ${selectedHistoricalSimulation.value}`);
      }
    } catch (error) {
      console.warn(`Error checking rainfall data for simulation ${selectedHistoricalSimulation.value}:`, error);
      hasRainfallData.value = false;
      rainfallData.value = [];
    }
    
    // Emit the simulation selection
    emit('select-historical-simulation', selectedHistoricalSimulation.value);
    close();
  }
};

// When modelValue changes, update activeTab
watch(() => props.modelValue, (newValue) => {
  if (newValue !== undefined) {
    activeTab.value = newValue ? 'live' : 'historical';
  }
});

// Watch activeTab changes to emit update:modelValue
watch(() => activeTab.value, (newTab) => {
  emit('update:modelValue', newTab === 'live');
});

const close = () => {
  emit('close');
};

const startInference = () => {
  emit('start-inference', inferenceSettings.value);
  close();
};

// Add rainfall toggle function
const toggleRainfallLayer = () => {
  if (hasRainfallDataForSelection.value) {
    // Toggle the rainfall layer visibility
    emit('update-settings', {
      ...settings.value,
      showRainfallLayer: !settings.value.showRainfallLayer
    });
  }
};

// Data loading function
const loadData = async () => {
  isLoading.value = true;
  error.value = null;

  try {
    // Load historical simulations first
    await fetchHistoricalSimulationsData();

    // Only fetch gauge data if we have timestamps
    if (props.timestamps.length > 0) {
      const firstTimestamp = props.timestamps[0];
      const lastTimestamp = props.timestamps[props.timestamps.length - 1];
      

      const startDate = getDateFromTimestamp(firstTimestamp);
      const endDate = getDateFromTimestamp(lastTimestamp);
      
      if (startDate && endDate) {
        await fetchGaugeData(formatDate(startDate), formatDate(endDate));
      }
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load data';
    console.error('Error loading data:', e);
  } finally {
    isLoading.value = false;
  }
};

// Watchers
watch(() => props.isOpen, async (isOpen) => {
  if (isOpen) {
    await loadData();
  }
});

watch(() => selectedHistoricalSimulation.value, async (simulation) => {
  if (!simulation) return;

  try {
    isLoading.value = true;
    error.value = null;
    
    // Check for rainfall data availability
    try {
      console.log(`Checking rainfall data for simulation ${simulation}`);
      const rainfallTimestamps = await fetchRainfallTilesList(simulation);
      hasRainfallData.value = rainfallTimestamps.length > 0;
      rainfallData.value = rainfallTimestamps;
      
      if (hasRainfallData.value) {
        console.log(`Loaded ${rainfallTimestamps.length} rainfall timestamps for simulation ${simulation}`);
        currentTimestamp.value = rainfallTimestamps[0] || '';
      } else {
        console.warn(`No rainfall timestamps found for simulation ${simulation}`);
      }
    } catch (error) {
      console.warn(`Error checking rainfall data for simulation ${simulation}:`, error);
      hasRainfallData.value = false;
      rainfallData.value = [];
    }
    
    // Emit the selection first
    emit('select-historical-simulation', simulation);
    
    // Wait for timestamps to be updated
    await new Promise(resolve => setTimeout(resolve, 100));
    
    // Fetch gauge data based on the new timestamps
    if (props.timestamps.length > 0) {
      const firstTimestamp = props.timestamps[0];
      const lastTimestamp = props.timestamps[props.timestamps.length - 1];
      

      const startDate = getDateFromTimestamp(firstTimestamp);
      const endDate = getDateFromTimestamp(lastTimestamp);
      
      if (startDate && endDate) {
        await fetchGaugeData(formatDate(startDate), formatDate(endDate));
      }
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load simulation data';
    console.error('Error loading simulation data:', e);
  } finally {
    isLoading.value = false;
  }
});

// Initial setup
onMounted(() => {
  // Set initial tab based on modelValue prop
  activeTab.value = props.modelValue ? 'live' : 'historical';
  
  if (props.isOpen) {
    loadData();
  }
});
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

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.25rem;
}

/* New tab styles */
.tabs {
  display: flex;
  border-bottom: 1px solid rgba(209, 213, 219, 0.4);
  margin-bottom: 1.25rem;
  margin-top: 0.5rem;
}

.tab-button {
  padding: 0.5rem 1rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: #4b5563;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-button:hover {
  color: #1E3D78;
}

.tab-button.active {
  color: #1E3D78;
  border-bottom: 2px solid #1E3D78;
}

.tab-content {
  margin-bottom: 1.25rem;
}

.settings-layout {
  display: flex;
  min-height: 320px;
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
  gap: 1rem;
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
  margin: 0 0 0.5rem 0;
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

.rainfall-toggle-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.rainfall-toggle-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  font-size: 0.875rem;
  font-weight: 500;
  color: #4b5563;
}

.rainfall-toggle-button {
  padding: 4px 8px;
  border: none;
  border-radius: 4px;
  background: #e5e7eb;
  color: #4b5563;
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.rainfall-toggle-button.active {
  background: #1E3D78;
  color: white;
}

.rainfall-toggle-button:hover {
  opacity: 0.9;
}
</style> 