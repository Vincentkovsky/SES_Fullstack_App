<template>
  <div class="map-container">
    <div ref="mapContainer" style="width: 100%; height: 100vh;"></div>
    
    <div class="control-panel">
      <div class="progress-bar">
        <div 
          class="progress-fill" 
          :style="{ width: `${progress}%` }"
        ></div>
      </div>
      <div class="controls">
        <button @click="togglePlayPause">
          {{ isPlaying ? '⏸️' : '▶️' }}
        </button>
        <div class="timestamp">{{ formattedTimestamp }}</div>
        <div class="speed-control">
          <label>Speed: {{ playbackSpeed }}x</label>
          <input 
            type="range" 
            v-model="playbackSpeed" 
            min="1" 
            max="5" 
            step="1"
          >
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

// State
const mapContainer = ref<HTMLElement | null>(null);
const isLoading = ref(true);
const isPlaying = ref(true);
const playbackSpeed = ref(1);
const currentTimestamp = ref('');
const progress = ref(0);

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

// Computed
const formattedTimestamp = computed(() => {
  if (!currentTimestamp.value) return '';
  const match = currentTimestamp.value.match(/waterdepth_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})/);
  if (!match) return currentTimestamp.value;
  const [_, year, month, day, hour, minute] = match;
  return `${year}-${month}-${day} ${hour}:${minute}`;
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
    const newLayer = createTileLayer(timestamps[index]);

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

// Initialization
const initializeMap = async () => {
  if (!mapContainer.value) return;

  const map = new mapboxgl.Map({
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

// Lifecycle
onMounted(async () => {
  try {
    const map = await initializeMap();
    const response = await fetchTilesList();
    timestamps = response.message;

    if (timestamps.length === 0) {
      throw new Error('No timestamps available');
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
  position: relative;
  width: 100%;
  height: 100vh;
}

.control-panel {
  position: absolute;
  left: 50%;
  top: 20px;
  transform: translateX(-50%);
  background: rgba(255, 255, 255, 0.2);
  padding: 8px 25px 12px;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  z-index: 1000;
  backdrop-filter: blur(4px);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.controls {
  display: flex;
  align-items: center;
  gap: 30px;
  height: 50px;
}

button {
  padding: 8px;
  font-size: 2em;
  cursor: pointer;
  border: none;
  background: rgba(0, 0, 0, 0.05);
  border-radius: 50%;
  width: 50px;
  height: 50px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.timestamp {
  font-size: 1.2em;
  font-weight: 500;
  color: #000000;
  min-width: 140px;
}

.speed-control {
  display: flex;
  align-items: center;
  gap: 15px;
}

.speed-control label {
  font-size: 1.2em;
  color: #000000;
  font-weight: 500;
  white-space: nowrap;
}

input[type="range"] {
  width: 120px;
}

.progress-bar {
  width: 100%;
  height: 4px;
  background: rgba(0, 0, 0, 0.1);
  border-radius: 2px;
  margin-bottom: 12px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #000000;
  transition: width 0.1s linear;
}

/* Add loading overlay */
.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.2em;
  z-index: 1000;
}
</style>