<template>
  <div id="app">
    <DeckGlMap />
  </div>
</template>

<script lang="ts">
import { defineComponent, ref } from "vue";
import DeckGlMap from "./components/DeckGLMap.vue";

export default defineComponent({
  name: "App",
  components: {
    DeckGlMap,
  }
});
</script>
