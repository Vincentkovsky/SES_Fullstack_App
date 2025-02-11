<template>
  <button 
    class="settings-button" 
    @click="toggleSettings" 
    aria-label="Toggle settings"
  >
    <img 
      src="../assets/icon/setting.svg"
      alt="Settings" 
    />
  </button>
</template>

<script setup lang="ts">
import { defineEmits } from 'vue';

const emit = defineEmits<{
  (e: 'toggle-settings'): void
}>();

const toggleSettings = () => emit('toggle-settings');
</script>

<style scoped>
.settings-button {
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
  border-radius: 50%;
  margin: 0 auto;
}

.settings-button img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.settings-button:hover {
  transform: scale(1.05);
  background: rgba(255, 255, 255, 0.1);
}

.settings-button:active {
  transform: scale(0.95);
}
</style> 