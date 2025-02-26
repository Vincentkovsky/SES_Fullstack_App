<template>
  <div class="mode-switch">
    <button 
      class="mode-button"
      :class="{ active: modelValue }"
      @click="$emit('update:modelValue', !modelValue)"
    >
      {{ modelValue ? 'STEED Mode' : 'Local Mode' }}
    </button>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  modelValue: boolean;
}>();

defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
}>();
</script>

<style scoped>
.mode-switch {
  background: rgba(255, 255, 255, 0.8);
  padding: 4px;
  border-radius: 8px;
  backdrop-filter: blur(4px);
}

.mode-button {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  background: #1E3D78;
  color: white;
  font-size: 0.9em;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.mode-button:hover {
  background: #2a4d8f;
}

.mode-button.active {
  background: #F48703;
}

.mode-button.active:hover {
  background: #ff9614;
}
</style> 