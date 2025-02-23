<template>
  <div class="map-container">
    <SettingsModal 
      :is-open="isSettingsOpen" 
      :timestamps="timestamps"
      @close="isSettingsOpen = false"
      @update-settings="handleSettingsUpdate"
      @start-inference="handleInferenceStart"
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
    <div class="legend">
      <div class="legend-title">Flood</div>
      <div class="legend-gradient">
        <div class="legend-content">
          <div class="gradient-bar"></div>
          <div class="gradient-labels">
            <span>10m</span>
            <span>5m</span>
            <span>2m</span>
            <span>1m</span>
            <span>0m</span>
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
        <img src="../assets/icon/SES.svg" alt="SES Logo" class="logo" />
        <img src="../assets/icon/UTS.svg" alt="UTS Logo" class="logo" />
      </div>
      <div class="playback-controls">
        <button 
          class="control-button" 
          @click="setPlayback(true, 1)" 
          aria-label="Play"
        >
          <img 
            :src="isPlaying && playbackSpeed === 1 
              ? 'src/assets/icon/play activated.svg' 
              : 'src/assets/icon/play.svg'" 
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
              ? 'src/assets/icon/speed2 activated.svg' 
              : 'src/assets/icon/speed2.svg'" 
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
              ? 'src/assets/icon/speed3 activated.svg' 
              : 'src/assets/icon/speed3.svg'" 
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
              ? 'src/assets/icon/pause activated.svg' 
              : 'src/assets/icon/pause.svg'" 
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
import { ref, computed, onMounted, watch } from 'vue';
import { TileLayer } from '@deck.gl/geo-layers';
import { BitmapLayer } from '@deck.gl/layers';
import { MapboxOverlay } from '@deck.gl/mapbox';
import mapboxgl from 'mapbox-gl';
import { animate } from 'popmotion';
import { COORDINATE_SYSTEM } from '@deck.gl/core';
import { fetchTilesList, runInference } from '../services/api';
import MapZoomControls from './MapZoomControls.vue';
import MapLayerControls from './MapLayerControls.vue';
import MapSettingsControl from './MapSettingsControl.vue';
import MapBasemapControl from './MapBasemapControl.vue';
import SettingsModal from './SettingsModal.vue';

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
const TRANSITION_DURATION = 800;
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

// Add cursor position state
const cursorLat = ref<number | null>(null);
const cursorLng = ref<number | null>(null);

// Add new state for scale
const currentZoom = ref(12);
const scaleWidth = ref(100);

// Add new state for inference
const isInferenceRunning = ref(false);

// Add new state for basemap
const isSatellite = ref(false);

// Add new state for settings
const isSettingsOpen = ref(false);

// Add weather layer state and source
let weatherSource: mapboxgl.RasterTileSource | null = null;
let weatherLayer: mapboxgl.Layer | null = null;

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

// Add computed for formatted coordinates
const formattedCoordinates = computed(() => {
  if (cursorLat.value === null || cursorLng.value === null) return '';
  
  const latDirection = cursorLat.value >= 0 ? 'N' : 'S';
  const lngDirection = cursorLng.value >= 0 ? 'E' : 'W';
  
  return `Lat ${Math.abs(cursorLat.value).toFixed(5)}°${latDirection} Lon ${Math.abs(cursorLng.value).toFixed(5)}°${lngDirection}`;
});

// Update the scale computation
const scaleInfo = computed(() => {
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
    style: 'mapbox://styles/mapbox/streets-v12',
    center: [147.356, -35.117],
    zoom: 12,
    accessToken: 'pk.eyJ1IjoidmluY2VudDEyOCIsImEiOiJjbHo4ZHhtcWswMXh0MnBvbW5vM2o0d2djIn0.Qj9VErbIh7yNL-DjTnAUFA'
  });

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
  });

  // Add zoom handler
  map.on('zoom', () => {
    currentZoom.value = map.getZoom();
  });

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
  map?.setZoom(12);
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

const toggleWeatherLayer = () => {
  map?.setZoom(6);
  map?.setCenter([147.356, -35.117]);
  
  isWeatherLayerActive.value = !isWeatherLayerActive.value;
  
  if (isWeatherLayerActive.value) {
    // Turn off flood layer when weather layer is active
    isFloodLayerActive.value = false;
    if (currentLayer) {
      deckOverlay?.setProps({ layers: [] });
    }

    // Add weather layer if it doesn't exist
    if (!map?.getSource('weather')) {
      map?.addSource('weather', {
        type: 'raster',
        tiles: [
          `http://maps.openweathermap.org/maps/2.0/weather/PR0/{z}/{x}/{y}?appid=${OPENWEATHERMAP_API_KEY}`
        ],
        tileSize: 256,
        attribution: '© OpenWeatherMap'
      });
    }

    if (!map?.getLayer('weather-layer')) {
      map?.addLayer({
        id: 'weather-layer',
        type: 'raster',
        source: 'weather',
        paint: {
          'raster-opacity': 0.8
        }
      });
    }
  } else {
    // Remove weather layer
    if (map?.getLayer('weather-layer')) {
      map.removeLayer('weather-layer');
    }
    if (map?.getSource('weather')) {
      map.removeSource('weather');
    }
  }
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

// Update the runInference method
const handleInference = async () => {
  try {
    isInferenceRunning.value = true;
    await runInference();
    console.log('Inference completed successfully');
    
    // Refresh the tiles list after successful inference
    const newTilesResponse = await fetchTilesList();
    timestamps = newTilesResponse.message;
    
    // Optionally restart animation with new timestamps
    if (isPlaying.value) {
      startAnimation();
    }
  } catch (error) {
    console.error('Error running inference:', error);
  } finally {
    isInferenceRunning.value = false;
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

const handleInferenceStart = async (inferenceSettings: {
  area: string;
  window: string;
}) => {
  try {
    isInferenceRunning.value = true;
    await runInference();
    console.log('Inference completed successfully');
    
    // Refresh the tiles list after successful inference
    const newTilesResponse = await fetchTilesList();
    timestamps = newTilesResponse.message;
    
    // Optionally restart animation with new timestamps
    if (isPlaying.value) {
      startAnimation();
    }
  } catch (error) {
    console.error('Error running inference:', error);
  } finally {
    isInferenceRunning.value = false;
  }
};

// Add the toggle function
const toggleBasemap = (value: boolean) => {
  isSatellite.value = value;
  if (map) {
    map.setStyle(value ? 'mapbox://styles/mapbox/satellite-v9' : 'mapbox://styles/mapbox/streets-v12');
  }
};

const OPENWEATHERMAP_API_KEY = import.meta.env.VITE_OPENWEATHERMAP_API_KEY;
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
  background: rgba(255, 255, 255, 0.2);
  padding: 12px;
  border-radius: 8px;
  color: white;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.legend-title {
  font-size: 0.9em;
  font-weight: 500;
  margin-bottom: 8px;
  text-align: center;
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
  background: linear-gradient(to bottom, 
    rgb(0, 0, 255) 0%,
    rgb(0, 128, 255) 25%,
    rgb(86, 180, 255) 50%,
    rgb(173, 216, 230) 75%,
    rgb(220, 238, 245) 100%
  );
}

.gradient-labels {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  font-size: 0.8em;
  font-weight: 500;
  padding: 4px 0;
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