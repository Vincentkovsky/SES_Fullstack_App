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
                <!-- Panel content container -->
                <div class="panel-content">
                  <!-- Removed the panel-header with Inference Settings title -->
                  
                  <!-- Inference Progress Section -->
                  <div v-if="inferenceTaskRunning" class="inference-progress-container">
                    <h3>Inference Task Running</h3>
                    <div class="progress-info">
                      <p>Task ID: {{ currentInferenceTask.taskId }}</p>
                      <p>Status: {{ inferenceStatusText }}</p>
                      <p>Running time: {{ formatElapsedTime(currentInferenceTask.elapsed) }}</p>
                    </div>
                    <div class="progress-bar-container">
                      <div class="progress-bar">
                        <div 
                          class="progress-fill" 
                          :style="{ 
                            width: inferenceTaskRunning ? '100%' : '0%',
                            animation: inferenceTaskRunning ? 'progress-animation 2s infinite' : 'none'
                          }"
                        ></div>
                      </div>
                    </div>
                    <div v-if="inferenceTaskError" class="error-message">
                      {{ inferenceTaskError }}
                    </div>
                  </div>
                  
                  <!-- Tabs for inference mode (hidden when task is running) -->
                  <div v-if="!inferenceTaskRunning">
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
                      
                      <!-- CUDA Device Dropdown -->
                      <div class="setting-item">
                        <label for="cuda-device">Inference Device</label>
                        <select id="cuda-device" v-model="inferenceSettings.device" :disabled="!cudaInfo.cuda_available">
                          <option v-if="!cudaInfo.cuda_available" value="cpu">CPU (CUDA not available)</option>
                          <option v-else value="cpu">CPU</option>
                          <option 
                            v-for="device in cudaInfo.devices" 
                            :key="device.device_id" 
                            :value="`cuda:${device.device_id}`"
                          >
                            {{ "CUDA:" + device.device_id + " - "+ device.device_name }} ({{ device.free_memory_gb.toFixed(1) }}GB free)
                          </option>
                        </select>
                        <div v-if="cudaInfo.cuda_available && cudaInfo.devices.length > 0" class="device-utilization">
                          <div v-for="device in cudaInfo.devices" :key="`util-${device.device_id}`" class="device-stats">
                            <div class="device-name">CUDA: {{ device.device_id }}: {{ device.device_name }}</div>
                            <div class="utilization-bar">
                              <div class="utilization-fill" :style="{ width: `${device.allocated_percent}%` }"></div>
                              <span class="utilization-text">{{ device.allocated_percent.toFixed(1) }}% used</span>
                            </div>
                          </div>
                        </div>
                        <div v-if="isLoadingCudaInfo" class="loading-indicator">Loading CUDA information...</div>
                      </div>
                      
                      <!-- Rainfall Data Files Dropdown -->
                      <div class="setting-item">
                        <label for="rainfall-file">Rainfall Data</label>
                        <select id="rainfall-file" v-model="inferenceSettings.dataDir">
                          <option value="">Select a rainfall data file</option>
                          <option 
                            v-for="file in rainfallFiles" 
                            :key="file.name" 
                            :value="file.name"
                          >
                            {{ file.name }} ({{ file.size_mb.toFixed(1) }} MB)
                          </option>
                        </select>
                        <div v-if="isLoadingRainfallFiles" class="loading-indicator">Loading rainfall files...</div>
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
                  </div>
                </div>
                
                <!-- Fixed buttons at the bottom -->
                <div v-if="!inferenceTaskRunning" class="inference-buttons-fixed">
                  <button class="primary-button" @click="activeTab === 'live' ? startInference() : loadHistoricalSimulation()">
                    {{ activeTab === 'live' ? 'Start Inference' : 'Load Simulation' }}
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
import { ref, defineProps, defineEmits, onMounted, watch, computed, onBeforeUnmount } from 'vue';
import RiverGaugeChart from './RiverGaugeChart.vue';
import RainfallMap from './RainfallMap.vue';
import { fetchGaugingData, fetchHistoricalSimulations, fetchRainfallTilesList, getCudaInfo, getRainfallFiles } from '../services/api';
import type { GaugingData, CudaInfoResponse, RainfallFilesResponse, CudaDeviceInfo, RainfallFileInfo } from '../services/api';

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
  device: string;
  dataDir: string;
};

// 推理任务状态接口
interface InferenceTaskStatus {
  taskId: string;
  status: string;
  message?: string;
  elapsed?: number;
  results?: any;
  error?: string;
}

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

// CUDA information state
const isLoadingCudaInfo = ref(false);
const cudaInfo = ref<{
  cuda_available: boolean;
  device_count: number;
  devices: CudaDeviceInfo[];
  current_device: number | null;
}>({
  cuda_available: false,
  device_count: 0,
  devices: [],
  current_device: null
});

// Rainfall files state
const isLoadingRainfallFiles = ref(false);
const rainfallFiles = ref<RainfallFileInfo[]>([]);

// 推理任务状态
const inferenceTaskRunning = ref(false);
const currentInferenceTask = ref<InferenceTaskStatus>({
  taskId: '',
  status: '',
  elapsed: 0
});
const inferenceTaskError = ref<string | null>(null);

const settings = ref<Settings>({
  animationSpeed: '1',
  mapStyle: 'satellite',
  showLegend: true,
  showCoordinates: true,
  showRainfallLayer: true
});

const inferenceSettings = ref<InferenceSettings>({
  area: 'wagga',
  window: '24',
  device: 'cpu',
  dataDir: ''
});

// 计算属性：推理状态文本
const inferenceStatusText = computed(() => {
  switch (currentInferenceTask.value.status) {
    case 'running':
      return 'Running';
    case 'completed':
      return 'Completed';
    case 'failed':
      return 'Failed';
    default:
      return currentInferenceTask.value.status || 'Unknown';
  }
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

// 格式化已运行时间
const formatElapsedTime = (seconds?: number): string => {
  if (seconds === undefined) return '0s';
  
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.floor(seconds % 60);
  
  if (minutes === 0) {
    return `${remainingSeconds} seconds`;
  }
  
  return `${minutes} min ${remainingSeconds} sec`;
};

const getDateFromTimestamp = (timestamp: string): Date | null => {
  const match = timestamp.match(/waterdepth_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})/);
  if (match) {
    const [_, year, month, day, hour, minute] = match;
    return new Date(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute));
  }
  return null;
};

// 处理推理任务事件
const handleInferenceTaskStarted = (data: { taskId: string; status: string; message: string }) => {
  inferenceTaskRunning.value = true;
  inferenceTaskError.value = null;
  currentInferenceTask.value = {
    taskId: data.taskId,
    status: data.status,
    message: data.message,
    elapsed: 0
  };
  console.log('Inference task started:', data);
};

const handleInferenceTaskProgress = (data: { taskId: string; status: string; elapsed: number; results?: any }) => {
  currentInferenceTask.value = {
    ...currentInferenceTask.value,
    ...data
  };
  console.log('Inference task progress update:', data);
};

const handleInferenceTaskCompleted = (data: { taskId: string }) => {
  inferenceTaskRunning.value = false;
  console.log('Inference task completed:', data);
  
  // Close modal
  setTimeout(() => {
    if (inferenceTaskError.value === null) {
      close();
    }
  }, 1000);
};

const handleInferenceTaskError = (data: { error: string }) => {
  inferenceTaskError.value = data.error;
  console.error('Inference task error:', data.error);
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

// New function to fetch CUDA information
const fetchCudaInfo = async () => {
  try {
    isLoadingCudaInfo.value = true;
    console.log('Fetching CUDA information...');
    const response = await getCudaInfo();
    
    if (response.success) {
      cudaInfo.value = response.data;
      console.log('CUDA information fetched:', response.data);
      
      // If CUDA is available, set the default device to the first CUDA device
      if (response.data.cuda_available && response.data.devices.length > 0) {
        inferenceSettings.value.device = `cuda:${response.data.devices[0].device_id}`;
      } else {
        inferenceSettings.value.device = 'cpu';
      }
    }
  } catch (error) {
    console.error('Error fetching CUDA information:', error);
    cudaInfo.value = {
      cuda_available: false,
      device_count: 0,
      devices: [],
      current_device: null
    };
    inferenceSettings.value.device = 'cpu';
  } finally {
    isLoadingCudaInfo.value = false;
  }
};

// New function to fetch rainfall files
const fetchRainfallFiles = async () => {
  try {
    isLoadingRainfallFiles.value = true;
    console.log('Fetching rainfall files...');
    const response = await getRainfallFiles();
    
    if (response.success) {
      rainfallFiles.value = response.data.rainfall_files;
      console.log('Rainfall files fetched:', response.data.rainfall_files);
      
      // Set default rainfall file if available
      if (response.data.rainfall_files.length > 0) {
        // Look for a file with name starting with 'rainfall_'
        const defaultFile = response.data.rainfall_files.find(file => 
          file.name.startsWith('rainfall_'));
        
        if (defaultFile) {
          inferenceSettings.value.dataDir = defaultFile.name;
        } else {
          inferenceSettings.value.dataDir = response.data.rainfall_files[0].name;
        }
      }
    }
  } catch (error) {
    console.error('Error fetching rainfall files:', error);
    rainfallFiles.value = [];
  } finally {
    isLoadingRainfallFiles.value = false;
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
  // 注意：不要关闭模态框，以便显示推理进度
  // close() 将由任务完成事件处理器调用
};


// Data loading function
const loadData = async () => {
  isLoading.value = true;
  error.value = null;

  try {
    // Load historical simulations first
    await fetchHistoricalSimulationsData();

    // Fetch CUDA information
    await fetchCudaInfo();
    
    // Fetch rainfall files
    await fetchRainfallFiles();

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

// Periodically refresh CUDA information when the modal is open and the Live tab is active
let cudaRefreshInterval: number | null = null;

// Setup auto-refresh for CUDA info when modal is open and in 'live' tab
watch([() => props.isOpen, () => activeTab.value], ([isOpen, tab]) => {
  // Clear any existing interval
  if (cudaRefreshInterval !== null) {
    clearInterval(cudaRefreshInterval);
    cudaRefreshInterval = null;
  }
  
  // If modal is open and on the live tab, set up auto-refresh
  if (isOpen && tab === 'live') {
    // Refresh every 5 seconds
    cudaRefreshInterval = window.setInterval(() => {
      fetchCudaInfo();
    }, 5000);
  }
}, { immediate: true });

// Initial setup
onMounted(() => {
  // Set initial tab based on modelValue prop
  activeTab.value = props.modelValue ? 'live' : 'historical';
  
  if (props.isOpen) {
    loadData();
  }
  
  // 设置全局事件监听器，用于接收来自DeckGLMap的推理任务事件
  window.addEventListener('inference-task-started', (e: any) => handleInferenceTaskStarted(e.detail));
  window.addEventListener('inference-task-progress', (e: any) => handleInferenceTaskProgress(e.detail));
  window.addEventListener('inference-task-completed', (e: any) => handleInferenceTaskCompleted(e.detail));
  window.addEventListener('inference-task-error', (e: any) => handleInferenceTaskError(e.detail));
});

// 清理事件监听器
onBeforeUnmount(() => {
  // Clear CUDA refresh interval
  if (cudaRefreshInterval !== null) {
    clearInterval(cudaRefreshInterval);
    cudaRefreshInterval = null;
  }
  
  window.removeEventListener('inference-task-started', (e: any) => handleInferenceTaskStarted(e.detail));
  window.removeEventListener('inference-task-progress', (e: any) => handleInferenceTaskProgress(e.detail));
  window.removeEventListener('inference-task-completed', (e: any) => handleInferenceTaskCompleted(e.detail));
  window.removeEventListener('inference-task-error', (e: any) => handleInferenceTaskError(e.detail));
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
  display: flex;
  flex-direction: column;
  background: rgba(249, 250, 251, 0.7);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border-right: 1px solid rgba(229, 231, 235, 0.4);
}

.panel-content {
  flex: 1;
  padding: 1.5rem;
  overflow-y: auto;
}

.inference-buttons-fixed {
  padding: 1rem;
  background: rgba(249, 250, 251, 0.9);
  border-top: 1px solid rgba(229, 231, 235, 0.4);
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-top: auto;
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

/* Inference progress styles */
.inference-progress-container {
  padding: 1rem;
  background: rgba(249, 250, 251, 0.8);
  border-radius: 8px;
  margin-bottom: 1.5rem;
  border: 1px solid rgba(209, 213, 219, 0.4);
}

.inference-progress-container h3 {
  font-size: 1rem;
  font-weight: 600;
  color: #1E3D78;
  margin-bottom: 1rem;
}

.progress-info {
  margin-bottom: 1rem;
}

.progress-info p {
  margin: 0.25rem 0;
  font-size: 0.875rem;
  color: #4b5563;
}

.progress-bar-container {
  margin-bottom: 1rem;
}

.progress-bar {
  height: 6px;
  background: rgba(209, 213, 219, 0.4);
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #1E3D78;
  border-radius: 3px;
  transition: width 0.3s ease;
}

@keyframes progress-animation {
  0% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0% 50%;
  }
}

.progress-fill.animated {
  background: linear-gradient(to right, #1E3D78, #3663B0, #1E3D78);
  background-size: 200% 200%;
  animation: progress-animation 2s infinite;
}

.error-message {
  padding: 0.75rem;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #B91C1C;
  font-size: 0.875rem;
  border-radius: 6px;
  margin-top: 1rem;
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

/* Device utilization styles */
.device-utilization {
  margin-top: 10px;
  padding: 8px;
  background: rgba(249, 250, 251, 0.7);
  border-radius: 6px;
  border: 1px solid rgba(209, 213, 219, 0.4);
}

.device-stats {
  margin-bottom: 8px;
}

.device-stats:last-child {
  margin-bottom: 0;
}

.device-name {
  font-size: 0.8rem;
  font-weight: 500;
  margin-bottom: 4px;
  color: #4b5563;
}

.utilization-bar {
  height: 8px;
  background: rgba(229, 231, 235, 0.6);
  border-radius: 4px;
  overflow: hidden;
  position: relative;
}

.utilization-fill {
  height: 100%;
  background: linear-gradient(to right, #1E3D78, #3663B0);
  border-radius: 4px;
  transition: width 0.3s ease;
}

.utilization-text {
  position: absolute;
  right: 4px;
  top: -16px;
  font-size: 0.7rem;
  color: #4b5563;
}

.loading-indicator {
  margin-top: 4px;
  font-size: 0.8rem;
  color: #6b7280;
  font-style: italic;
}
</style> 