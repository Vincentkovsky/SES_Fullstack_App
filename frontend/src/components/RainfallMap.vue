<template>
  <div ref="mapContainer" class="rainfall-map-container">
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed } from 'vue';
import mapboxgl from 'mapbox-gl';
import { fetchRainfallTilesList } from '../services/api';

// Props
const props = defineProps<{
  timestamp: string;
  simulation?: string;
}>();

// State
const mapContainer = ref<HTMLElement | null>(null);
const isLoading = ref(false);
const error = ref<string | null>(null);
const hasRainfallData = ref(false);
const currentTimestampIndex = ref(0);
const timestamps = ref<string[]>([]);

let map: mapboxgl.Map | null = null;
let animationFrameId: number | null = null;
let lastFrameTime = 0;
const FRAME_DELAY = 500; // 500ms between frames

// Methods
const MAPBOX_ACCESS_TOKEN = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN;

// Start animation
const startAnimation = () => {
  if (!hasRainfallData.value || timestamps.value.length <= 1) {
    console.log('Animation not started: No data or only one timestamp');
    return;
  }
  
  console.log('Starting rainfall animation with', timestamps.value.length, 'frames');
  
  const animate = (timestamp: number) => {
    const elapsed = timestamp - lastFrameTime;
    
    if (elapsed > FRAME_DELAY) {
      lastFrameTime = timestamp;
      // Move to next timestamp
      currentTimestampIndex.value = (currentTimestampIndex.value + 1) % timestamps.value.length;
      updateRainfallLayer(timestamps.value[currentTimestampIndex.value]);
    }
    
    animationFrameId = requestAnimationFrame(animate);
  };
  
  lastFrameTime = performance.now();
  animationFrameId = requestAnimationFrame(animate);
};

// Stop animation
const stopAnimation = () => {
  if (animationFrameId !== null) {
    console.log('Stopping rainfall animation');
    cancelAnimationFrame(animationFrameId);
    animationFrameId = null;
  }
};

// Add type guard for map initialization
const initializeMap = () => {
  if (!mapContainer.value || !MAPBOX_ACCESS_TOKEN) {
    console.error('Missing required configuration');
    return;
  }

  console.log('Initializing rainfall map');
  map = new mapboxgl.Map({
    container: mapContainer.value,
    style: 'mapbox://styles/mapbox/streets-v11',
    center: [147.356, -35.117], // Wagga Wagga coordinates
    zoom: 9,
    accessToken: MAPBOX_ACCESS_TOKEN
  });

  map.on('load', async () => {
    console.log('RainfallMap - Map load event triggered');
    
    if (!map) {
      console.error('Map is missing');
      return;
    }

    // Load rainfall data if we have a simulation
    if (props.simulation) {
      await loadRainfallData();
    }
  });
};

// Load rainfall data for the current simulation
const loadRainfallData = async () => {
  if (!props.simulation) {
    console.log('No simulation provided, cannot load rainfall data');
    return;
  }
  
  try {
    isLoading.value = true;
    error.value = null;
    
    console.log(`Loading rainfall data for simulation: ${props.simulation}`);
    
    // Fetch timestamps for the simulation from API
    await fetchTimestamps();
    
    console.log(`Fetched ${timestamps.value.length} rainfall timestamps`);
    
    if (timestamps.value.length > 0) {
      hasRainfallData.value = true;
      currentTimestampIndex.value = 0;
      
      // Add the initial rainfall layer
      updateRainfallLayer(timestamps.value[0]);
      
      // Start animation
      console.log('Starting animation after loading data');
      startAnimation();
    } else {
      console.warn('No rainfall timestamps found for this simulation');
      hasRainfallData.value = false;
    }
  } catch (err) {
    console.error('Error loading rainfall data:', err);
    error.value = err instanceof Error ? err.message : String(err);
    hasRainfallData.value = false;
  } finally {
    isLoading.value = false;
  }
};

// Fetch timestamps from API
const fetchTimestamps = async () => {
  if (!props.simulation) return;
  
  try {
    console.log(`Fetching rainfall timestamps for simulation: ${props.simulation}`);
    
    // Get timestamps from the API
    const rainfallTimestamps = await fetchRainfallTilesList(props.simulation);
    
    if (rainfallTimestamps && rainfallTimestamps.length > 0) {
      console.log(`Received ${rainfallTimestamps.length} rainfall timestamps from API`);
      timestamps.value = rainfallTimestamps;
    } else {
      console.warn('No rainfall timestamps received from API, using provided timestamp as fallback');
      
      // Fallback to the provided timestamp if API returns no data
      if (props.timestamp) {
        timestamps.value = [props.timestamp];
      } else {
        timestamps.value = [];
      }
    }
  } catch (error) {
    console.error('Error fetching rainfall timestamps:', error);
    
    // Fallback to the provided timestamp in case of error
    if (props.timestamp) {
      console.warn('Using provided timestamp as fallback due to API error');
      timestamps.value = [props.timestamp];
    } else {
      timestamps.value = [];
    }
  }
};

// Update the rainfall layer on the map
const updateRainfallLayer = (timestamp: string) => {
  if (!map || !map.isStyleLoaded() || !props.simulation) {
    console.warn('Cannot update rainfall layer: map not ready or no simulation');
    return;
  }

  // Remove existing weather layer and source
  if (map.getLayer('rainfall-layer')) {
    map.removeLayer('rainfall-layer');
  }
  if (map.getSource('rainfall')) {
    map.removeSource('rainfall');
  }
  
  console.log(`Loading rainfall tiles for simulation: ${props.simulation} with timestamp: ${timestamp}`);
  
  // Add updated rainfall layer using the tile-based approach with timestamp
  map.addSource('rainfall', {
    type: 'raster',
    tiles: [
      `http://localhost:3000/api/rainfall-tiles/${props.simulation}/${timestamp}/{z}/{x}/{y}`
    ],
    tileSize: 256,
    attribution: '© Flood Model'
  });

  map.addLayer({
    id: 'rainfall-layer',
    type: 'raster',
    source: 'rainfall',
    paint: {
      'raster-opacity': 0.8
    }
  });

  // Add error handler for tile loading errors
  map.on('error', (e: any) => {
    // Check if the error is related to our rainfall tiles
    if (e.error && e.sourceId === 'rainfall') {
      console.warn(`Rainfall tiles not found for simulation: ${props.simulation} with timestamp: ${timestamp}`);
      hasRainfallData.value = false;
      stopAnimation();
    }
  });
};

// Clean up on unmount
onUnmounted(() => {
  stopAnimation();
  if (map) {
    map.remove();
  }
});

// Initialize map on mount
onMounted(() => {
  console.log('RainfallMap component mounted');
  initializeMap();
});

// Update when timestamp changes
watch(() => props.timestamp, (newTimestamp) => {
  if (newTimestamp && map?.isStyleLoaded()) {
    console.log(`Timestamp changed to ${newTimestamp}`);
    
    // Update timestamps if needed
    if (!timestamps.value.includes(newTimestamp)) {
      fetchTimestamps();
    }
    
    // Update the layer
    if (timestamps.value.length > 0) {
      updateRainfallLayer(timestamps.value[0]);
    }
  }
});

// Update when simulation changes
watch(() => props.simulation, async (newSimulation) => {
  console.log(`Simulation changed to ${newSimulation}`);
  
  if (newSimulation) {
    stopAnimation();
    await loadRainfallData();
  } else {
    hasRainfallData.value = false;
    stopAnimation();
  }
}, { immediate: true });
</script>

<style scoped>
.rainfall-map-container {
  width: 100%;
  height: 160px;
  border-radius: 8px;
  overflow: hidden;
  position: relative;
}

.no-data-message {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: rgba(240, 240, 240, 0.7);
  color: #666;
  font-size: 0.9rem;
  text-align: center;
  padding: 1rem;
}

/* Removed controls styles as they're no longer needed */
</style> 