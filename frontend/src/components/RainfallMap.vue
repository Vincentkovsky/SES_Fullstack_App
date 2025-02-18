<template>
  <div ref="mapContainer" class="rainfall-map-container"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue';
import mapboxgl from 'mapbox-gl';

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
    zoom: 8,
    accessToken: MAPBOX_ACCESS_TOKEN
  });

  map.on('load', () => {
    console.log('Map load event triggered');
    
    if (!map || !OPENWEATHERMAP_API_KEY) {
      console.error('Map or API key is missing');
      return;
    }

    try {
      console.log('Adding weather source...');
      map.addSource('weather', {
        type: 'raster',
        tiles: [
          `https://tile.openweathermap.org/map/PR0/{z}/{x}/{y}?appid=${OPENWEATHERMAP_API_KEY}`
        ],
        tileSize: 256,
        attribution: '© OpenWeatherMap'
      });
      console.log('Weather source added successfully');

      console.log('Adding weather layer...');
      map.addLayer({
        id: 'weather-layer',
        type: 'raster',
        source: 'weather',
        paint: {
          'raster-opacity': 0.8
        }
      }, 'road-label'); // Add before labels
      console.log('Weather layer added successfully');

      // Test if the layer exists
      const hasLayer = map.getLayer('weather-layer');
      console.log('Weather layer exists:', !!hasLayer);

      // Log the tile URL to verify it's correct
      console.log('Tile URL example:', `https://tile.openweathermap.org/map/precipitation_new/8/8/8.png?appid=${OPENWEATHERMAP_API_KEY}`);

      // Check network requests for tiles
      console.log('Check Network tab for tile requests to OpenWeatherMap');
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