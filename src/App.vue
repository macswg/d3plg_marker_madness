<template>
  <div class="app">
    <h1>Designer Plugin</h1>
    
    <!-- Text Layer Control Component -->
    <TextLayerControl />
    
    <!-- Playhead Display Component -->
    <PlayheadDisplay :liveUpdate="liveUpdate" />
    
    <!-- Display connection status -->
    <LiveUpdateOverlay :liveUpdate="liveUpdate" />
  </div>
</template>

<script setup>
import { useLiveUpdate, LiveUpdateOverlay } from '@disguise-one/vue-liveupdate'
import TextLayerControl from './components/TextLayerControl.vue'
import PlayheadDisplay from './components/PlayheadDisplay.vue'

// Extract the director endpoint from the URL query parameters
const urlParams = new URLSearchParams(window.location.search)
const directorEndpoint = urlParams.get('director') || 'localhost:80' // Fallback for development

// Initialize the live update composable for the overlay
const liveUpdate = useLiveUpdate(directorEndpoint)
</script>

<style>
.app {
  max-width: 800px;
  margin: 0 auto;
  padding: 1rem;
}
</style>
