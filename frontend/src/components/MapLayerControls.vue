<template>
  <div class="layer-controls">
    <button 
      class="layer-button" 
      :class="{ active: isFloodLayerActive }"
      @click="toggleFloodLayer" 
      aria-label="Toggle flood layer"
      
    >
      <img 
        :src="isFloodLayerActive ? 'src/assets/icon/Flood1.svg' : 'src/assets/icon/Flood0.svg'" 
        alt="Flood layer" 
      />
    </button>
    <button 
      class="layer-button" 
      :class="{ active: isWeatherLayerActive }"
      @click="toggleWeatherLayer" 
      aria-label="Toggle weather layer"
    >
      <img 
        :src="isWeatherLayerActive ? 'src/assets/icon/weather1.svg' : 'src/assets/icon/weather0.svg'" 
        alt="Weather layer" 
      />
    </button>
  </div>
</template>

<script setup lang="ts">
import { defineProps, defineEmits } from 'vue';

const props = defineProps<{
  isFloodLayerActive: boolean
  isWeatherLayerActive: boolean
}>();

const emit = defineEmits<{
  (e: 'toggle-flood'): void
  (e: 'toggle-weather'): void
}>();

const toggleFloodLayer = () => emit('toggle-flood');
const toggleWeatherLayer = () => emit('toggle-weather');
</script>

<style scoped>
.layer-controls {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
}

.layer-button {
  width: 48px;
  height: 48px;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.layer-button img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.layer-button:hover {
  transform: scale(1.05);
  background: rgba(255, 255, 255, 0.1);
}

.layer-button.active {
  background: rgba(30, 61, 120, 0.1);
  transform: scale(1.05);
}

.layer-button:active {
  transform: scale(0.95);
}
</style> 