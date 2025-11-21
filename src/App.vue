<template>
  <div class="app">
    <h1>Marker Madness Plugin</h1>
    
    <!-- Transport Name Configuration -->
    <div class="transport-config-section">
      <h2 class="transport-title">Transport Configuration</h2>
      <div class="transport-input-group">
        <label for="transport-name" class="transport-label">Transport Name</label>
        <input 
          id="transport-name"
          type="text" 
          v-model="transportName" 
          placeholder="default"
          class="transport-input"
        />
        <p class="transport-hint">Enter the name of the transport to monitor and control</p>
      </div>
    </div>
    
    <!-- Playhead Display Component -->
    <!-- Use key to force component recreation when transport name changes -->
    <PlayheadDisplay 
      :key="transportName"
      :liveUpdate="liveUpdate" 
      :transportName="transportName"
      @capture-position="capturePosition"
    />
    
    <!-- Stored Positions Section -->
    <div class="stored-positions-section">
      <h2>Stored Positions</h2>
      <div v-if="storedPositions.length === 0" class="empty-message">
        No positions captured yet. Click "Capture Position" to add one.
      </div>
      <ul v-else class="positions-list">
        <li v-for="(position, index) in storedPositions" :key="index" class="position-item">
          <div class="position-value">
            <span class="position-seconds">{{ position.toFixed(2) }}s</span>
            <span class="position-timecode">{{ formatTimecode(position) }}</span>
          </div>
          <div class="button-group">
            <button @click="goToPosition(position)" class="go-to-btn">Go To</button>
            <button @click="removePosition(index)" class="remove-btn">Remove</button>
          </div>
        </li>
      </ul>
    </div>
    
    <!-- Display connection status -->
    <LiveUpdateOverlay :liveUpdate="liveUpdate" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useLiveUpdate, LiveUpdateOverlay } from '@disguise-one/vue-liveupdate'
import TextLayerControl from './components/TextLayerControl.vue'
import PlayheadDisplay from './components/PlayheadDisplay.vue'

// Extract the director endpoint from the URL query parameters
const urlParams = new URLSearchParams(window.location.search)
const directorEndpoint = urlParams.get('director') || 'localhost:80' // Fallback for development

// Initialize the live update composable for the overlay
const liveUpdate = useLiveUpdate(directorEndpoint)

// Store the transport name (defaults to 'default')
const transportName = ref('default')

// Store the list of captured playhead positions
const storedPositions = ref([])

// Function to capture the current playhead position
const capturePosition = (position) => {
  if (position !== undefined && position !== null) {
    storedPositions.value.push(position)
  }
}

// Function to remove a position from the list
const removePosition = (index) => {
  storedPositions.value.splice(index, 1)
}

// Convert seconds to timecode format (HH:MM:SS:FF)
// Assuming 30 fps for frames
const formatTimecode = (seconds) => {
  if (seconds === undefined || seconds === null) {
    return '00:00:00:00'
  }
  const fps = 30
  const totalFrames = Math.floor(seconds * fps)
  const hours = Math.floor(totalFrames / (fps * 3600))
  const minutes = Math.floor((totalFrames % (fps * 3600)) / (fps * 60))
  const secs = Math.floor((totalFrames % (fps * 60)) / fps)
  const frames = totalFrames % fps
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}:${String(frames).padStart(2, '0')}`
}

// Function to move playhead to a specific position
const goToPosition = async (position) => {
  try {
    console.log(`Attempting to move playhead to ${position.toFixed(2)}s`)
    
    // Ensure directorEndpoint has protocol, default to http://
    const endpoint = directorEndpoint.startsWith('http://') || directorEndpoint.startsWith('https://')
      ? directorEndpoint
      : `http://${directorEndpoint}`
    
    // Use the REST API endpoint for gototime
    const apiUrl = `${endpoint}/api/session/transport/gototime`
    const response = await fetch(apiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        transports: [
          {
            transport: {
              name: transportName.value || 'default'
            },
            time: position
          }
        ]
      })
    })
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const result = await response.json()
    if (result.status && result.status.code === 0) {
      console.log(`Successfully moved playhead to ${position.toFixed(2)}s`)
    } else {
      console.error('Error moving playhead:', result.status)
    }
  } catch (error) {
    console.error('Error moving playhead:', error)
  }
}
</script>

<style>
* {
  box-sizing: border-box;
}

body {
  background-color: #121212;
  color: #e0e0e0;
}

.app {
  max-width: 800px;
  margin: 0 auto;
  padding: 1rem;
  padding-top: 0;
  background-color: #121212;
  color: #e0e0e0;
}

.app h1 {
  color: #ffffff;
  font-size: 2rem;
  margin-bottom: 0.5rem;
}

.stored-positions-section {
  margin: 1rem;
  padding: 1rem;
  border: 1px solid #424242;
  border-radius: 4px;
  background-color: #1e1e1e;
  color: #e0e0e0;
}

.transport-config-section {
  margin: 1rem;
  padding: 1.5rem;
  border: 2px solid #424242;
  border-radius: 8px;
  background-color: #1e1e1e;
  color: #e0e0e0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.transport-title {
  margin: 0 0 1.25rem 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: #ffffff;
  border-bottom: 2px solid #424242;
  padding-bottom: 0.75rem;
}

.transport-input-group {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.transport-label {
  display: block;
  font-weight: 600;
  font-size: 0.95rem;
  color: #b0b0b0;
  margin-bottom: 0.25rem;
  letter-spacing: 0.3px;
}

.transport-input {
  width: 100%;
  padding: 0.75rem 1rem;
  border: 2px solid #424242;
  border-radius: 6px;
  font-size: 1rem;
  color: #e0e0e0;
  background-color: #2a2a2a;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  font-family: inherit;
  box-sizing: border-box;
}

.transport-input:focus {
  outline: none;
  border-color: #64b5f6;
  box-shadow: 0 0 0 3px rgba(100, 181, 246, 0.2);
}

.transport-input::placeholder {
  color: #757575;
  font-style: italic;
}

.transport-hint {
  margin: 0;
  font-size: 0.85rem;
  color: #9e9e9e;
  font-style: italic;
  line-height: 1.4;
}

.stored-positions-section h2 {
  margin-top: 0;
  margin-bottom: 1rem;
  color: #ffffff;
}

.empty-message {
  color: #9e9e9e;
  font-style: italic;
  padding: 0.5rem 0;
}

.positions-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.position-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem;
  margin: 0.5rem 0;
  background-color: #2a2a2a;
  border-radius: 4px;
  border: 1px solid #424242;
}

.button-group {
  display: flex;
  gap: 0.5rem;
}

.position-value {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.position-seconds {
  font-weight: bold;
  color: #ffffff;
  font-size: 1.1rem;
}

.position-timecode {
  font-size: 0.9rem;
  font-family: 'Courier New', monospace;
  color: #b0b0b0;
}

.go-to-btn {
  padding: 0.25rem 0.5rem;
  background-color: #1976d2;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.go-to-btn:hover {
  background-color: #1565c0;
}

.remove-btn {
  padding: 0.25rem 0.5rem;
  background-color: #d32f2f;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.remove-btn:hover {
  background-color: #c62828;
}
</style>
