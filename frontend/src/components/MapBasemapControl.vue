<template>
  <div class="basemap-control">
    <button 
      class="basemap-button"
      @click="toggleBasemap(!isSatellite)"
      :aria-label="isSatellite ? 'Switch to street view' : 'Switch to satellite view'"
    >
      <img 
        :src="isSatellite ? 'src/assets/icon/street.svg' : 'src/assets/icon/satellite.svg'"
        :alt="isSatellite ? 'Street' : 'Satellite'" 
      />
    </button>
  </div>
</template>

<script setup lang="ts">
import { defineProps, defineEmits } from 'vue';

const props = defineProps<{
  isSatellite: boolean
}>();

const emit = defineEmits<{
  (e: 'toggle-basemap', value: boolean): void
}>();

const toggleBasemap = (value: boolean) => emit('toggle-basemap', value);
</script>

<style scoped>
.basemap-control {
  display: flex;
  backdrop-filter: blur(4px);
}

.basemap-button {
  width: 88px;
  height: 88px;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.basemap-button:active {
  transform: scale(0.95);
}
</style> 