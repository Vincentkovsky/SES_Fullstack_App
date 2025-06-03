<template>
  <div class="map-container">
    <SettingsModal 
      :is-open="isSettingsOpen" 
      :timestamps="timestamps"
      @close="isSettingsOpen = false"
      @update-settings="handleSettingsUpdate"
      @start-inference="handleInferenceStart"
      @select-historical-simulation="handleHistoricalSimulation"
    />
    <div ref="mapContainer" style="width: 100%; height: 100vh;"></div>
    <div class="map-controls">
      <MapZoomControls
        class="panel-button"
        @zoom-in="zoomIn"
        @zoom-out="zoomOut"
      />
      <MapSettingsControl
        class="panel-button"
        @toggle-settings="toggleSettings"
      />
      <MapLayerControls
        class="panel-button"
        :is-flood-layer-active="isFloodLayerActive"
        :is-weather-layer-active="isWeatherLayerActive"
        @toggle-flood="toggleFloodLayer"
        @toggle-weather="toggleWeatherLayer"
      />
    </div>
    <div class="legend" :class="{ 'hidden': !isLegendVisible }">
      <div class="legend-title">{{ isWeatherLayerActive ? 'Rainfall' : 'Flood' }}</div>
      <div class="legend-gradient">
        <div class="legend-content">
          <div v-if="!isWeatherLayerActive" class="gradient-bar flood-gradient"></div>
          <div v-if="!isWeatherLayerActive" class="gradient-labels flood-labels">
            <span>10m</span>
            <span>5m</span>
            <span>2m</span>
            <span>1m</span>
            <span>0m</span>
          </div>
          
          <div v-if="isWeatherLayerActive" class="gradient-bar rainfall-gradient"></div>
          <div v-if="isWeatherLayerActive" class="gradient-labels rainfall-labels">
            <span>45mm</span>
            <span>30mm</span>
            <span>15mm</span>
            <span>5mm</span>
            <span>1mm</span>
          </div>
        </div>
      </div>
    </div>
    <MapBasemapControl
      class="basemap-control-container"
      :is-satellite="isSatellite"
      @toggle-basemap="toggleBasemap"
    />
    <div class="bottom-control-bar">
      <div class="logos">
        <img :src="sesLogo" alt="SES Logo" class="logo" />
        <img :src="utsLogo" alt="UTS Logo" class="logo" />
      </div>
      <div class="playback-controls">
        <button 
          class="control-button" 
          @click="setPlayback(true, 1)" 
          aria-label="Play"
        >
          <img 
            :src="isPlaying && playbackSpeed === 1 
              ? playActivatedIcon 
              : playIcon" 
            alt="Play" 
          />
        </button>
        <button 
          class="control-button" 
          @click="setPlayback(true, 2)" 
          aria-label="Play Speed 2x"
        >
          <img 
            :src="isPlaying && playbackSpeed === 2 
              ? speed2ActivatedIcon 
              : speed2Icon" 
            alt="Speed 2x" 
          />
        </button>
        <button 
          class="control-button" 
          @click="setPlayback(true, 3)" 
          aria-label="Play Speed 3x"
        >
          <img 
            :src="isPlaying && playbackSpeed === 3 
              ? speed3ActivatedIcon 
              : speed3Icon" 
            alt="Speed 3x" 
          />
        </button>
        <button 
          class="control-button" 
          @click="setPlayback(false, playbackSpeed)" 
          aria-label="Pause"
        >
          <img 
            :src="!isPlaying 
              ? pauseActivatedIcon 
              : pauseIcon" 
            alt="Pause" 
          />
        </button>
        <div class="progress-container">
          <div class="progress-bar">
            <div 
              class="progress-fill" 
              :style="{ width: `${progress}%` }"
            ></div>
          </div>
          <div class="timestamp">{{ formattedTimestamp }}</div>
        </div>
      </div>
      <div class="right-controls">
        <div class="water-depth" v-if="isFloodLayerActive">
          {{ formattedWaterDepth }}
        </div>
        <div class="coordinates">
          {{ formattedCoordinates || 'Lat 0.00000°S Lon 0.00000°E' }}
        </div>
        <div class="scale-bar">
          <div class="scale-distance">{{ scaleInfo.label }}</div>
          <div class="scale-line" :style="{ width: `${scaleInfo.width}px` }"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, onBeforeUnmount, defineEmits } from 'vue';
import { TileLayer } from '@deck.gl/geo-layers';
import { BitmapLayer } from '@deck.gl/layers';
import { MapboxOverlay } from '@deck.gl/mapbox';
import mapboxgl from 'mapbox-gl';
import { COORDINATE_SYSTEM } from '@deck.gl/core';
import type { _Tile2DHeader } from '@deck.gl/geo-layers';
import { fetchTilesList, runInferenceTask, getInferenceTaskStatus, fetchWaterDepth, fetchRainfallTilesList } from '../services/api';
import type { InferenceParams } from '../services/api';
import MapZoomControls from './MapZoomControls.vue';
import MapLayerControls from './MapLayerControls.vue';
import MapSettingsControl from './MapSettingsControl.vue';
import MapBasemapControl from './MapBasemapControl.vue';
import SettingsModal from './SettingsModal.vue';
import { debounce } from 'lodash-es';

// Import icons
import playIcon from '../assets/icon/play.svg'
import playActivatedIcon from '../assets/icon/play activated.svg'
import speed2Icon from '../assets/icon/speed2.svg'
import speed2ActivatedIcon from '../assets/icon/speed2 activated.svg'
import speed3Icon from '../assets/icon/speed3.svg'
import speed3ActivatedIcon from '../assets/icon/speed3 activated.svg'
import pauseIcon from '../assets/icon/pause.svg'
import pauseActivatedIcon from '../assets/icon/pause activated.svg'
import sesLogo from '../assets/icon/SES.svg'
import utsLogo from '../assets/icon/UTS.svg'

// Set Mapbox token
mapboxgl.accessToken = import.meta.env.VITE_SHARED_MAPBOX_ACCESS_TOKEN;

// State
const mapContainer = ref<HTMLElement | null>(null);
const isLoading = ref(true);
const isPlaying = ref(true);
const playbackSpeed = ref(1);
const currentTimestamp = ref('');
const progress = ref(0);
let map: mapboxgl.Map | null = null;

// Add environment variables
const API_HOST = import.meta.env.VITE_HOST || 'localhost';
const API_PORT = import.meta.env.VITE_BACKEND_PORT || 3000;
const API_BASE_URL = `http://${API_HOST}:${API_PORT}/api`;

// Layers
let currentLayer: TileLayer | null = null;
let previousLayer: TileLayer | null = null;
let animationIntervalId: number | null = null;
let deckOverlay: MapboxOverlay | null = null;
let timestamps: string[] = [];
let currentTimeIndex = 0;

// Constants for fixed time intervals
const BASE_FRAME_INTERVAL = 1000; // 1 second per frame at 1x speed
// Frame intervals for different playback speeds (in milliseconds)
const FRAME_INTERVALS = {
  1: BASE_FRAME_INTERVAL, // 1x speed: 1 frame per second
  2: BASE_FRAME_INTERVAL / 2, // 2x speed: 1 frame per 500ms
  3: BASE_FRAME_INTERVAL / 3, // 3x speed: 1 frame per 333ms
};

// Constants
const TRANSITION_DURATION = 300; // Reduced from 800ms to 300ms for smoother transitions
// Add transition settings for animation
const TRANSITION_SETTINGS = {
  easing: (t: number) => t * (2 - t), // Simple easeOut function
  interpolation: {
    opacity: (start: number, end: number, t: number) => start + (end - start) * t
  }
};

// Add layer state
const isFloodLayerActive = ref(true);
const isWeatherLayerActive = ref(false);

// Add startDate ref to store the first timestamp's date
const startDate = ref<Date | null>(null);

// Add cursor position state
const cursorLat = ref<number | null>(null);
const cursorLng = ref<number | null>(null);

// Add new state for scale
const currentZoom = ref(12);

// Add new state for inference
const isInferenceRunning = ref(false);

// Add new state for basemap
const isSatellite = ref(false);

// Add new state for settings
const isSettingsOpen = ref(false);

// Add new state for simulation
const currentSimulation = ref<string | null>(null);

// 添加水深相关状态
const waterDepth = ref<number | null>(null);
const isLoadingWaterDepth = ref(false);

// Add new state for rainfall data
const rainfallTimestamps = ref<string[]>([]);
const currentRainfallIndex = ref(0);
const currentRainfallTimestamp = ref('');

// Add new state for legend visibility
const isLegendVisible = computed(() => {
  return isFloodLayerActive.value || (isWeatherLayerActive.value && rainfallTimestamps.value.length > 0);
});

// Add state for tracking current inference task
const currentInferenceTaskId = ref<string | null>(null);

// Define emit
const emit = defineEmits<{
  (e: 'inference-task-started', data: { taskId: string; status: string; message: string }): void;
  (e: 'inference-task-progress', data: { taskId: string; status: string; elapsed: number; results?: any }): void;
  (e: 'inference-task-completed', data: { taskId: string }): void;
  (e: 'inference-task-error', data: { error: string }): void;
}>();

// Computed
const formattedTimestamp = computed(() => {
  // For flood layer timestamps
  if (isFloodLayerActive.value) {
    if (!currentTimestamp.value) return '';
    const match = currentTimestamp.value.match(/waterdepth_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})/);
    if (!match) return currentTimestamp.value;
    
    const [_, year, month, day, hour, minute] = match;
    const currentDate = new Date(Number(year), Number(month) - 1, Number(day));
    
    if (!startDate.value) return `${hour}:${minute} Day 1`;
    
    const diffTime = Math.abs(currentDate.getTime() - startDate.value.getTime()) +1;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    return `${hour}:${minute} Day ${diffDays}`;
  } 
  // For rainfall timestamps - update to handle rainfall_YYYYMMDDHHMMSS format
  else if (isWeatherLayerActive.value) {
    if (!currentRainfallTimestamp.value) return '';
    
    // Extract timestamp from rainfall_YYYYMMDDHHMMSS format
    const match = currentRainfallTimestamp.value.match(/rainfall_(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})/);
    if (match) {
      const [_, year, month, day, hour, minute, second] = match;
      const currentDate = new Date(Number(year), Number(month) - 1, Number(day));
      
      if (!startDate.value) return `${hour}:${minute} Day 1`;
      
      const diffTime = Math.abs(currentDate.getTime() - startDate.value.getTime()) + 1;
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
      
      return `${hour}:${minute} Day ${diffDays}`;
    }
    
    return currentRainfallTimestamp.value;
  }
  
  return '';
});

// Add computed for formatted coordinates
const formattedCoordinates = computed(() => {
  if (cursorLat.value === null || cursorLng.value === null) return '';
  
  const latDirection = cursorLat.value >= 0 ? 'N' : 'S';
  const lngDirection = cursorLng.value >= 0 ? 'E' : 'W';
  
  return `Lat ${Math.abs(cursorLat.value).toFixed(5)}°${latDirection} Lon ${Math.abs(cursorLng.value).toFixed(5)}°${lngDirection}`;
});

// Update the scale computation
const scaleInfo = computed(() => {
  // 添加空值检查
  if (cursorLat.value === null) {
    return { width: 100, label: '1 km' };
  }
  
  const metersPerPixel = 156543.03392 * Math.cos(cursorLat.value * Math.PI / 180) / Math.pow(2, currentZoom.value);
  
  // Find a nice round number for the scale
  let distance = metersPerPixel * 100; // Start with 100px width
  let width = 100;
  
  // Round to nice numbers
  if (distance >= 1000) {
    // For kilometers, round to 1, 2, 5, 10, 20, 50, 100, etc.
    const km = distance / 1000;
    const magnitude = Math.pow(10, Math.floor(Math.log10(km)));
    const normalized = km / magnitude;
    
    let roundedKm;
    if (normalized >= 5) roundedKm = 5 * magnitude;
    else if (normalized >= 2) roundedKm = 2 * magnitude;
    else roundedKm = magnitude;
    
    width = (roundedKm * 1000) / metersPerPixel;
    return {
      width: Math.round(width),
      label: `${roundedKm} km`
    };
  } else {
    // For meters, round to 50, 100, 200, 500, etc.
    const magnitude = Math.pow(10, Math.floor(Math.log10(distance)));
    const normalized = distance / magnitude;
    
    let roundedMeters;
    if (normalized >= 5) roundedMeters = 5 * magnitude;
    else if (normalized >= 2) roundedMeters = 2 * magnitude;
    else roundedMeters = magnitude;
    
    width = roundedMeters / metersPerPixel;
    return {
      width: Math.round(width),
      label: `${roundedMeters} m`
    };
  }
});

// 获取水深信息的函数
const fetchWaterDepthInfo = debounce(async (lat: number, lng: number) => {
  if (!lat || !lng) return;
  
  isLoadingWaterDepth.value = true;
  
  try {
    // 确保有当前时间戳和模拟ID
    const simulation = currentSimulation.value;

    if (!currentTimestamp.value || !simulation) {
      console.warn('无法获取水深：当前时间戳或模拟ID为空');
      return;
    }
    
    // 调用API获取水深信息
    const result = await fetchWaterDepth(lat, lng, currentTimestamp.value, simulation);
    
    if (result.success) {
      // 保存结果
      waterDepth.value = result.depth;
      
      // 记录日志
      console.debug(`坐标(${lat}, ${lng})处的水深: ${waterDepth.value}米`);
    } else {
      throw new Error(result.message || '获取水深失败');
    }
  } catch (error) {
    console.error('获取水深度失败:', error);
    waterDepth.value = null;
  } finally {
    isLoadingWaterDepth.value = false;
  }
}, 300); // 300ms的防抖时间

// 格式化水深显示的计算属性
const formattedWaterDepth = computed(() => {
  if (waterDepth.value === null) return 'Water depth : --';
  return `Water depth : ${waterDepth.value} m`;
});

// Methods
const createTileLayer = (timestamp: string) => {
  let tileUrl = '';
  
  if (currentSimulation.value) {
    console.log(`使用模拟: ${currentSimulation.value}`);
    tileUrl = `${API_BASE_URL}/tiles/${currentSimulation.value}/${timestamp}/{z}/{x}/{y}.png`;
  } else {
    const defaultSimulation = '20221024_20221022';
    console.log(`使用默认模拟: ${defaultSimulation}`);
    tileUrl = `${API_BASE_URL}/tiles/${defaultSimulation}/${timestamp}/{z}/{x}/{y}.png`;
  }
  
  return new TileLayer({
    id: `TileLayer-${timestamp}`,
    data: tileUrl,
    maxZoom: 16,
    minZoom: 13,
    tileSize: 256,
    maxCacheSize: 100,
    coordinateSystem: COORDINATE_SYSTEM.LNGLAT,
    loadOptions: {
      fetch: {
        maxConcurrency: 8,
      }
    },
    refinementStrategy: 'no-overlap',
    updateTriggers: {
      data: timestamp
    },
    onTileError: (err: Error) => {
      console.warn(`Tile loading error for timestamp ${timestamp}:`, err);
      return null;
    },
    onTileLoad: (tile: _Tile2DHeader<any>) => {
      const { x, y, z } = tile.index;
      console.debug(`Tile loaded successfully for timestamp ${timestamp} at z=${z}, x=${x}, y=${y}`);
    },
    renderSubLayers: (props: any) => {
      const { boundingBox, data } = props.tile;

      if (!data) {
        return null;
      }

      try {
        return new BitmapLayer({
          id: props.id,
          image: data,
          bounds: [
            boundingBox[0][0],
            boundingBox[0][1],
            boundingBox[1][0],
            boundingBox[1][1],
          ],
          opacity: 1,
        });
      } catch (error) {
        console.warn(`Error rendering tile layer for timestamp ${timestamp}:`, error);
        return null;
      }
    },
  });
};

const createRainfallLayer = (timestamp: string) => {
  if (!currentSimulation.value) return null;
  
  console.log(`Creating rainfall layer for simulation ${currentSimulation.value} with timestamp ${timestamp}`);
  
  const tileUrl = `${API_BASE_URL}/rainfall-tiles/${currentSimulation.value}/${timestamp}/{z}/{x}/{y}`;
  
  return new TileLayer({
    id: `RainfallLayer-${currentSimulation.value}-${timestamp}`,
    data: tileUrl,
    maxZoom: 16,
    minZoom: 13,
    tileSize: 256,
    maxCacheSize: 100,
    coordinateSystem: COORDINATE_SYSTEM.LNGLAT,
    loadOptions: {
      fetch: {
        maxConcurrency: 8,
      }
    },
    refinementStrategy: 'no-overlap',
    updateTriggers: {
      data: timestamp
    },
    onTileError: (err: Error) => {
      console.warn(`Rainfall tile loading error for ${currentSimulation.value} ${timestamp}:`, err);
      return null;
    },
    onTileLoad: (tile: _Tile2DHeader<any>) => {
      const { x, y, z } = tile.index;
      console.debug(`Rainfall tile loaded successfully for ${currentSimulation.value} ${timestamp} at z=${z}, x=${x}, y=${y}`);
    },
    renderSubLayers: (props: any) => {
      const { boundingBox, data } = props.tile;

      if (!data) {
        return null;
      }

      try {
        return new BitmapLayer({
          id: props.id,
          image: data,
          bounds: [
            boundingBox[0][0],
            boundingBox[0][1],
            boundingBox[1][0],
            boundingBox[1][1],
          ],
          opacity: 0.7,
        });
      } catch (error) {
        console.warn(`Error rendering rainfall tile layer for ${currentSimulation.value} ${timestamp}:`, error);
        return null;
      }
    },
  });
};

const updateLayers = (index: number) => {
  try {
    let newLayer = null;
    
    // Determine which layer to create based on active layer type
    if (isFloodLayerActive.value) {
      newLayer = createTileLayer(timestamps[index]);
      currentTimestamp.value = timestamps[index];
      
      // 如果有当前鼠标位置，更新水深信息
      if (cursorLat.value !== null && cursorLng.value !== null) {
        fetchWaterDepthInfo(cursorLat.value, cursorLng.value);
      }
    } else if (isWeatherLayerActive.value && currentSimulation.value && rainfallTimestamps.value.length > 0) {
      // For rainfall, use the rainfall timestamps
      const rainfallTimestamp = rainfallTimestamps.value[currentRainfallIndex.value];
      newLayer = createRainfallLayer(rainfallTimestamp);
      currentRainfallTimestamp.value = rainfallTimestamp;
    }

    if (previousLayer) {
      let startTime: number | null = null;
      
      const animate = (currentTime: number) => {
        if (!startTime) startTime = currentTime;
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / TRANSITION_DURATION, 1);
        const eased = TRANSITION_SETTINGS.easing(progress);
        
        const opacity = TRANSITION_SETTINGS.interpolation.opacity(1, 0, eased);
        
        const layerProps = previousLayer?.props;
        previousLayer = previousLayer?.constructor === TileLayer 
          ? new TileLayer({
              ...layerProps,
              opacity,
            })
          : null;
        
        deckOverlay?.setProps({ 
          layers: [previousLayer, currentLayer].filter(Boolean) 
        });
        
        if (progress < 1) {
          requestAnimationFrame(animate);
        } else {
          previousLayer = null;
        }
      };
      
      requestAnimationFrame(animate);
    }

    previousLayer = currentLayer;
    currentLayer = newLayer;
    deckOverlay?.setProps({ layers: [previousLayer, currentLayer].filter(Boolean) });
  } catch (error) {
    console.error(`Error updating layers:`, error);
    // Updated error handling for the new interval-based system
    if (animationIntervalId !== null) {
      clearInterval(animationIntervalId);
      animationIntervalId = null;
      isPlaying.value = false;
    }
  }
};

const startAnimation = () => {
  // Clear any existing animation interval
  if (animationIntervalId !== null) {
    clearInterval(animationIntervalId);
    animationIntervalId = null;
  }
  
  // Set the appropriate timestamp array based on active layer
  const activeTimestamps = isFloodLayerActive.value ? timestamps : rainfallTimestamps.value;
  
  // Skip animation if there are no timestamps
  if (activeTimestamps.length === 0) {
    return;
  }
  
  // Get the interval based on current playback speed
  const frameInterval = FRAME_INTERVALS[playbackSpeed.value as keyof typeof FRAME_INTERVALS] || BASE_FRAME_INTERVAL;
  
  console.log(`Starting animation with fixed interval: ${frameInterval}ms per frame`);
  
  // Start a new interval timer
  animationIntervalId = window.setInterval(() => {
    // Calculate next index with wrapping
    let nextIndex;
    
    if (isFloodLayerActive.value) {
      nextIndex = (currentTimeIndex + 1) % timestamps.length;
      currentTimeIndex = nextIndex;
      progress.value = (nextIndex / timestamps.length) * 100;
      updateLayers(currentTimeIndex);
    } else {
      nextIndex = (currentRainfallIndex.value + 1) % rainfallTimestamps.value.length;
      currentRainfallIndex.value = nextIndex;
      progress.value = (nextIndex / rainfallTimestamps.value.length) * 100;
      updateLayers(currentRainfallIndex.value);
    }
  }, frameInterval);
};

const togglePlayPause = () => {
  isPlaying.value = !isPlaying.value;
  if (isPlaying.value) {
    startAnimation();
  } else {
    if (animationIntervalId !== null) {
      clearInterval(animationIntervalId);
      animationIntervalId = null;
    }
  }
};

// Add zoom methods
const zoomIn = () => {
  if (map) {
    map.zoomIn();
  }
};

const zoomOut = () => {
  if (map) {
    map.zoomOut();
  }
};

// Modify initializeMap to store map instance
const initializeMap = async () => {
  if (!mapContainer.value) return;

  map = new mapboxgl.Map({
    container: mapContainer.value,
    style: 'mapbox://styles/mapbox/streets-v12',
    center: [147.356, -35.117],
    zoom: 13,
    minZoom: 13,
    maxZoom: 16,
    accessToken: import.meta.env.VITE_SHARED_MAPBOX_ACCESS_TOKEN
  });

  console.log("mapbox access token", import.meta.env.VITE_SHARED_MAPBOX_ACCESS_TOKEN);

  deckOverlay = new MapboxOverlay({ layers: [] });
  map.addControl(deckOverlay);

  // Initialize with center coordinates
  cursorLat.value = -35.117;
  cursorLng.value = 147.356;
  currentZoom.value = map.getZoom();

  // Add mouse move handler
  map.on('mousemove', (e) => {
    cursorLat.value = e.lngLat.lat;
    cursorLng.value = e.lngLat.lng;
    
    // 获取水深信息
    if (isFloodLayerActive.value) {
      fetchWaterDepthInfo(e.lngLat.lat, e.lngLat.lng);
    }
  });

  // 添加鼠标移出事件处理
  map.on('mouseout', () => {
    waterDepth.value = null;
  });

  // Add zoom handler
  map.on('zoom', () => {
    if (map) {
      currentZoom.value = map.getZoom();
    }
  });

  return map;
};

const preloadFirstFrame = async (firstTimestamp: string) => {
  // 确定使用哪个模拟
  const simulation = currentSimulation.value || '20221024_20221022';
  const baseUrl = `${API_BASE_URL}/tiles/${simulation}/${firstTimestamp}`;
  
  try {
    // 预加载一些瓦片来加速初始显示
    await Promise.all([
      fetch(`${baseUrl}/12/3964/2494.png`),
      fetch(`${baseUrl}/12/3964/2495.png`),
      fetch(`${baseUrl}/12/3965/2494.png`),
      fetch(`${baseUrl}/12/3965/2495.png`)
    ]);
    console.log('预加载瓦片完成');
  } catch (error) {
    console.warn('预加载瓦片失败:', error);
  }
};

// Add layer toggle methods
const toggleFloodLayer = () => {
  isFloodLayerActive.value = !isFloodLayerActive.value;
  map?.setCenter([147.356, -35.117]);
  
  // Turn off weather layer when flood layer is active
  if (isFloodLayerActive.value && isWeatherLayerActive.value) {
    isWeatherLayerActive.value = false;
    if (map?.getLayer('weather-layer')) {
      map.removeLayer('weather-layer');
    }
    if (map?.getSource('weather')) {
      map.removeSource('weather');
    }
  }

  updateLayers(currentTimeIndex);
};

const toggleWeatherLayer = async () => {
  map?.setCenter([147.356, -35.117]);
  
  isWeatherLayerActive.value = !isWeatherLayerActive.value;
  
  // If turning on the weather layer
  if (isWeatherLayerActive.value) {
    try {
      // Stop any existing animation
      if (animationIntervalId !== null) {
        clearInterval(animationIntervalId);
        animationIntervalId = null;
      }
      
      // Turn off flood layer
      isFloodLayerActive.value = false;
      if (currentLayer) {
        deckOverlay?.setProps({ layers: [] });
      }

      // Make sure we have a selected simulation
      if (!currentSimulation.value) {
        console.error('No simulation selected. Please select a simulation first.');
        isWeatherLayerActive.value = false;
        return;
      }

      // First fetch the rainfall timestamps for the selected simulation
      console.log(`Fetching rainfall timestamps for simulation: ${currentSimulation.value}`);
      rainfallTimestamps.value = await fetchRainfallTilesList(currentSimulation.value);
      
      if (rainfallTimestamps.value.length === 0) {
        console.error('No rainfall data available for the selected simulation');
        isWeatherLayerActive.value = false;
        return;
      }
      
      // Set the initial rainfall timestamp
      currentRainfallIndex.value = 0;
      currentRainfallTimestamp.value = rainfallTimestamps.value[0];
      
      // Create and display the rainfall layer with the first timestamp
      const rainfallLayer = createRainfallLayer(currentRainfallTimestamp.value);
      currentLayer = rainfallLayer;
      deckOverlay?.setProps({ layers: [rainfallLayer].filter(Boolean) });
      
      // Start animation if playing
      if (isPlaying.value) {
        startAnimation();
      }
    } catch (error) {
      console.error('Failed to load rainfall data:', error);
      isWeatherLayerActive.value = false;
    }
  } else {
    // Remove weather layer
    if (currentLayer) {
      deckOverlay?.setProps({ layers: [] });
      currentLayer = null;
    }
    
    // Stop animation for rainfall layer
    if (animationIntervalId !== null) {
      clearInterval(animationIntervalId);
      animationIntervalId = null;
    }
  }
};

const setPlayback = (playing: boolean, speed: number) => {
  isPlaying.value = playing;
  playbackSpeed.value = speed;
  
  // Always clear existing interval when changing playback settings
  if (animationIntervalId !== null) {
    clearInterval(animationIntervalId);
    animationIntervalId = null;
  }
  
  // Start new animation if playing is true
  if (playing) {
    startAnimation();
  }
};


// Lifecycle
onMounted(async () => {
  try {
    const map = await initializeMap();
    
    // 获取时间步列表
    try {
      const defaultSimulation = '20221024_20221022';
      currentSimulation.value = defaultSimulation;
      
      const response = await fetch(`${API_BASE_URL}/simulations/${defaultSimulation}/timesteps`);
      if (!response.ok) {
        throw new Error(`HTTP错误: ${response.status}`);
      }
      
      const data = await response.json();
      if (data.success && data.data) {
        // 提取时间步ID列表
        timestamps = data.data.map((item: any) => item.timestep_id);
        console.log(`获取到${timestamps.length}个时间步`);
      } else {
        throw new Error('API返回的数据格式不正确');
      }
    } catch (error) {
      console.error('获取时间步列表失败:', error);
      throw error; // 让错误继续向上传播
    }

    if (timestamps.length === 0) {
      throw new Error('No timestamps available');
    }

    // Set the start date from the first timestamp
    const firstMatch = timestamps[0].match(/waterdepth_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})/);
    if (firstMatch) {
      const [_, year, month, day] = firstMatch;
      startDate.value = new Date(Number(year), Number(month) - 1, Number(day));
    }

    await preloadFirstFrame(timestamps[0]);
    currentTimestamp.value = timestamps[0];
    updateLayers(0);
    
    // Start the animation with fixed time intervals
    if (isPlaying.value) {
      startAnimation();
    }
    
    isLoading.value = false;

  } catch (error) {
    console.error('Initialization error:', error);
    isLoading.value = false;
  }
});

// Add cleanup for animation interval
onBeforeUnmount(() => {
  // Clean up animation interval when component is unmounted
  if (animationIntervalId !== null) {
    clearInterval(animationIntervalId);
    animationIntervalId = null;
  }
});

// Watchers
watch(playbackSpeed, (newSpeed) => {
  if (isPlaying.value) {
    // Stop and restart animation with new speed
    if (animationIntervalId !== null) {
      clearInterval(animationIntervalId);
      animationIntervalId = null;
    }
    
    const frameInterval = FRAME_INTERVALS[newSpeed as keyof typeof FRAME_INTERVALS] || BASE_FRAME_INTERVAL;
    console.log(`Playback speed changed: ${newSpeed}x (${frameInterval}ms per frame)`);
    
    startAnimation();
  }
}, { flush: 'sync' });

const toggleSettings = () => {
  isSettingsOpen.value = !isSettingsOpen.value;
};

const handleSettingsUpdate = (newSettings: {
  animationSpeed: string;
  mapStyle: string;
  showLegend: boolean;
  showCoordinates: boolean;
}) => {
  // Update playback speed
  setPlayback(isPlaying.value, parseInt(newSettings.animationSpeed));
  
  // Update map style
  toggleBasemap(newSettings.mapStyle === 'satellite');
                                                                
  // Update UI visibility
  document.querySelector('.legend')?.classList.toggle('hidden', !newSettings.showLegend);
  document.querySelector('.coordinates')?.classList.toggle('hidden', !newSettings.showCoordinates);
};

// 将emit替换为自定义事件
const dispatchInferenceEvent = (eventName: string, detail: any) => {
  window.dispatchEvent(new CustomEvent(eventName, { detail }));
};

// Function to wait for task completion
const waitForTaskCompletion = async (taskId: string): Promise<void> => {
  // 我们不再需要轮询，因为 SettingsModal 组件现在使用 WebSocket 获取进度更新
  // 只需要等待任务完成的自定义事件
  return new Promise((resolve, reject) => {
    const taskCompletionHandler = (e: CustomEvent) => {
      if (e.detail.taskId === taskId) {
        console.log(`Task ${taskId} completion event received`);
        window.removeEventListener('inference-task-completed-internal', taskCompletionHandler as EventListener);
        window.removeEventListener('inference-task-failed-internal', taskErrorHandler as EventListener);
        
        if (e.detail.error) {
          reject(new Error(e.detail.error));
        } else {
          resolve();
        }
      }
    };
    
    const taskErrorHandler = (e: CustomEvent) => {
      if (e.detail.taskId === taskId) {
        console.log(`Task ${taskId} error event received`);
        window.removeEventListener('inference-task-completed-internal', taskCompletionHandler as EventListener);
        window.removeEventListener('inference-task-failed-internal', taskErrorHandler as EventListener);
        reject(new Error(e.detail.error));
      }
    };
    
    window.addEventListener('inference-task-completed-internal', taskCompletionHandler as EventListener);
    window.addEventListener('inference-task-failed-internal', taskErrorHandler as EventListener);
    
    // 设置超时，避免永久等待
    setTimeout(() => {
      window.removeEventListener('inference-task-completed-internal', taskCompletionHandler as EventListener);
      window.removeEventListener('inference-task-failed-internal', taskErrorHandler as EventListener);
      reject(new Error('Task completion timeout'));
    }, 1800000); // 30分钟超时
  });
};

const handleInferenceStart = async (inferenceSettings: {
  area: string;
  window: string;
  device: string;
  dataDir: string;
}) => {
  try {
    console.log('Inference Start');
    isInferenceRunning.value = true;
    
    // Stop any current animation
    if (animationIntervalId !== null) {
      clearInterval(animationIntervalId);
      animationIntervalId = null;
    }
    
    // Convert window to pred_length parameter
    const predLength = parseInt(inferenceSettings.window) * 2;
    
    // Prepare inference parameters
    const inferenceParams: InferenceParams = {
      model_path: 'best.pt',
      data_dir: inferenceSettings.dataDir, // Use selected rainfall NC file
      device: inferenceSettings.device || 'cuda:0', // Use selected CUDA device
      pred_length: predLength
    };
    
    console.log('Inference parameters:', inferenceParams);
    
    // Call new API to run inference task
    const result = await runInferenceTask(inferenceParams);
    
    if (result.success) {
      // Save task ID for status checking
      currentInferenceTaskId.value = result.data.task_id;
      console.log(`Inference task started, Task ID: ${result.data.task_id}`);
      
      // Dispatch event to notify settings modal to show progress
      dispatchInferenceEvent('inference-task-started', {
        taskId: result.data.task_id,
        status: result.data.status,
        message: result.data.message
      });
      
      // SettingsModal 会连接 WebSocket 获取实时进度，我们只需等待任务完成事件
      try {
        await waitForTaskCompletion(result.data.task_id);
        console.log(`Task ${result.data.task_id} completed successfully`);
        
        // Refresh tiles list after task completion
        const newTilesResponse = await fetchTilesList();
        timestamps = newTilesResponse.message || [];
        
        // Reset animation state
        currentTimeIndex = 0;
        if (timestamps.length > 0) {
          currentTimestamp.value = timestamps[0];
          updateLayers(0);
        }
        
        // Restart animation if it was playing
        if (isPlaying.value) {
          startAnimation();
        }
      } catch (error) {
        console.error(`Error waiting for task ${result.data.task_id} completion:`, error);
        throw error;
      }
    } else {
      throw new Error('Failed to start inference task');
    }
  } catch (error) {
    console.error('Error running inference:', error);
    // Notify modal to show error
    dispatchInferenceEvent('inference-task-error', {
      error: error instanceof Error ? error.message : String(error),
      taskId: currentInferenceTaskId.value
    });
  } finally {
    isInferenceRunning.value = false;
    // 这里不需要再发送完成事件，因为 SettingsModal 已经通过 WebSocket 获取了完成状态
  }
};

// Add the toggle function
const toggleBasemap = (value: boolean) => {
  isSatellite.value = value;
  if (map) {
    map.setStyle(value ? 'mapbox://styles/mapbox/satellite-v9' : 'mapbox://styles/mapbox/streets-v12');
  }
};

const handleHistoricalSimulation = async (simulation: string) => {
  console.log(`Loading historical simulation: ${simulation}`);
  
  try {
    // Stop any current animation
    if (animationIntervalId !== null) {
      clearInterval(animationIntervalId);
      animationIntervalId = null;
    }
    
    // 更新当前选择的模拟
    currentSimulation.value = simulation;
    console.log(`Setting current simulation: ${simulation}`);
    
    // 调用后端API获取时间步列表
    try {
      // 直接调用后端API
      const response = await fetch(`${API_BASE_URL}/simulations/${simulation}/timesteps`);
      if (!response.ok) {
        throw new Error(`HTTP错误: ${response.status}`);
      }
      
      const data = await response.json();
      if (data.success && data.data) {
        // 提取时间步ID列表
        timestamps = data.data.map((item: any) => item.timestep_id);
        console.log(`获取到${timestamps.length}个时间步`);
      } else {
        throw new Error('API返回的数据格式不正确');
      }
    } catch (error) {
      console.error('获取时间步列表失败:', error);
      timestamps = [];
    }
    
    if (timestamps.length === 0) {
      throw new Error('No timestamps available for selected simulation');
    }
    
    // Also fetch rainfall timestamps for the simulation (保持不变)
    try {
      console.log(`Fetching rainfall timestamps for simulation: ${simulation}`);
      rainfallTimestamps.value = await fetchRainfallTilesList(simulation);
      console.log(`Found ${rainfallTimestamps.value.length} rainfall timestamps`);
    } catch (error) {
      console.warn('Failed to load rainfall timestamps:', error);
      rainfallTimestamps.value = [];
    }

    // Reset animation state
    currentTimeIndex = 0;
    currentTimestamp.value = timestamps[0];
    currentRainfallIndex.value = 0;
    if (rainfallTimestamps.value.length > 0) {
      currentRainfallTimestamp.value = rainfallTimestamps.value[0];
    }
    progress.value = 0;
    
    // Update the first layer based on which layer is active
    updateLayers(0);
    
    // Start animation if it was playing
    if (isPlaying.value) {
      startAnimation();
    }

  } catch (error) {
    console.error('Error loading historical simulation:', error);
  }
};

const OPENWEATHERMAP_API_KEY = import.meta.env.VITE_SHARED_OPENWEATHERMAP_API_KEY;
</script>

<style scoped>
.map-container {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  width: 100vw;
  height: 100vh;
  margin: 0;
  padding: 0;
  overflow: hidden;
}

.map-container > div:first-child {
  width: 100vw !important;
  height: 100vh !important;
  margin: 0;
  padding: 0;
}

.control-panel, .controls, .speed-control, button {
  display: none;
}

.map-controls {
  position: absolute;
  top: 20px;
  right: 20px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  z-index: 1000;
}

.bottom-control-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 60px;
  background-color: #1E3D78;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  box-sizing: border-box;
}

.logos {
  display: flex;
  align-items: center;
  gap: 20px;
  min-width: 200px;
  flex-shrink: 0;
}

.logo {
  height: 30px;
  width: auto;
  object-fit: contain;
}

.playback-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  justify-content: center;
  margin: 0 20px;
  min-width: 0; /* Allow container to shrink below min-content width */
}

.control-button {
  width: 40px;
  height: 40px;
  padding: 8px;
  border: none;
  background: transparent;
  cursor: pointer;
  transition: transform 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.control-button:active {
  transform: scale(0.95);
}

.control-button img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.progress-container {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: 12px;
  flex: 1;
  min-width: 200px;
  max-width: 400px;
}

.progress-bar {
  flex: 1;
  height: 4px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #F48703;
  transition: width 0.1s linear;
}

.timestamp {
  font-size: 0.9em;
  font-weight: 500;
  color: #FFFFFF;
  white-space: nowrap;
  min-width: 100px;
}

.right-controls {
  display: flex;
  align-items: center;
  gap: 20px;
  flex-shrink: 0;
}

.water-depth {
  font-size: 0.9em;
  font-weight: 500;
  color: #FFFFFF;
  white-space: nowrap;
  margin-right: 16px;
  min-width: 100px;
}

.coordinates {
  font-size: 0.9em;
  font-weight: 500;
  color: #FFFFFF;
  white-space: nowrap;
}

.scale-bar {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 100px;
}

.scale-line {
  height: 2px;
  background: white;
  transition: width 0.3s ease;
}

.scale-distance {
  font-size: 0.8em;
  font-weight: 500;
  color: white;
  text-align: center;
  margin-bottom: 2px;
}

/* Remove the standalone scale-control styles */
.scale-control {
  display: none;
}

/* Remove inference button styles */
.inference-button {
  display: none;
}

.legend {
  position: absolute;
  bottom: 80px;
  right: 20px;
  background: rgba(255, 255, 255, 0.8);
  padding: 12px;
  border-radius: 8px;
  color: black;
  z-index: 1000;
  backdrop-filter: blur(4px);
  transition: opacity 0.3s ease;
}

.legend.hidden {
  opacity: 0;
  pointer-events: none;
}

.legend-title {
  font-size: 0.9em;
  font-weight: 500;
  margin-bottom: 8px;
  text-align: center;
  color: black;
}

.legend-gradient {
  display: flex;
  gap: 8px;
}

.legend-content {
  display: flex;
  gap: 8px;
  align-items: stretch;
}

.gradient-bar {
  width: 20px;
  height: 150px;
  border-radius: 4px;
}

/* Flood depth gradient */
.flood-gradient {
  background: linear-gradient(to bottom, 
    rgb(0, 0, 255) 0%,
    rgb(0, 128, 255) 25%,
    rgb(86, 180, 255) 50%,
    rgb(173, 216, 230) 75%,
    rgb(220, 238, 245) 100%
  );
}

/* Rainfall gradient based on rainfallColor.txt */
.rainfall-gradient {
  background: linear-gradient(to bottom, 
    rgb(0, 0, 255) 0%,      /* 45mm - Blue */
    rgb(86, 121, 212) 25%,  /* 30mm - Lighter blue */
    rgb(130, 168, 216) 50%, /* 15mm - Light blue */
    rgb(173, 216, 230) 75%, /* 5mm - Light blue/cyan */
    rgb(200, 230, 240) 100% /* 1mm - Very light blue */
  );
}

.gradient-labels {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  font-size: 0.8em;
  font-weight: 500;
  padding: 4px 0;
  color: black;
}

.gradient-labels span {
  line-height: 1;
}

.panel-button {
  display: flex;
  flex-direction: column;
  justify-content: normal;
  align-items: center;
}

.basemap-control-container {
  position: absolute;
  bottom: 80px;
  left: 20px;
  z-index: 1000;
}
</style>