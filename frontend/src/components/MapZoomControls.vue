<template>
  <div class="zoom-controls">
    <button class="zoom-button" @click="zoomIn" aria-label="Zoom in">
      <img :src="zoomInIcon" alt="Zoom in" />
    </button>
    <button class="zoom-button" @click="zoomOut" aria-label="Zoom out">
      <img :src="zoomOutIcon" alt="Zoom out" />
    </button>
  </div>
</template>

<script setup lang="ts">
import { defineEmits } from 'vue';
import zoomInIcon from '../assets/icon/zoomIn.svg';
import zoomOutIcon from '../assets/icon/zoomOut.svg';

const emit = defineEmits<{
  (e: 'zoom-in'): void
  (e: 'zoom-out'): void
}>();

const zoomIn = () => emit('zoom-in');
const zoomOut = () => emit('zoom-out');
</script>

<style scoped>
.zoom-controls {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.zoom-button {
  width: 32px;
  height: 32px;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.zoom-button img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.zoom-button:hover {
  transform: scale(1.05);
}

.zoom-button:active {
  transform: scale(0.95);
}
</style> 