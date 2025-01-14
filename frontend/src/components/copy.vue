<template>
    <div ref="mapContainer" style="width: 100%; height: 100vh;"></div>
  </template>
  
  <script lang="ts">
  import { defineComponent, onMounted, ref } from 'vue';
  import { Deck } from '@deck.gl/core';
  import { TileLayer } from '@deck.gl/geo-layers';
  import { BitmapLayer } from '@deck.gl/layers';
  import { MapboxOverlay } from '@deck.gl/mapbox';
  import mapboxgl from 'mapbox-gl';
  import { animate } from 'popmotion'; // Import Popmotion
  import { fetchTilesList } from '../services/api';
  
  async function getAvailableTimestamps(): Promise<string[]> {
    try {
      const tilesListResponse = await fetchTilesList();
      const timestamps = tilesListResponse.message;
  
      if (!timestamps || timestamps.length === 0) {
        throw new Error('No timestamps available from the API.');
      }
  
      return timestamps;
    } catch (error) {
      console.error('Error fetching available timestamps:', error);
      throw error;
    }
  }
  
  export default defineComponent({
    name: 'DeckGlMap',
    setup() {
      const mapContainer = ref<HTMLElement | null>(null);
  
      onMounted(async () => {
        if (!mapContainer.value) return;
  
        const MAPBOX_ACCESS_TOKEN =
          'pk.eyJ1IjoidmluY2VudDEyOCIsImEiOiJjbHo4ZHhtcWswMXh0MnBvbW5vM2o0d2djIn0.Qj9VErbIh7yNL-DjTnAUFA';
        mapboxgl.accessToken = MAPBOX_ACCESS_TOKEN;
  
        // Initialize Mapbox map
        const map = new mapboxgl.Map({
          container: mapContainer.value,
          style: 'mapbox://styles/mapbox/satellite-v9',
          center: [147.356, -35.117],
          zoom: 12,
        });
  
        map.fitBounds(
          [
            [147.2269791304944, -35.04697273466993], // South-west corner
            [147.6591065730234, -35.20580970683755], // North-east corner
          ],
          { padding: 20 }
        );
  
        // Fetch available timestamps
        const timestamps = await getAvailableTimestamps();
        if (timestamps.length === 0) {
          console.error('No timestamps available to display.');
          return;
        }
  
        let currentTimeIndex = 0;
        const transitionDuration = 500; // Animation duration for each transition
  
        // Initialize Deck.gl instance
        const deckOverlay = new MapboxOverlay({ layers: [] });
        map.addControl(deckOverlay);
  
        function updateLayers(currentIndex: number) {
    const tileLayer = new TileLayer({
      id: `TileLayer-${timestamps[currentIndex]}`,
      data: `http://localhost:3000/api/tiles/${timestamps[currentIndex]}/{z}/{x}/{y}`,
      maxZoom: 14,
      minZoom: 0,
      tileSize: 256,
      renderSubLayers: (props) => {
        const { boundingBox } = props.tile;
  
        return new BitmapLayer(props, {
          data: null,
          image: props.data,
          bounds: [
            boundingBox[0][0],
            boundingBox[0][1],
            boundingBox[1][0],
            boundingBox[1][1],
          ],
          opacity: Math.min(1, currentTimeIndex * 0.1), // 动态调整透明度
        });
      },
      pickable: true,
    });
  
    deckOverlay.setProps({ layers: [tileLayer] });
  }
  
        // Start the animation loop using popmotion
        animate({
          from: 0,
          to: timestamps.length - 1,
          duration: transitionDuration * timestamps.length, // Complete a full loop over all timestamps
          repeat: Infinity,
          onUpdate: (value) => {
            const nextIndex = Math.floor(value); // Get the current index
            if (nextIndex !== currentTimeIndex) {
              currentTimeIndex = nextIndex; // Update the current index
              updateLayers(currentTimeIndex); // Update the map layers
            }
          },
        });
      });
  
      return {
        mapContainer,
      };
    },
  });
  </script>
  
  <style>
  /* Optional: Add styles for your map container */
  </style>