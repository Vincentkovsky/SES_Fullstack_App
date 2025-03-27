<template>
  <div ref="mapContainer" class="rainfall-map-container"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import mapboxgl from 'mapbox-gl';

// 实际使用timestamp,只是注释掉了watch部分
const props = defineProps<{
  timestamp: string;
}>();

const mapContainer = ref<HTMLElement | null>(null);
let map: mapboxgl.Map | null = null;

const OPENWEATHERMAP_API_KEY = import.meta.env.VITE_OPENWEATHERMAP_API_KEY;
const MAPBOX_ACCESS_TOKEN = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN;

// Add type guard for map initialization
const initializeMap = () => {
  if (!mapContainer.value || !MAPBOX_ACCESS_TOKEN || !OPENWEATHERMAP_API_KEY) {
    console.error('Missing required configuration');
    return;
  }

  map = new mapboxgl.Map({
    container: mapContainer.value,
    style: 'mapbox://styles/mapbox/streets-v11',
    center: [147.356, -35.117], // Wagga Wagga coordinates
    zoom: 6,
    accessToken: MAPBOX_ACCESS_TOKEN
  });

  map.on('load', () => {
    console.log('Map load event triggered');
    
    if (!map || !OPENWEATHERMAP_API_KEY) {
      console.error('Map or API key is missing');
      return;
    }

    try {
      map.addSource('weather', {
        type: 'raster',
        tiles: [
        `http://maps.openweathermap.org/maps/2.0/weather/PR0/{z}/{x}/{y}?appid=${OPENWEATHERMAP_API_KEY}`
        ],
        tileSize: 256,
        attribution: '© OpenWeatherMap'
      });
      map.addLayer({
        id: 'weather-layer',
        type: 'raster',
        source: 'weather',
        paint: {
          'raster-opacity': 0.8
        }
      }, 'road-label'); // Add before labels
    } catch (error) {
      console.error('Error adding weather layer:', error);
    }
  });
};

// Clean up on unmount
onUnmounted(() => {
  if (map) {
    map.remove();
  }
});

// Initialize map on mount
onMounted(() => {
  initializeMap();
});

// Update weather layer when timestamp changes
// watch(() => props.timestamp, (newTimestamp) => {
//   if (!map || !map.isStyleLoaded()) return;

//   // Remove existing weather layer and source
//   if (map.getLayer('weather-layer')) {
//     map.removeLayer('weather-layer');
//   }
//   if (map.getSource('weather')) {
//     map.removeSource('weather');
//   }

//   // Add updated weather layer
//   map.addSource('weather', {
//     type: 'raster',
//     tiles: [
//       `https://maps.openweathermap.org/maps/2.0/weather/PR0/{z}/{x}/{y}?appid=${OPENWEATHERMAP_API_KEY}`
//     ],
//     tileSize: 256,
//     attribution: '© OpenWeatherMap'
//   });

//   map.addLayer({
//     id: 'weather-layer',
//     type: 'raster',
//     source: 'weather',
//     paint: {
//       'raster-opacity': 0.8
//     }
//   });
// });
</script>

<style scoped>
.rainfall-map-container {
  width: 100%;
  height: 160px;
  border-radius: 8px;
  overflow: hidden;
}
</style> 