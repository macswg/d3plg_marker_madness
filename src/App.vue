<template>
  <div class="app">
    <h1>Marker Madness Plugin</h1>
    
    <!-- Transport Name Configuration -->
    <div class="transport-config-section">
      <div class="transport-input-group">
        <label for="transport-name" class="transport-label">Transport Name</label>
        <input 
          id="transport-name"
          type="text" 
          v-model="transportName" 
          placeholder="default"
          class="transport-input"
        />
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
      <div class="section-header">
        <h2>Stored Positions</h2>
        <div class="import-export-buttons">
          <button @click="exportPositions" class="export-btn">Export YAML</button>
          <button @click="triggerImport" class="import-btn">Import YAML</button>
          <input 
            ref="fileInput"
            type="file" 
            accept=".yaml,.yml" 
            @change="importPositions" 
            style="display: none"
          />
        </div>
      </div>
      <div v-if="storedPositions.length === 0" class="empty-message">
        No positions captured yet. Click "Capture Position" to add one.
      </div>
      <ul v-else class="positions-list">
        <li v-for="(item, index) in storedPositions" :key="index" class="position-item">
          <div class="position-value">
            <span class="position-seconds">{{ item.position.toFixed(2) }}s</span>
            <input 
              type="text" 
              v-model="item.label" 
              placeholder="Enter label..."
              class="position-label-input"
            />
          </div>
          <div class="button-group">
            <button @click="goToPosition(item.position)" class="go-to-btn">Go To</button>
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
import PlayheadDisplay from './components/PlayheadDisplay.vue'
import { dump, load } from 'js-yaml'

// Extract the director endpoint from the URL query parameters
const urlParams = new URLSearchParams(window.location.search)
const { hostname } = window.location
const defaultDirector = hostname ? `${hostname}:80` : 'localhost:80'
const directorEndpoint = urlParams.get('director') || defaultDirector // Fallback for development

// Initialize the live update composable for the overlay
const liveUpdate = useLiveUpdate(directorEndpoint)

// Store the transport name (defaults to 'default')
const transportName = ref('default')

// Store the list of captured playhead positions
const storedPositions = ref([])

// Ref for file input element
const fileInput = ref(null)

// Function to capture the current playhead position
const capturePosition = (position) => {
  if (position !== undefined && position !== null) {
    storedPositions.value.push({
      position: position,
      label: ''
    })
  }
}

// Function to remove a position from the list
const removePosition = (index) => {
  storedPositions.value.splice(index, 1)
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

// Function to export stored positions as YAML
const exportPositions = () => {
  try {
    const data = {
      positions: storedPositions.value.map(item => ({
        position: item.position,
        label: item.label || ''
      }))
    }
    
    const yamlString = dump(data, { indent: 2 })
    const blob = new Blob([yamlString], { type: 'application/x-yaml' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `marker-positions-${new Date().toISOString().split('T')[0]}.yaml`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    console.log('Positions exported successfully')
  } catch (error) {
    console.error('Error exporting positions:', error)
    alert('Failed to export positions. Please check the console for details.')
  }
}

// Function to trigger file input for import
const triggerImport = () => {
  fileInput.value?.click()
}

// Function to import stored positions from YAML
const importPositions = async (event) => {
  try {
    const file = event.target.files[0]
    if (!file) {
      return
    }
    
    const text = await file.text()
    const data = load(text)
    
    // Validate the imported data structure
    if (!data || !Array.isArray(data.positions)) {
      throw new Error('Invalid YAML format. Expected an object with a "positions" array.')
    }
    
    // Validate each position has required fields
    const validPositions = data.positions.filter(pos => {
      return typeof pos.position === 'number' && pos.position >= 0
    })
    
    if (validPositions.length === 0) {
      throw new Error('No valid positions found in the YAML file.')
    }
    
    // Ask user if they want to replace or append
    const shouldReplace = confirm(
      `Found ${validPositions.length} position(s). Do you want to replace existing positions?\n\n` +
      'Click OK to replace, Cancel to append to existing positions.'
    )
    
    if (shouldReplace) {
      storedPositions.value = validPositions.map(pos => ({
        position: pos.position,
        label: pos.label || ''
      }))
    } else {
      storedPositions.value.push(...validPositions.map(pos => ({
        position: pos.position,
        label: pos.label || ''
      })))
    }
    
    // Reset file input so the same file can be imported again
    event.target.value = ''
    
    console.log(`Imported ${validPositions.length} position(s) successfully`)
  } catch (error) {
    console.error('Error importing positions:', error)
    alert(`Failed to import positions: ${error.message}`)
    // Reset file input on error
    if (event.target) {
      event.target.value = ''
    }
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
  max-width: 96%;
  margin: 0 auto;
  padding: 0.5rem 2rem;
  padding-top: 0;
  background-color: #121212;
  color: #e0e0e0;
}

.app h1 {
  color: #ffffff;
  font-size: 2rem;
  margin-bottom: 0.5rem;
  text-align: center;
}

.stored-positions-section {
  margin: 0.5rem 0;
  padding: 1rem;
  border: 1px solid #424242;
  border-radius: 4px;
  background-color: #1e1e1e;
  color: #e0e0e0;
  margin-left: 0.5rem;
  margin-right: 0.5rem;
}

.transport-config-section {
  margin: 0.5rem 0;
  padding: 0.75rem 1rem;
  border: 1px solid #424242;
  border-radius: 4px;
  background-color: #1e1e1e;
  color: #e0e0e0;
  margin-left: 0.5rem;
  margin-right: 0.5rem;
}

.transport-input-group {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 0.75rem;
}

.transport-label {
  font-weight: 600;
  font-size: 0.9rem;
  color: #b0b0b0;
  white-space: nowrap;
  letter-spacing: 0.3px;
}

.transport-input {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border: 1px solid #424242;
  border-radius: 4px;
  font-size: 0.9rem;
  color: #e0e0e0;
  background-color: #2a2a2a;
  transition: border-color 0.2s ease;
  font-family: inherit;
  box-sizing: border-box;
}

.transport-input:focus {
  outline: none;
  border-color: #64b5f6;
}

.transport-input::placeholder {
  color: #757575;
  font-style: italic;
}

.section-header {
  display: flex;
  justify-content: center;
  align-items: center;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  gap: 1rem;
}

.stored-positions-section h2 {
  margin: 0;
  color: #ffffff;
}

.import-export-buttons {
  display: flex;
  gap: 0.5rem;
}

.export-btn,
.import-btn {
  padding: 0.5rem 1rem;
  background-color: #424242;
  color: #e0e0e0;
  border: 1px solid #616161;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: background-color 0.2s ease, border-color 0.2s ease;
}

.export-btn:hover {
  background-color: #4a4a4a;
  border-color: #757575;
}

.import-btn:hover {
  background-color: #4a4a4a;
  border-color: #757575;
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

.position-label-input {
  padding: 0.5rem;
  border: 2px solid #424242;
  border-radius: 4px;
  font-size: 0.9rem;
  color: #e0e0e0;
  background-color: #1e1e1e;
  transition: border-color 0.2s ease;
  font-family: inherit;
  width: 100%;
  max-width: 300px;
}

.position-label-input:focus {
  outline: none;
  border-color: #64b5f6;
}

.position-label-input::placeholder {
  color: #757575;
  font-style: italic;
}

.go-to-btn {
  padding: 0.25rem 0.5rem;
  min-width: 70px;
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

/* Mobile styles - reduce horizontal margins for maximum width */
@media (max-width: 768px) {
  .app {
    padding: 0;
  }

  .transport-config-section,
  .stored-positions-section {
    margin-top: 0.5rem;
    margin-bottom: 0.5rem;
    margin-left: 0;
    margin-right: 0;
  }

  .position-item {
    gap: 0.75rem;
  }
}
</style>
