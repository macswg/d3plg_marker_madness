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
          <button 
            @click="numberKeysArmed = !numberKeysArmed" 
            :class="['number-keys-btn', { 'armed': numberKeysArmed }]"
          >
            {{ numberKeysArmed ? 'Disable Number Keys' : 'Enable Number Keys' }}
          </button>
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
        <li 
          v-for="(item, index) in storedPositions" 
          :key="index" 
          class="position-item"
          draggable="true"
          @dragstart="handleDragStart($event, index)"
          @dragover="handleDragOver"
          @dragenter="handleDragEnter"
          @dragleave="handleDragLeave"
          @drop="handleDrop($event, index)"
          @dragend="handleDragEnd"
        >
          <div class="position-value">
            <div class="position-header">
              <span class="position-index">{{ index + 1 }}</span>
              <span class="position-seconds">{{ item.position.toFixed(2) }}s</span>
            </div>
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
import { ref, onMounted, onUnmounted } from 'vue'
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

// State for number key shortcuts (1-9 to jump to markers)
const numberKeysArmed = ref(false)

// State for drag and drop reordering
const draggedIndex = ref(null)

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

// Drag and drop handlers for reordering positions
const handleDragStart = (event, index) => {
  draggedIndex.value = index
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/html', event.target)
  event.target.style.opacity = '0.5'
}

const handleDragOver = (event) => {
  event.preventDefault()
  event.dataTransfer.dropEffect = 'move'
}

const handleDragEnter = (event) => {
  event.preventDefault()
  event.currentTarget.classList.add('drag-over')
}

const handleDragLeave = (event) => {
  event.currentTarget.classList.remove('drag-over')
}

const handleDrop = (event, dropIndex) => {
  event.preventDefault()
  event.currentTarget.classList.remove('drag-over')
  
  if (draggedIndex.value === null || draggedIndex.value === dropIndex) {
    return
  }
  
  // Get the dragged item
  const draggedItem = storedPositions.value[draggedIndex.value]
  
  // Remove the dragged item from its original position
  storedPositions.value.splice(draggedIndex.value, 1)
  
  // Calculate the new index after removal
  let newIndex
  if (draggedIndex.value < dropIndex) {
    // Dragging down: after removing an item before the drop position,
    // the dropIndex shifts down by 1, so we use dropIndex (which is now correct)
    newIndex = dropIndex
  } else {
    // Dragging up: after removing an item after the drop position,
    // the dropIndex remains the same
    newIndex = dropIndex
  }
  
  // Insert it at the new position
  storedPositions.value.splice(newIndex, 0, draggedItem)
  
  // Reset drag state
  draggedIndex.value = null
}

const handleDragEnd = (event) => {
  event.target.style.opacity = ''
  draggedIndex.value = null
  // Remove drag-over class from all items
  document.querySelectorAll('.position-item').forEach(item => {
    item.classList.remove('drag-over')
  })
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
    // Prompt user for filename
    const defaultFilename = `marker-positions-${new Date().toISOString().split('T')[0]}`
    const userFilename = prompt('Enter filename for export:', defaultFilename)
    
    // If user cancelled, exit
    if (userFilename === null) {
      return
    }
    
    // Clean the filename (remove invalid characters and ensure .yaml extension)
    let filename = userFilename.trim()
    if (!filename) {
      filename = defaultFilename
    }
    // Remove any invalid filename characters
    filename = filename.replace(/[<>:"/\\|?*]/g, '')
    // Ensure it ends with .yaml
    if (!filename.toLowerCase().endsWith('.yaml') && !filename.toLowerCase().endsWith('.yml')) {
      filename += '.yaml'
    }
    
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
    a.download = filename
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

// Keyboard event handler for number key shortcuts (1-9)
const handleKeyPress = (event) => {
  if (!numberKeysArmed.value) return
  
  const key = event.key
  if (key >= '1' && key <= '9') {
    const index = parseInt(key) - 1
    if (index < storedPositions.value.length) {
      event.preventDefault()
      goToPosition(storedPositions.value[index].position)
    }
  }
}

// Set up and clean up keyboard event listener
onMounted(() => {
  window.addEventListener('keydown', handleKeyPress)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyPress)
})
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
  flex-wrap: wrap;
}

.number-keys-btn {
  padding: 0.5rem 1rem;
  background-color: #424242;
  color: #e0e0e0;
  border: 1px solid #616161;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: background-color 0.2s ease, border-color 0.2s ease;
}

.number-keys-btn:hover {
  background-color: #4a4a4a;
  border-color: #757575;
}

.number-keys-btn.armed {
  background-color: #d32f2f;
  border-color: #f44336;
  color: white;
  animation: flashRed 0.8s ease-in-out infinite;
}

.number-keys-btn.armed:hover {
  background-color: #b71c1c;
  border-color: #d32f2f;
}

@keyframes flashRed {
  0%, 100% {
    background-color: #b71c1c;
    border-color: #d32f2f;
    box-shadow: 0 0 5px rgba(211, 47, 47, 0.4);
  }
  50% {
    background-color: #ff1744;
    border-color: #ff5252;
    box-shadow: 0 0 20px rgba(255, 23, 68, 1), 0 0 30px rgba(255, 82, 82, 0.8);
  }
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
  cursor: move;
  transition: background-color 0.2s ease, border-color 0.2s ease, opacity 0.2s ease;
}

.position-item:hover {
  background-color: #333333;
  border-color: #525252;
}

.position-item.drag-over {
  border-color: #1976d2;
  background-color: #1e3a5f;
  border-style: dashed;
}

.position-item:active {
  cursor: grabbing;
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

.position-header {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
}

.position-index {
  color: #757575;
  font-size: 0.85rem;
  font-weight: 500;
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
