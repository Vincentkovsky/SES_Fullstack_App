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
                    <div class="progress-header">
                      <h3>Inference Task Running</h3>
                      <div class="status-badge" :class="{
                        'status-running': currentInferenceTask.status === 'running',
                        'status-completed': currentInferenceTask.status === 'completed',
                        'status-failed': currentInferenceTask.status === 'failed',
                        'status-cancelled': currentInferenceTask.status === 'cancelled'
                      }">{{ inferenceStatusText }}</div>
                    </div>
                    
                    <div class="progress-info">
                      <div class="info-item">
                        <div class="info-label">Task ID:</div>
                        <div class="task-id-container">
                          <div class="task-id-value">{{ currentInferenceTask.taskId }}</div>
                        </div>
                      </div>
                      <div class="info-item">
                        <div class="info-label">Stage:</div>
                        <div class="info-value-container">
                          <div class="stage-badge">{{ currentInferenceTask.stage || 'Initializing' }}</div>
                        </div>
                      </div>
                      <div class="info-item">
                        <div class="info-label">Running time:</div>
                        <div class="info-value-container">
                          <div class="time-value">{{ formatElapsedTime(currentInferenceTask.elapsed) }}</div>
                        </div>
                      </div>
                    </div>
                    
                    <div class="progress-bar-container">
                      <div class="progress-bar">
                        <div 
                          class="progress-fill" 
                          :class="{ 'animated': currentInferenceTask.status === 'running' }"
                          :style="{ 
                            width: `${currentInferenceTask.progress || 0}%`,
                            background: getProgressBarColor(currentInferenceTask.stage, currentInferenceTask.status)
                          }"
                        ></div>
                      </div>
                      <div class="progress-text">{{ currentInferenceTask.progress || 0 }}%</div>
                    </div>
                    
                    <div class="progress-message">
                      <div class="message-icon">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                          <circle cx="12" cy="12" r="10"></circle>
                          <line x1="12" y1="16" x2="12" y2="12"></line>
                          <line x1="12" y1="8" x2="12.01" y2="8"></line>
                        </svg>
                      </div>
                      <div class="message-text">
                        {{ currentInferenceTask.message || 'Processing...' }}
                      </div>
                    </div>
                    
                    <div v-if="inferenceTaskError" class="error-message">
                      <div class="error-icon">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                          <circle cx="12" cy="12" r="10"></circle>
                          <line x1="12" y1="8" x2="12" y2="12"></line>
                          <line x1="12" y1="16" x2="12.01" y2="16"></line>
                        </svg>
                      </div>
                      <div class="error-text">{{ inferenceTaskError }}</div>
                    </div>
                    
                    <!-- 修改条件显示逻辑，在任务运行中时始终显示按钮 -->
                    <button v-if="inferenceTaskRunning && (currentInferenceTask.status === 'running' || currentInferenceTask.status === 'starting')" class="warning-button" @click="handleCancelInferenceTask">
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="cancel-icon">
                        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                        <line x1="9" y1="9" x2="15" y2="15"></line>
                        <line x1="15" y1="9" x2="9" y2="15"></line>
                      </svg>
                      Cancel Task
                    </button>
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
                            {{ "CUDA " + device.device_id + " - "+ device.device_name }} ({{ device.free_memory_gb.toFixed(1) }}GB Available)
                          </option>
                        </select>
                        <div v-if="cudaInfo.cuda_available && cudaInfo.devices.length > 0" class="device-utilization">
                          <div v-for="device in cudaInfo.devices" :key="`util-${device.device_id}`" class="device-stats">
                            <div class="device-name">CUDA {{ device.device_id }} - {{ device.device_name }}</div>
                            <div class="utilization-bar">
                              <div class="utilization-fill" :style="{ width: `${device.allocated_percent}%` }"></div>
                              <span class="utilization-text">{{ device.allocated_percent.toFixed(1) }}% used</span>
                            </div>
                          </div>
                        </div>
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
import { ref, computed, onMounted, watch, onBeforeUnmount } from 'vue';
import RiverGaugeChart from './RiverGaugeChart.vue';
import RainfallMap from './RainfallMap.vue';
import { fetchGaugingData, fetchHistoricalSimulations, fetchRainfallTilesList, getCudaInfo, getRainfallFiles, getInferenceTasksList, cancelInferenceTask } from '../services/api';
import type { GaugingData, CudaInfoResponse, RainfallFilesResponse, CudaDeviceInfo, RainfallFileInfo } from '../services/api';

// API配置常量
const API_HOST = import.meta.env.VITE_HOST || 'localhost';
const API_PORT = import.meta.env.VITE_BACKEND_PORT || 3000;

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
  progress: number;
  stage: string;
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
  progress: 0,
  stage: 'initialization',
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

// 格式化已运行时间，使用本地计时器
const formatElapsedTime = (seconds?: number): string => {
  // 优先使用本地计时器的值，如果任务正在运行
  const elapsedSeconds = inferenceTaskRunning.value ? localElapsedTime.value : (seconds || 0);
  
  const minutes = Math.floor(elapsedSeconds / 60);
  const remainingSeconds = Math.floor(elapsedSeconds % 60);
  
  if (minutes === 0) {
    return `${remainingSeconds} seconds`;
  }
  
  return `${minutes} min ${remainingSeconds} sec`;
};

// 获取进度条颜色
const getProgressBarColor = (stage?: string, status?: string): string => {
  if (status === 'failed') {
    return 'linear-gradient(to right, #ef4444, #b91c1c)';
  }
  
  if (status === 'cancelled') {
    return 'linear-gradient(to right, #f59e0b, #b45309)';
  }
  
  if (stage === 'reconnecting') {
    return 'linear-gradient(to right, #f59e0b, #b45309)';
  }
  
  return 'linear-gradient(to right, #1E3D78, #3663B0)';
};

const getDateFromTimestamp = (timestamp: string): Date | null => {
  const match = timestamp.match(/waterdepth_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})/);
  if (match) {
    const [_, year, month, day, hour, minute] = match;
    return new Date(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute));
  }
  return null;
};

// WebSocket connection for real-time progress tracking
let progressWebSocket: WebSocket | null = null;
let webSocketPingInterval: number | null = null;

// Connect to WebSocket for progress tracking
const connectProgressWebSocket = (taskId: string) => {
  if (!taskId) {
    console.error('Cannot connect WebSocket: Task ID is empty');
    return;
  }

  // 关闭现有连接（如果有）
  disconnectProgressWebSocket();
  
  // 构建与API配置一致的WebSocket URL
  const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const wsUrl = `${wsProtocol}://${API_HOST}:${API_PORT}/api/inference/ws/progress/${taskId}`;
  
  console.log(`Attempting to connect WebSocket at URL: ${wsUrl}`);
  
  try {
    progressWebSocket = new WebSocket(wsUrl);
    
    progressWebSocket.onopen = () => {
      console.log(`WebSocket successfully connected for task ${taskId}`);
      
      // Setup ping interval to keep connection alive
      if (webSocketPingInterval) {
        clearInterval(webSocketPingInterval);
      }
      
      webSocketPingInterval = window.setInterval(() => {
        if (progressWebSocket && progressWebSocket.readyState === WebSocket.OPEN) {
          progressWebSocket.send('ping');
          console.log('Ping sent to WebSocket server');
        } else {
          console.warn('Cannot send ping: WebSocket not open');
          // 尝试重新连接
          if (progressWebSocket && progressWebSocket.readyState !== WebSocket.OPEN) {
            console.log('Attempting to reconnect WebSocket...');
            connectProgressWebSocket(taskId);
          }
        }
      }, 30000); // Send ping every 30 seconds
    };
    
    progressWebSocket.onmessage = (event) => {
      console.log('WebSocket message received:', event.data);
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === 'pong') {
          console.log('Received pong response');
          return; // Ignore pong responses
        }
        
        // 当收到初始状态时，同步本地计时器
        if (data.elapsed_time && inferenceTaskRunning.value) {
          // 重新启动本地计时器，从服务器报告的时间开始
          startElapsedTimeCounter(data.elapsed_time);
        }
        
        // Update inference task status
        currentInferenceTask.value = {
          ...currentInferenceTask.value,
          status: data.status,
          progress: data.progress,
          stage: data.stage,
          message: data.message,
          elapsed: data.elapsed_time,
        };
        
        console.log('Updated task status:', currentInferenceTask.value);
        
        if (data.type === 'error') {
          inferenceTaskError.value = data.message;
          console.error('Inference task error from WebSocket:', data.message);
          stopElapsedTimeCounter(); // 错误时停止计时器
        }
        
        // 处理各种状态
        if (data.status === 'completed') {
          console.log('Task completed event from WebSocket');
          handleInferenceTaskCompleted({ taskId: data.task_id, results: data.results });
        } else if (data.status === 'failed') {
          console.error('Task failed event from WebSocket');
          inferenceTaskError.value = data.message;
          stopElapsedTimeCounter(); // 失败时停止计时器
        } else if (data.status === 'cancelled') {
          console.log('Task cancelled event from WebSocket');
          // 停止计时器
          stopElapsedTimeCounter();
          
          // 2秒后关闭模态框
          setTimeout(() => {
            inferenceTaskRunning.value = false;
            close();
          }, 2000);
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error, event.data);
      }
    };
    
    progressWebSocket.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
    
    progressWebSocket.onclose = (event) => {
      console.log(`WebSocket connection closed: code=${event.code}, reason=${event.reason}`);
      if (webSocketPingInterval) {
        clearInterval(webSocketPingInterval);
        webSocketPingInterval = null;
      }
      
      // 如果意外关闭且任务仍在运行，尝试重新连接
      if (event.code !== 1000 && event.code !== 1001 && inferenceTaskRunning.value) {
        console.log('Unexpected WebSocket close, attempting to reconnect...');
        setTimeout(() => {
          connectProgressWebSocket(taskId);
        }, 3000);
      }
    };
  } catch (error) {
    console.error('Error creating WebSocket connection:', error);
  }
};

// Disconnect WebSocket
const disconnectProgressWebSocket = () => {
  console.log('Disconnecting WebSocket');
  
  // 先清除ping间隔
  if (webSocketPingInterval) {
    console.log('Clearing WebSocket ping interval');
    clearInterval(webSocketPingInterval);
    webSocketPingInterval = null;
  }
  
  // 关闭WebSocket连接
  if (progressWebSocket) {
    // 移除所有事件监听器，防止意外重连
    progressWebSocket.onclose = null;
    progressWebSocket.onerror = null;
    progressWebSocket.onmessage = null;
    
    // 如果连接仍然打开，正常关闭它
    if (progressWebSocket.readyState === WebSocket.OPEN) {
      console.log('Closing open WebSocket connection');
      progressWebSocket.close(1000, 'Task completed or disconnected by user');
    }
    
    progressWebSocket = null;
    console.log('WebSocket connection nullified');
  }
};

// 处理推理任务事件
const handleInferenceTaskStarted = (data: { taskId: string; status: string; message: string }) => {
  console.log('Inference task started event received:', data);
  
  if (!data || !data.taskId) {
    console.error('Invalid task started data received:', data);
    return;
  }
  
  inferenceTaskRunning.value = true;
  inferenceTaskError.value = null;
  currentInferenceTask.value = {
    taskId: data.taskId,
    status: data.status || 'running',
    message: data.message || 'Starting inference...',
    progress: 0,
    stage: 'initialization',
    elapsed: 0
  };
  
  // 启动本地计时器
  startElapsedTimeCounter(0);
  
  console.log('Starting WebSocket connection for task:', data.taskId);
  // Connect to WebSocket for real-time progress updates
  connectProgressWebSocket(data.taskId);
};

const handleInferenceTaskProgress = (data: { 
  taskId: string; 
  status: string; 
  progress: number; 
  stage: string;
  message: string;
  elapsed: number; 
  results?: any 
}) => {
  console.log('Inference task progress event received:', data);
  
  if (!data || !data.taskId) {
    console.error('Invalid task progress data received:', data);
    return;
  }
  
  // 如果WebSocket未连接，尝试连接
  if (!progressWebSocket || progressWebSocket.readyState !== WebSocket.OPEN) {
    console.log('WebSocket not connected during progress update, reconnecting...');
    connectProgressWebSocket(data.taskId);
  }
  
  currentInferenceTask.value = {
    ...currentInferenceTask.value,
    ...data
  };
};

const handleInferenceTaskCompleted = (data: { taskId: string; results?: any }) => {
  console.log('Inference task completed event received:', data);
  
  if (!data || !data.taskId) {
    console.error('Invalid task completed data received:', data);
    return;
  }
  
  inferenceTaskRunning.value = false;
  currentInferenceTask.value = {
    ...currentInferenceTask.value,
    status: 'completed',
    progress: 100,
    elapsed: localElapsedTime.value // 保存最终运行时间
  };
  
  // 停止本地计时器
  stopElapsedTimeCounter();
  
  // 向 DeckGLMap 组件发送内部完成事件
  window.dispatchEvent(new CustomEvent('inference-task-completed-internal', { 
    detail: { 
      taskId: data.taskId,
      results: data.results
    } 
  }));
  
  // Disconnect WebSocket
  disconnectProgressWebSocket();
  
  // Close modal
  setTimeout(() => {
    if (inferenceTaskError.value === null) {
      close();
    }
  }, 1000);
};

const handleInferenceTaskError = (data: { error: string; taskId?: string }) => {
  console.error('Inference task error event received:', data);
  
  inferenceTaskError.value = data.error;
  
  // 向 DeckGLMap 组件发送内部错误事件
  if (data.taskId || currentInferenceTask.value.taskId) {
    window.dispatchEvent(new CustomEvent('inference-task-failed-internal', { 
      detail: { 
        taskId: data.taskId || currentInferenceTask.value.taskId,
        error: data.error
      } 
    }));
  }
  
  // Disconnect WebSocket only if the task is completed or failed
  if (currentInferenceTask.value.status !== 'running') {
    disconnectProgressWebSocket();
  }
};

// Data fetching functions
const fetchHistoricalSimulationsData = async () => {
  try {
    console.log('Fetching historical simulations...');
    // Store current selection
    const currentSimulation = selectedHistoricalSimulation.value;
    
    const data = await fetchHistoricalSimulations();
    historicalSimulations.value = data;
    console.log('Historical simulations fetched:', data);
    
    // Restore the selection if it exists in the new data
    if (currentSimulation && data.includes(currentSimulation)) {
      selectedHistoricalSimulation.value = currentSimulation;
    }
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
      // Store current device selection before updating
      const currentDeviceSelection = inferenceSettings.value.device;
      
      cudaInfo.value = response.data;
      console.log('CUDA information fetched:', response.data);
      
      // Only set the default device if it hasn't been set yet
      if (!currentDeviceSelection || currentDeviceSelection === '') {
        if (response.data.cuda_available && response.data.devices.length > 0) {
          inferenceSettings.value.device = `cuda:${response.data.devices[0].device_id}`;
        } else {
          inferenceSettings.value.device = 'cpu';
        }
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
    
    // Only reset to CPU if device hasn't been selected yet
    if (!inferenceSettings.value.device) {
      inferenceSettings.value.device = 'cpu';
    }
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
      // Store current selection before updating
      const currentRainfallFile = inferenceSettings.value.dataDir;
      
      rainfallFiles.value = response.data.rainfall_files;
      console.log('Rainfall files fetched:', response.data.rainfall_files);
      
      // Only set default rainfall file if none is selected yet
      if (!currentRainfallFile || currentRainfallFile === '') {
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

const startInference = async () => {
  try {
    // 验证必要的输入
    if (!inferenceSettings.value.dataDir) {
      inferenceTaskError.value = "Please select a rainfall data file";
      return;
    }
    
    console.log('Starting inference with settings:', inferenceSettings.value);
    
    // 设置初始状态
    inferenceTaskRunning.value = true;
    inferenceTaskError.value = null;
    currentInferenceTask.value = {
      taskId: 'pending',
      status: 'starting',
      progress: 0,
      stage: 'initialization',
      elapsed: 0,
      message: 'Starting inference task...'
    };
    
    // 调用 API 启动推理
    emit('start-inference', inferenceSettings.value);
    
    // 注意：WebSocket 连接将由事件处理程序在收到任务 ID 后建立
    console.log('Inference started, waiting for task ID...');
  } catch (error) {
    console.error('Error starting inference:', error);
    inferenceTaskError.value = error instanceof Error ? error.message : 'Failed to start inference';
    inferenceTaskRunning.value = false;
  }
};


// Data loading function
const loadData = async (preserveSelections = true) => {
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

// 添加检查运行中任务的函数
const checkRunningTasks = async () => {
  try {
    console.log('Checking for running inference tasks...');
    const response = await getInferenceTasksList();
    
    if (response.success && response.data.tasks.length > 0) {
      // 查找状态为 'running' 的任务
      const runningTask = response.data.tasks.find(task => task.status === 'running');
      
      if (runningTask) {
        console.log('Found running inference task:', runningTask);
        
        // 计算初始已运行时间
        const initialElapsedTime = runningTask.elapsed_time || (Date.now() / 1000 - runningTask.start_time);
        
        // 自动连接到这个任务的WebSocket并显示进度
        inferenceTaskRunning.value = true;
        inferenceTaskError.value = null;
        currentInferenceTask.value = {
          taskId: runningTask.task_id,
          status: runningTask.status,
          progress: 0, // 初始进度，将通过WebSocket更新
          stage: 'reconnecting',
          message: 'Reconnecting to running task...',
          elapsed: initialElapsedTime
        };
        
        // 启动本地计时器，从计算出的时间开始
        startElapsedTimeCounter(initialElapsedTime);
        
        // 连接WebSocket获取实时进度
        connectProgressWebSocket(runningTask.task_id);
        
        // 如果正在运行任务，强制切换到实时推理标签
        activeTab.value = 'live';
        return true;
      }
    }
    
    return false;
  } catch (error) {
    console.error('Error checking for running tasks:', error);
    return false;
  }
};

// 在 watch 函数中调用
watch(() => props.isOpen, async (isOpen) => {
  if (isOpen) {
    // 首先检查是否有正在运行的任务
    const hasRunningTask = await checkRunningTasks();
    
    // 如果没有正在运行的任务，正常加载数据
    if (!hasRunningTask) {
      await loadData();
    }
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

// 为了能正确移除事件监听器，声明事件处理函数引用
const inferenceTaskStartedHandler = ((e: CustomEvent) => {
  console.log('Received inference-task-started event:', e.detail);
  handleInferenceTaskStarted(e.detail);
}) as EventListener;

const inferenceTaskProgressHandler = ((e: CustomEvent) => {
  console.log('Received inference-task-progress event:', e.detail);
  handleInferenceTaskProgress(e.detail);
}) as EventListener;

const inferenceTaskCompletedHandler = ((e: CustomEvent) => {
  console.log('Received inference-task-completed event:', e.detail);
  handleInferenceTaskCompleted(e.detail);
}) as EventListener;

const inferenceTaskErrorHandler = ((e: CustomEvent) => {
  console.log('Received inference-task-error event:', e.detail);
  handleInferenceTaskError(e.detail);
}) as EventListener;

// Initial setup
onMounted(() => {
  // Set initial tab based on modelValue prop
  activeTab.value = props.modelValue ? 'live' : 'historical';
  
  if (props.isOpen) {
    loadData();
  }
  
  // 使用保存的函数引用添加事件监听器
  console.log('Setting up inference task event listeners');
  window.addEventListener('inference-task-started', inferenceTaskStartedHandler);
  window.addEventListener('inference-task-progress', inferenceTaskProgressHandler);
  window.addEventListener('inference-task-completed', inferenceTaskCompletedHandler);
  window.addEventListener('inference-task-error', inferenceTaskErrorHandler);
});

// 清理事件监听器
onBeforeUnmount(() => {
  console.log('Cleaning up event listeners and intervals');
  
  // Clear CUDA refresh interval
  if (cudaRefreshInterval !== null) {
    clearInterval(cudaRefreshInterval);
    cudaRefreshInterval = null;
  }
  
  // 停止计时器
  stopElapsedTimeCounter();
  
  // Disconnect WebSocket
  disconnectProgressWebSocket();
  
  // 使用保存的函数引用移除事件监听器
  window.removeEventListener('inference-task-started', inferenceTaskStartedHandler);
  window.removeEventListener('inference-task-progress', inferenceTaskProgressHandler);
  window.removeEventListener('inference-task-completed', inferenceTaskCompletedHandler);
  window.removeEventListener('inference-task-error', inferenceTaskErrorHandler);
});

// 添加取消推理任务的函数
const handleCancelInferenceTask = async () => {
  if (!currentInferenceTask.value.taskId) {
    console.error('Cannot cancel task: Task ID is empty');
    return;
  }
  
  try {
    console.log(`Attempting to cancel inference task ${currentInferenceTask.value.taskId}`);
    
    // 调用API取消任务
    const response = await cancelInferenceTask(currentInferenceTask.value.taskId);
    
    if (response.success) {
      console.log(`Task ${currentInferenceTask.value.taskId} cancelled successfully`);
      
      // 关闭WebSocket连接
      disconnectProgressWebSocket();
      
      // 停止计时器
      stopElapsedTimeCounter();
      
      // 更新UI状态
      currentInferenceTask.value = {
        ...currentInferenceTask.value,
        status: 'cancelled',
        stage: 'cancelled',
        message: 'Task cancelled by user',
        progress: currentInferenceTask.value.progress || 0
      };
      
      // 2秒后重置状态并关闭模态框
      setTimeout(() => {
        inferenceTaskRunning.value = false;
        close();
      }, 2000);
    } else {
      throw new Error(response.message || 'Failed to cancel task');
    }
  } catch (error) {
    console.error('Error cancelling inference task:', error);
    inferenceTaskError.value = error instanceof Error ? error.message : 'Failed to cancel inference task';
    
    // 即使出错也尝试断开连接并停止计时器
    disconnectProgressWebSocket();
    stopElapsedTimeCounter();
  }
};

// 添加计时器变量
let elapsedTimeInterval: number | null = null;
let localElapsedTime = ref(0);

// 启动本地计时器，每秒更新一次运行时间
const startElapsedTimeCounter = (initialElapsedTime: number = 0) => {
  // 清除现有计时器
  if (elapsedTimeInterval !== null) {
    clearInterval(elapsedTimeInterval);
    elapsedTimeInterval = null;
  }
  
  // 设置初始值
  localElapsedTime.value = initialElapsedTime;
  
  // 启动新的计时器，每秒递增
  elapsedTimeInterval = window.setInterval(() => {
    if (inferenceTaskRunning.value) {
      localElapsedTime.value += 1;
    } else {
      // 如果任务不再运行，停止计时器
      clearInterval(elapsedTimeInterval!);
      elapsedTimeInterval = null;
    }
  }, 1000);
};

// 停止计时器
const stopElapsedTimeCounter = () => {
  if (elapsedTimeInterval !== null) {
    clearInterval(elapsedTimeInterval);
    elapsedTimeInterval = null;
  }
};

// 在组件卸载时清理计时器
onBeforeUnmount(() => {
  // 清理计时器
  stopElapsedTimeCounter();
  
  // ...其他现有的清理代码
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
  padding: 1.25rem;
  background: rgba(249, 250, 251, 0.8);
  border-radius: 8px;
  margin-bottom: 1.5rem;
  border: 1px solid rgba(209, 213, 219, 0.4);
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  border-bottom: 1px solid rgba(209, 213, 219, 0.4);
  padding-bottom: 0.75rem;
}

.progress-header h3 {
  font-size: 1.125rem;
  font-weight: 600;
  color: #1E3D78;
  margin: 0;
}

.status-badge {
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 0.75rem;
  font-weight: 600;
  color: white;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.status-running {
  background: linear-gradient(to right, #1E3D78, #3663B0);
}

.status-completed {
  background: linear-gradient(to right, #10B981, #059669);
}

.status-failed {
  background: linear-gradient(to right, #EF4444, #B91C1C);
}

.status-cancelled {
  background: linear-gradient(to right, #F59E0B, #B45309);
}

.progress-info {
  margin-bottom: 1.25rem;
  background: rgba(255, 255, 255, 0.5);
  border-radius: 8px;
  padding: 1rem;
  border: 1px solid rgba(209, 213, 219, 0.3);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.info-item {
  margin-bottom: 0.75rem;
  display: flex;
  flex-direction: column;
}

.info-item:last-child {
  margin-bottom: 0;
}

.info-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: #6b7280;
  margin-bottom: 0.25rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.task-id-container {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.task-id-value {
  font-family: monospace;
  font-size: 0.875rem;
  color: #1f2937;
  background: rgba(243, 244, 246, 0.7);
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  border: 1px solid rgba(209, 213, 219, 0.5);
  white-space: normal;
  word-break: break-all;
  width: 100%;
  line-height: 1.4;
}

.info-value-container {
  display: flex;
  flex: 1;
  width: 100%;
}

.stage-badge {
  display: inline-block;
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  background: rgba(243, 244, 246, 0.7);
  color: #1f2937;
  font-size: 0.875rem;
  font-weight: 400;
  width: 100%;
  border: 1px solid rgba(209, 213, 219, 0.5);
  line-height: 1.4;
}

.time-value {
  font-weight: 400;
  color: #1f2937;
  background: rgba(243, 244, 246, 0.7);
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  border: 1px solid rgba(209, 213, 219, 0.5);
  width: 100%;
  font-size: 0.875rem;
  line-height: 1.4;
}

.progress-bar-container {
  margin-bottom: 1.25rem;
  position: relative;
  padding-top: 1rem;
}

.progress-bar {
  height: 10px;
  background: rgba(209, 213, 219, 0.4);
  border-radius: 5px;
  overflow: hidden;
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.1);
}

.progress-fill {
  height: 100%;
  border-radius: 5px;
  transition: width 0.3s ease;
}

.progress-text {
  position: absolute;
  right: 0;
  top: -5px;
  font-size: 0.875rem;
  font-weight: 600;
  color: #1E3D78;
}

.progress-message {
  margin-top: 1rem;
  display: flex;
  align-items: flex-start;
  background-color: rgba(243, 244, 246, 0.7);
  padding: 0.75rem;
  border-radius: 6px;
  border: 1px solid rgba(209, 213, 219, 0.4);
}

.message-icon {
  margin-right: 0.5rem;
  color: #6b7280;
  margin-top: 2px;
}

.message-text {
  font-size: 0.875rem;
  color: #1f2937;
  line-height: 1.4;
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
  display: flex;
  align-items: flex-start;
}

.error-icon {
  margin-right: 0.5rem;
  color: #B91C1C;
  margin-top: 2px;
}

.error-text {
  font-size: 0.875rem;
  color: #B91C1C;
  line-height: 1.4;
}

.warning-button {
  padding: 0.75rem 1rem;
  border-radius: 8px;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  width: 100%;
  margin-top: 1.25rem;
  background: linear-gradient(to right, #EF4444, #B91C1C);
  color: white;
  border: none;
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 4px rgba(239, 68, 68, 0.3);
}

.warning-button:hover {
  background: linear-gradient(to right, #DC2626, #991B1B);
  transform: translateY(-1px);
  box-shadow: 0 4px 6px rgba(239, 68, 68, 0.4);
}

.warning-button:active {
  transform: translateY(0);
  box-shadow: 0 1px 2px rgba(239, 68, 68, 0.3);
}

.cancel-icon {
  margin-right: 0.5rem;
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

/* 图表样式恢复 */
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