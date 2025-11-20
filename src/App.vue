<template>
  <div class="app">
    <h1>Designer Plugin</h1>
    
    
    <!-- Playhead Display Component -->
    <PlayheadDisplay 
      :liveUpdate="liveUpdate" 
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
    
    // Use the REST API endpoint for gototime
    const apiUrl = `http://${directorEndpoint}/api/session/transport/gototime`
    const response = await fetch(apiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        transports: [
          {
            transport: {
              name: 'default'
            },
            time: position
          }
        ]
      })
    })
    
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
.app {
  max-width: 800px;
  margin: 0 auto;
  padding: 1rem;
  padding-top: 0;
}

.stored-positions-section {
  margin: 1rem;
  padding: 1rem;
  border: 1px solid #ccc;
  border-radius: 4px;
  background-color: #fff;
  color: #212121;
}

.stored-positions-section h2 {
  margin-top: 0;
  margin-bottom: 1rem;
  color: #212121;
}

.empty-message {
  color: #666;
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
  background-color: #f5f5f5;
  border-radius: 4px;
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
  color: #212121;
  font-size: 1.1rem;
}

.position-timecode {
  font-size: 0.9rem;
  font-family: 'Courier New', monospace;
  color: #666;
}

.go-to-btn {
  padding: 0.25rem 0.5rem;
  background-color: #2196F3;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.go-to-btn:hover {
  background-color: #1976D2;
}

.remove-btn {
  padding: 0.25rem 0.5rem;
  background-color: #ff4444;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.remove-btn:hover {
  background-color: #cc0000;
}
</style>
