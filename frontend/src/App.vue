<template>
  <div id="app">
    <DeckGlMap />
    <SettingsModal 
      :is-open="isSettingsModalOpen" 
      :timestamps="timestamps"
      @close="closeSettingsModal" 
      @update-settings="updateSettings"
      @start-inference="startInference"
      @select-historical-simulation="selectHistoricalSimulation" 
    />
  </div>
</template>

<script lang="ts">
import { defineComponent, ref } from "vue";
import DeckGlMap from "./components/DeckGLMap.vue";
import SettingsModal from "./components/SettingsModal.vue";

export default defineComponent({
  name: "App",
  components: {
    DeckGlMap,
    SettingsModal,
  },
  setup() {
    const isSettingsModalOpen = ref(false);
    const timestamps = ref([]);

    const closeSettingsModal = () => {
      isSettingsModalOpen.value = false;
    };

    const updateSettings = (settings: { animationSpeed: string; mapStyle: string; showLegend: boolean; showCoordinates: boolean }) => {
      console.log('Settings updated:', settings);
    };

    const startInference = (inferenceSettings: { area: string; window: string }) => {
      console.log('Starting inference with settings:', inferenceSettings);
    };

    const selectHistoricalSimulation = (simulation: string) => {
      console.log('Selected historical simulation:', simulation);
      // TODO: Implement logic to load and display the selected historical simulation
      // This could involve switching to a different dataset or view mode
    };

    return {
      isSettingsModalOpen,
      timestamps,
      closeSettingsModal,
      updateSettings,
      startInference,
      selectHistoricalSimulation
    };
  }
});
</script>

<style>
/* Add global styles if necessary */
</style>