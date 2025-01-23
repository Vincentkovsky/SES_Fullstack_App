<template>
  <div class="map-container">
    <div ref="mapContainer" style="width: 100%; height: 100vh;"></div>
    <div class="map-controls">
      <MapZoomControls
        @zoom-in="zoomIn"
        @zoom-out="zoomOut"
      />
      <MapLayerControls
        :is-flood-layer-active="isFloodLayerActive"
        :is-weather-layer-active="isWeatherLayerActive"
        @toggle-flood="toggleFloodLayer"
        @toggle-weather="toggleWeatherLayer"
      />
    </div>
    <div class="bottom-control-bar">
      <div class="logos">
        <img src="../assets/icon/SES.svg" alt="SES Logo" class="logo" />
        <img src="../assets/icon/UTS.svg" alt="UTS Logo" class="logo" />
      </div>
      <div class="playback-controls">
        <button 
          class="control-button" 
          :class="{ active: isPlaying && playbackSpeed === 1 }"
          @click="setPlayback(true, 1)" 
          aria-label="Play"
        >
          <img src="../assets/icon/play_inactive.svg" alt="Play" />
        </button>
        <button 
          class="control-button" 
          :class="{ active: isPlaying && playbackSpeed === 2 }"
          @click="setPlayback(true, 2)" 
          aria-label="Play Speed 2x"
        >
          <img src="../assets/icon/speed2.svg" alt="Speed 2x" />
        </button>
        <button 
          class="control-button" 
          :class="{ active: isPlaying && playbackSpeed === 3 }"
          @click="setPlayback(true, 3)" 
          aria-label="Play Speed 3x"
        >
          <img src="../assets/icon/speed3.svg" alt="Speed 3x" />
        </button>
        <button 
          class="control-button" 
          :class="{ active: !isPlaying }"
          @click="setPlayback(false, playbackSpeed)" 
          aria-label="Pause"
        >
          <img src="../assets/icon/pause.svg" alt="Pause" />
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
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { TileLayer } from '@deck.gl/geo-layers';
import { BitmapLayer } from '@deck.gl/layers';
import { MapboxOverlay } from '@deck.gl/mapbox';
import mapboxgl from 'mapbox-gl';
import { animate } from 'popmotion';
import { COORDINATE_SYSTEM } from '@deck.gl/core';
import { fetchTilesList } from '../services/api';
import MapZoomControls from './MapZoomControls.vue';
import MapLayerControls from './MapLayerControls.vue';

// State
const mapContainer = ref<HTMLElement | null>(null);
const isLoading = ref(true);
const isPlaying = ref(true);
const playbackSpeed = ref(1);
const currentTimestamp = ref('');
const progress = ref(0);
let map: mapboxgl.Map | null = null;

// Layers
let currentLayer: TileLayer | null = null;
let previousLayer: TileLayer | null = null;
let animationInstance: any = null;
let deckOverlay: MapboxOverlay | null = null;
let timestamps: string[] = [];
let currentTimeIndex = 0;

// Constants
const TRANSITION_DURATION = 1000;
const FADE_DURATION = 300;

// 添加平滑过渡控制
const TRANSITION_SETTINGS = {
  duration: 300,
  easing: (t: number) => t * (2 - t), // easeOut
  interpolation: {
    opacity: (from: number, to: number, t: number) => from + (to - from) * t
  }
};

// Add layer state
const isFloodLayerActive = ref(true);
const isWeatherLayerActive = ref(false);

// Add startDate ref to store the first timestamp's date
const startDate = ref<Date | null>(null);

// Computed
const formattedTimestamp = computed(() => {
  if (!currentTimestamp.value) return '';
  const match = currentTimestamp.value.match(/waterdepth_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})/);
  if (!match) return currentTimestamp.value;
  
  const [_, year, month, day, hour, minute] = match;
  const currentDate = new Date(Number(year), Number(month) - 1, Number(day));
  
  if (!startDate.value) return `${hour}:${minute} Day 1`;
  
  const diffTime = Math.abs(currentDate.getTime() - startDate.value.getTime()) +1;
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  
  return `${hour}:${minute} Day ${diffDays}`;
});

// Methods
const createTileLayer = (timestamp: string) => {
  return new TileLayer({
    id: `TileLayer-${timestamp}`,
    data: `http://localhost:3000/api/tiles/${timestamp}/{z}/{x}/{y}`,
    maxZoom: 14,
    minZoom: 8,
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
    onTileError: (err) => {
      console.warn(`Tile loading error for timestamp ${timestamp}:`, err);
      return null;
    },
    onTileLoad: (tile) => {
      console.debug(`Tile loaded successfully for timestamp ${timestamp} at z=${tile.index[0]}, x=${tile.index[1]}, y=${tile.index[2]}`);
    },
    renderSubLayers: (props) => {
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

const updateLayers = (index: number) => {
  try {
    const newLayer = isFloodLayerActive.value ? createTileLayer(timestamps[index]) : null;

    if (previousLayer) {
      let startTime: number | null = null;
      
      const animate = (currentTime: number) => {
        if (!startTime) startTime = currentTime;
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / TRANSITION_SETTINGS.duration, 1);
        const eased = TRANSITION_SETTINGS.easing(progress);
        
        const opacity = TRANSITION_SETTINGS.interpolation.opacity(1, 0, eased);
        
        const layerProps = previousLayer?.props;
        previousLayer = new TileLayer({
          ...layerProps,
          opacity,
        });
        
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
    console.error(`Error updating layers for timestamp index ${index}:`, error);
    if (animationInstance) {
      animationInstance.stop();
      isPlaying.value = false;
    }
  }
};

const startAnimation = () => {
  if (animationInstance) {
    animationInstance.stop();
  }

  const duration = TRANSITION_DURATION * timestamps.length / playbackSpeed.value;
  
  animationInstance = animate({
    from: currentTimeIndex,
    to: timestamps.length,
    duration,
    onUpdate: (value) => {
      const nextIndex =  Math.floor(value % timestamps.length);
      progress.value = (nextIndex / timestamps.length) * 100;
      
      if (nextIndex !== currentTimeIndex) {
        currentTimeIndex = nextIndex;
        currentTimestamp.value = timestamps[currentTimeIndex];
        updateLayers(currentTimeIndex);
      }
    },
  });
};

const togglePlayPause = () => {
  isPlaying.value = !isPlaying.value;
  if (isPlaying.value) {
    startAnimation();
  } else {
    animationInstance?.stop();
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
    style: 'mapbox://styles/mapbox/satellite-v9',
    center: [147.356, -35.117],
    zoom: 12,
    accessToken: 'pk.eyJ1IjoidmluY2VudDEyOCIsImEiOiJjbHo4ZHhtcWswMXh0MnBvbW5vM2o0d2djIn0.Qj9VErbIh7yNL-DjTnAUFA'
  });

  deckOverlay = new MapboxOverlay({ layers: [] });
  map.addControl(deckOverlay);

  return map;
};

const preloadFirstFrame = async (firstTimestamp: string) => {
  const baseUrl = `http://localhost:3000/api/tiles/${firstTimestamp}`;
  await Promise.all([
    fetch(`${baseUrl}/12/3964/2494`),
    fetch(`${baseUrl}/12/3964/2495`),
    fetch(`${baseUrl}/12/3965/2494`),
    fetch(`${baseUrl}/12/3965/2495`)
  ]);
};

// Add layer toggle methods
const toggleFloodLayer = () => {
  isFloodLayerActive.value = !isFloodLayerActive.value;
  updateLayers(currentTimeIndex);
};

const toggleWeatherLayer = () => {
  isWeatherLayerActive.value = !isWeatherLayerActive.value;
  updateLayers(currentTimeIndex);
};

const setPlayback = (playing: boolean, speed: number) => {
  isPlaying.value = playing;
  playbackSpeed.value = speed;
  
  if (playing) {
    startAnimation();
  } else {
    animationInstance?.stop();
  }
};

// Lifecycle
onMounted(async () => {
  try {
    const map = await initializeMap();
    const response = await fetchTilesList();
    timestamps = response.message;

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
    startAnimation();
    isLoading.value = false;

  } catch (error) {
    console.error('Initialization error:', error);
    isLoading.value = false;
  }
});

// Watchers
watch(playbackSpeed, (newSpeed) => {
  if (isPlaying.value) {
    const durationMs = Math.round(TRANSITION_DURATION / newSpeed);
    console.log(`Playback speed: ${newSpeed}x (${durationMs}ms per frame)`);
    startAnimation();
  }
}, { flush: 'sync' });
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
  gap: 12px;
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
  padding: 0 40px;
}

.logos {
  display: flex;
  align-items: center;
  gap: 20px;
  width: 260px;
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
  margin-right: 260px; /* Balance with logos width */
}

.control-button {
  width: 40px;
  height: 40px;
  padding: 8px;
  border: none;
  background: transparent;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
}

.control-button img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.control-button:hover {
  background: rgba(255, 255, 255, 0.1);
}

.control-button.active {
  background: rgba(255, 255, 255, 0.2);
  transform: scale(1.05);
}

.control-button:active {
  transform: scale(0.95);
}

.progress-container {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-left: 20px;
  min-width: 400px;
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
  background: #FFFFFF;
  transition: width 0.1s linear;
}

.timestamp {
  font-size: 0.9em;
  font-weight: 500;
  color: #FFFFFF;
  white-space: nowrap;
  min-width: 100px;
}
</style>