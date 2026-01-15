<template>
  <div class="rainfall-map-wrapper">
    <div ref="mapContainer" class="rainfall-map-container"></div>
    
    <!-- Status overlays -->
    <div v-if="!OPENWEATHER_API_KEY" class="status-overlay error-overlay">
      <div class="status-icon">⚠️</div>
      <div class="status-text">OpenWeatherMap API key not configured</div>
      <div class="status-hint">Add VITE_SHARED_OPENWEATHERMAP_API_KEY to .env</div>
    </div>
    
    <div v-else-if="isLoading" class="status-overlay loading-overlay">
      <div class="loading-spinner"></div>
      <div class="status-text">Loading precipitation data...</div>
    </div>
    
    <div v-else-if="error" class="status-overlay error-overlay">
      <div class="status-icon">❌</div>
      <div class="status-text">{{ error }}</div>
    </div>
    
    <div v-else-if="layerLoaded" class="status-badge success-badge">
      ✓ Rainfall data loaded
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue';
import mapboxgl from 'mapbox-gl';

// Props
const props = defineProps<{
  timestamp: string;
  simulation?: string;
}>();

// State
const mapContainer = ref<HTMLElement | null>(null);
const isLoading = ref(true);
const error = ref<string | null>(null);
const layerLoaded = ref(false);

let map: mapboxgl.Map | null = null;

// Methods
const MAPBOX_ACCESS_TOKEN = import.meta.env.VITE_SHARED_MAPBOX_ACCESS_TOKEN;
const OPENWEATHER_API_KEY = import.meta.env.VITE_SHARED_OPENWEATHERMAP_API_KEY;

// Convert timestamp to Unix time (rounded to 3 hours for Weather Maps 2.0)
const getUnixTimeFromTimestamp = (timestamp: string): number => {
  // If no timestamp provided, use current time
  if (!timestamp || timestamp === '') {
    const now = Math.floor(Date.now() / 1000);
    // Round to previous 3-hour interval (10800 seconds = 3 hours)
    return Math.floor(now / 10800) * 10800;
  }
  
  try {
    // Parse timestamp format: waterdepth_YYYYMMDD_HHMM or similar
    const match = timestamp.match(/(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})/);
    if (match) {
      const [_, year, month, day, hour, minute] = match;
      const date = new Date(
        parseInt(year),
        parseInt(month) - 1,
        parseInt(day),
        parseInt(hour),
        parseInt(minute)
      );
      // Get Unix timestamp in seconds
      const unixTime = Math.floor(date.getTime() / 1000);
      // Round to previous 3-hour interval (Weather Maps 2.0 requirement)
      return Math.floor(unixTime / 10800) * 10800;
    }
  } catch (err) {
    console.error('RainfallMap: Error parsing timestamp:', err);
  }
  
  // Fallback to current time rounded to 3-hour interval
  const now = Math.floor(Date.now() / 1000);
  return Math.floor(now / 10800) * 10800;
};

// Add type guard for map initialization
const initializeMap = () => {
  if (!mapContainer.value || !MAPBOX_ACCESS_TOKEN) {
    console.error('RainfallMap: Missing required configuration', {
      hasContainer: !!mapContainer.value,
      hasMapboxToken: !!MAPBOX_ACCESS_TOKEN
    });
    error.value = 'Map configuration missing';
    isLoading.value = false;
    return;
  }

  if (!OPENWEATHER_API_KEY) {
    console.error('RainfallMap: OpenWeatherMap API key not configured');
    error.value = 'OpenWeatherMap API key not configured';
    isLoading.value = false;
    return;
  }

  console.log('RainfallMap: Initializing map with OpenWeatherMap Weather Maps 2.0 API');
  console.log('RainfallMap: API key length:', OPENWEATHER_API_KEY.length);
  console.log('RainfallMap: Using PA0 layer (Accumulated Precipitation) with enhanced color palette');
  
  try {
    map = new mapboxgl.Map({
      container: mapContainer.value,
      style: 'mapbox://styles/mapbox/light-v11',
      center: [147.356, -35.117], // Wagga Wagga coordinates
      zoom: 9,
      accessToken: MAPBOX_ACCESS_TOKEN,
      attributionControl: false, // Hide attribution control (info icon)
      logoPosition: 'bottom-left' // We'll hide it with CSS
    });

    map.on('load', () => {
      console.log('RainfallMap: Map loaded successfully');
      addPrecipitationLayer();
    });

    map.on('error', (e) => {
      console.error('RainfallMap: Map error:', e);
      if (e.error) {
        error.value = `Map error: ${e.error.message || 'Unknown error'}`;
      }
    });
  } catch (err) {
    console.error('RainfallMap: Failed to initialize map:', err);
    error.value = `Failed to initialize map: ${err instanceof Error ? err.message : 'Unknown error'}`;
    isLoading.value = false;
  }
};

// Add OpenWeatherMap precipitation layer
const addPrecipitationLayer = () => {
  if (!map || !map.isStyleLoaded()) {
    console.warn('RainfallMap: Cannot add precipitation layer - map not ready');
    return;
  }

  if (!OPENWEATHER_API_KEY) {
    console.error('RainfallMap: API key missing when trying to add layer');
    error.value = 'OpenWeatherMap API key not configured';
    isLoading.value = false;
    return;
  }

  try {
    // Remove existing layer and source if they exist
    if (map.getLayer('precipitation-layer')) {
      console.log('RainfallMap: Removing existing precipitation layer');
      map.removeLayer('precipitation-layer');
    }
    if (map.getSource('precipitation')) {
      console.log('RainfallMap: Removing existing precipitation source');
      map.removeSource('precipitation');
    }
    
    // Get Unix timestamp for the selected date (rounded to 3 hours)
    const unixTime = getUnixTimeFromTimestamp(props.timestamp || '');
    
    // Use Weather Maps 2.0 API with PA0 (Accumulated Precipitation) layer
    // URL format: http://maps.openweathermap.org/maps/2.0/weather/{op}/{z}/{x}/{y}?appid={API key}&date={unix_time}
    // PA0 = Accumulated precipitation in mm
    // Custom palette with more vibrant colors for better visibility
    // Format: {value}:{HEX_color} - from light blue (0.1mm) to dark blue (140mm)
    const customPalette = '0:00000000;0.1:5599FF60;0.5:3377FF99;1:0055FFCC;5:0033CCFF;10:0011AAFF;50:000088FF;140:000055FF';
    const tileUrl = `https://maps.openweathermap.org/maps/2.0/weather/PA0/{z}/{x}/{y}?appid=${OPENWEATHER_API_KEY}&date=${unixTime}&opacity=1.0&palette=${encodeURIComponent(customPalette)}&fill_bound=true`;
    console.log('RainfallMap: Adding precipitation layer (PA0 - Accumulated Precipitation) with enhanced colors');
    console.log('RainfallMap: Using timestamp:', props.timestamp, '=> Unix time:', unixTime, '(', new Date(unixTime * 1000).toISOString(), ')');
    
    // Add OpenWeatherMap Weather Maps 2.0 precipitation layer
    map.addSource('precipitation', {
      type: 'raster',
      tiles: [tileUrl],
      tileSize: 256,
      minzoom: 0,
      maxzoom: 18,
      attribution: ''
    });

    map.addLayer({
      id: 'precipitation-layer',
      type: 'raster',
      source: 'precipitation',
      paint: {
        'raster-opacity': 1.0, // Full opacity with custom palette
        'raster-fade-duration': 300,
        'raster-brightness-max': 1.0 // Ensure maximum brightness
      }
    });

    console.log('RainfallMap: Weather Maps 2.0 precipitation layer (PA0) added successfully');
    layerLoaded.value = true;
    isLoading.value = false;
    
    // Hide success badge after 3 seconds
    setTimeout(() => {
      layerLoaded.value = false;
    }, 3000);

    // Listen for tile loading errors
    map.on('error', (e) => {
      if (e.sourceId === 'precipitation') {
        console.error('RainfallMap: Error loading precipitation tiles:', e);
        error.value = 'Failed to load precipitation data. Check API key.';
        isLoading.value = false;
      }
    });

    // Listen for successful tile loads
    map.on('sourcedata', (e) => {
      if (e.sourceId === 'precipitation' && e.isSourceLoaded) {
        console.log('RainfallMap: Precipitation tiles loaded');
      }
    });
  } catch (err) {
    console.error('RainfallMap: Failed to add precipitation layer:', err);
    error.value = `Failed to add precipitation layer: ${err instanceof Error ? err.message : 'Unknown error'}`;
    isLoading.value = false;
  }
};

// Clean up on unmount
onUnmounted(() => {
  if (map) {
    map.remove();
  }
});

// Initialize map on mount
onMounted(() => {
  console.log('RainfallMap component mounted');
  initializeMap();
});

// Watch for timestamp changes and update the layer
watch(() => props.timestamp, (newTimestamp) => {
  if (newTimestamp && map?.isStyleLoaded()) {
    console.log('RainfallMap: Timestamp changed to', newTimestamp);
    addPrecipitationLayer();
  }
});
</script>

<style scoped>
.rainfall-map-wrapper {
  width: 100%;
  height: 160px;
  position: relative;
  border-radius: 8px;
  overflow: hidden;
}

.rainfall-map-container {
  width: 100%;
  height: 100%;
  border-radius: 8px;
  overflow: hidden;
}

/* Hide Mapbox logo and attribution */
.rainfall-map-container :deep(.mapboxgl-ctrl-logo),
.rainfall-map-container :deep(.mapboxgl-ctrl-attrib),
.rainfall-map-container :deep(.mapboxgl-ctrl-attrib-button) {
  display: none !important;
}

/* Status overlays */
.status-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 0.5rem;
  z-index: 10;
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}

.loading-overlay {
  background-color: rgba(249, 250, 251, 0.9);
}

.error-overlay {
  background-color: rgba(254, 242, 242, 0.95);
}

.status-icon {
  font-size: 2rem;
  margin-bottom: 0.25rem;
}

.status-text {
  font-size: 0.875rem;
  font-weight: 500;
  color: #374151;
  text-align: center;
  padding: 0 1rem;
}

.status-hint {
  font-size: 0.75rem;
  color: #6b7280;
  font-style: italic;
  text-align: center;
  padding: 0 1rem;
}

/* Loading spinner */
.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(30, 61, 120, 0.2);
  border-radius: 50%;
  border-top-color: #1E3D78;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* Success badge */
.status-badge {
  position: absolute;
  bottom: 0.5rem;
  right: 0.5rem;
  padding: 0.375rem 0.75rem;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 500;
  z-index: 5;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  animation: fadeIn 0.3s ease-in;
}

.success-badge {
  background-color: rgba(16, 185, 129, 0.9);
  color: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style> 