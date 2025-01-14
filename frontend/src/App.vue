<template>
  <div id="app">
    <DeckGlMap />
  </div>
</template>

<script lang="ts">
import { defineComponent } from "vue";
import DeckGlMap from "./components/DeckGLMap.vue";

export default defineComponent({
  name: "App",
  components: {
    DeckGlMap,
  },
});
</script>

<style>
/* Add global styles if necessary */
</style>