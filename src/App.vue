<template>
  <div class="app">
    <h1>Marker Madness Plugin</h1>
    
    <!-- Transport Selection -->
    <div class="transport-config-section">
      <div class="transport-input-group">
        <label for="transport-name" class="transport-label">Transport</label>
        <select
          id="transport-name"
          v-model="transportName"
          class="transport-input"
        >
          <!-- Keep the current value selectable even when the list can't be
               fetched (e.g. no Designer session), so behaviour still works. -->
          <option v-if="!availableTransports.some(t => t.name === transportName)" :value="transportName">
            {{ transportName || 'default' }}
          </option>
          <option v-for="t in availableTransports" :key="t.uid || t.name" :value="t.name">
            {{ t.name }}
          </option>
        </select>
        <button @click="fetchTransports" class="refresh-btn" title="Refresh transport list" aria-label="Refresh transports">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12a9 9 0 1 1-3-6.7L21 8" />
            <path d="M21 3v5h-5" />
          </svg>
        </button>
      </div>
    </div>
    
    <!-- Playhead Display Component -->
    <!-- Use key to force component recreation when transport name changes -->
    <PlayheadDisplay
      :key="transportName"
      :liveUpdate="liveUpdate"
      :transportName="transportName"
      :hotkeyArmed="markerKeyArmed"
      @capture-position="capturePosition"
    />
    
    <!-- Stored Positions Section -->
    <div class="stored-positions-section">
      <div class="section-header">
        <h2>Stored Positions</h2>
        <div class="import-export-buttons">
          <button
            @click="markerKeyArmed = !markerKeyArmed"
            :class="['number-keys-btn', { 'armed-green': markerKeyArmed }]"
            title="Press ` to add a marker"
          >
            Add Marker Key `
          </button>
          <button
            @click="numberKeysArmed = !numberKeysArmed"
            :class="['number-keys-btn', { 'armed': numberKeysArmed }]"
          >
            {{ numberKeysArmed ? 'Num Keys ON' : 'Num Keys OFF' }}
          </button>
          <button @click="exportPositions" class="export-btn" title="Export YAML" aria-label="Export YAML">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 3v12" />
              <path d="M7 10l5 5 5-5" />
              <path d="M5 21h14" />
            </svg>
          </button>
          <button @click="triggerImport" class="import-btn" title="Import YAML" aria-label="Import YAML">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 21V9" />
              <path d="M7 14l5-5 5 5" />
              <path d="M5 3h14" />
            </svg>
          </button>
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
              <span class="position-seconds">{{ item.timecode || item.position.toFixed(2) + 's' }}</span>
              <span class="position-transport">{{ item.track || '(no track)' }}</span>
            </div>
            <input 
              type="text" 
              v-model="item.label" 
              placeholder="Enter label..."
              class="position-label-input"
            />
          </div>
          <div class="button-group">
            <button @click="goToPosition(item)" class="go-to-btn">Go To</button>
            <button @click="removePosition(index)" class="remove-btn">Remove</button>
          </div>
        </li>
      </ul>
    </div>
    
    <!-- Display connection status -->
    <LiveUpdateOverlay :liveUpdate="liveUpdate" />

    <!-- Version number -->
    <footer class="app-footer">
      <div>v{{ version }}</div>
      <div class="app-author">Sean Green</div>
    </footer>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useLiveUpdate, LiveUpdateOverlay } from '@disguise-one/vue-liveupdate'
import PlayheadDisplay from './components/PlayheadDisplay.vue'
import { dump, load } from 'js-yaml'
import { version } from '../package.json'

// Extract the director endpoint from the URL query parameters
const urlParams = new URLSearchParams(window.location.search)
const { hostname } = window.location
const defaultDirector = hostname ? `${hostname}:80` : 'localhost:80'
const directorEndpoint = urlParams.get('director') || defaultDirector // Fallback for development

// Initialize the live update composable for the overlay
const liveUpdate = useLiveUpdate(directorEndpoint)

// Store the transport name (defaults to 'default')
const transportName = ref('default')

// Available transports fetched from the session: [{ uid, name }]
const availableTransports = ref([])

// Store the list of captured playhead positions
const storedPositions = ref([])

// Ref for file input element
const fileInput = ref(null)

// State for number key shortcuts (1-9 to jump to markers)
const numberKeysArmed = ref(false)

// State for the marker hotkey (` to add a marker)
const markerKeyArmed = ref(false)

// State for drag and drop reordering
const draggedIndex = ref(null)

// Build a normalized http(s) base URL for the director REST API
const apiBase = () => {
  return directorEndpoint.startsWith('http://') || directorEndpoint.startsWith('https://')
    ? directorEndpoint
    : `http://${directorEndpoint}`
}

// Fetch the list of transports available in the session (read-only GET) and
// populate the dropdown. Multitransports (multi-transport managers) are
// intentionally excluded.
const fetchTransports = async () => {
  try {
    const response = await fetch(`${apiBase()}/api/session/transport/transports`)
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    const data = await response.json()
    const list = Array.isArray(data.transports) ? data.transports : []
    availableTransports.value = list
      .map(t => ({ uid: t.uid || '', name: t.name || '' }))
      .filter(t => t.name)

    // If the current selection isn't among the available transports, fall back
    // to the first one so the dropdown always reflects a real transport.
    if (
      availableTransports.value.length &&
      !availableTransports.value.some(t => t.name === transportName.value)
    ) {
      transportName.value = availableTransports.value[0].name
    }
  } catch (error) {
    console.warn('Could not fetch transports:', error)
  }
}

// Fetch the track currently loaded on the given transport (read-only GET).
// Returns { name, uid }; empty strings if it can't be determined.
const fetchCurrentTrack = async (transport) => {
  try {
    const response = await fetch(`${apiBase()}/api/session/transport/activetransport`)
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    const data = await response.json()
    const transports = Array.isArray(data.result) ? data.result : []
    // Prefer the transport matching our name, otherwise fall back to the first
    const match = transports.find(t => t.name === transport) || transports[0]
    if (match && match.currentTrack) {
      return {
        name: match.currentTrack.name || '',
        uid: match.currentTrack.uid || ''
      }
    }
  } catch (error) {
    console.warn('Could not fetch current track:', error)
  }
  return { name: '', uid: '' }
}

// Function to capture the current playhead position (and the loaded track)
const capturePosition = async (position, transport, timecode) => {
  if (position === undefined || position === null) {
    return
  }
  const transportNameValue = transport || transportName.value || 'default'
  // Look up which track is loaded on the transport right now
  const track = await fetchCurrentTrack(transportNameValue)
  storedPositions.value.push({
    position: position,
    transport: transportNameValue,
    track: track.name,
    trackUid: track.uid,
    timecode: timecode || '',
    label: ''
  })
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

// POST a transport command and verify the status code, throwing on failure
const postTransportCommand = async (command, body) => {
  const response = await fetch(`${apiBase()}/api/session/transport/${command}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body)
  })

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  const result = await response.json()
  if (result.status && result.status.code !== 0) {
    throw new Error(`${command} failed: ${JSON.stringify(result.status)}`)
  }
  return result
}

// Function to move playhead to a stored marker: switch to its track, then seek
const goToPosition = async (marker) => {
  const position = marker.position
  const targetTransport = marker.transport || transportName.value || 'default'
  const transportLocator = { name: targetTransport }

  try {
    // 1. Switch to the captured track first (prefer uid, fall back to name).
    //    Locators check uid when present, so include both when we have them.
    if (marker.trackUid || marker.track) {
      const trackLocator = {}
      if (marker.trackUid) trackLocator.uid = marker.trackUid
      if (marker.track) trackLocator.name = marker.track

      console.log(`Switching transport "${targetTransport}" to track "${marker.track || marker.trackUid}"`)
      await postTransportCommand('gototrack', {
        transports: [
          { transport: transportLocator, track: trackLocator }
        ]
      })
    }

    // 2. Seek to the captured time within that track
    console.log(`Moving playhead to ${position.toFixed(2)}s on transport "${targetTransport}"`)
    await postTransportCommand('gototime', {
      transports: [
        { transport: transportLocator, time: position }
      ]
    })

    console.log(`Successfully moved to ${position.toFixed(2)}s on track "${marker.track || '(none)'}"`)
  } catch (error) {
    console.error('Error moving playhead:', error)
  }
}

// Function to export stored positions as YAML
const exportPositions = () => {
  try {
    // Build the filename directly. We deliberately avoid prompt() here: inside
    // the Disguise plugin host the panel runs in a sandboxed webview where
    // window.prompt() is blocked and returns null, which silently aborted the
    // export. A fixed, dated filename works in both the plugin and a browser.
    const filename = `marker-positions-${new Date().toISOString().split('T')[0]}.yaml`

    const data = {
      positions: storedPositions.value.map(item => ({
        position: item.position,
        transport: item.transport || 'default',
        track: item.track || '',
        trackUid: item.trackUid || '',
        // The d3-computed timecode string shown for the marker
        timecode: item.timecode || '',
        // The per-marker note shown in the UI label input
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
    
    const normalize = pos => ({
      position: pos.position,
      transport: pos.transport || 'default',
      track: pos.track || '',
      trackUid: pos.trackUid || '',
      timecode: pos.timecode || '',
      label: pos.label || ''
    })

    if (shouldReplace) {
      storedPositions.value = validPositions.map(normalize)
    } else {
      storedPositions.value.push(...validPositions.map(normalize))
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
      goToPosition(storedPositions.value[index])
    }
  }
}

// Set up and clean up keyboard event listener
onMounted(() => {
  window.addEventListener('keydown', handleKeyPress)
  // Populate the transport dropdown from the session
  fetchTransports()
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
  font-size: 1.5rem;
  margin-top: 0.3rem;
  margin-bottom: 0.3rem;
  text-align: center;
}

.stored-positions-section {
  margin: 0.3rem 0.5rem;
  padding: 0.6rem 1rem;
  border: 1px solid #424242;
  border-radius: 4px;
  background-color: #1e1e1e;
  color: #e0e0e0;
}

.transport-config-section {
  margin: 0.3rem 0.5rem;
  padding: 0.5rem 1rem;
  border: 1px solid #424242;
  border-radius: 4px;
  background-color: #1e1e1e;
  color: #e0e0e0;
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

/* The transport selector is a <select>; let it grow and sit beside the
   refresh button in the flex row. */
select.transport-input {
  flex: 1;
  cursor: pointer;
}

.refresh-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 0.6rem;
  background-color: #424242;
  color: #e0e0e0;
  border: 1px solid #616161;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: background-color 0.2s ease, border-color 0.2s ease;
}

.refresh-btn:hover {
  background-color: #4a4a4a;
  border-color: #757575;
}

.section-header {
  display: flex;
  justify-content: center;
  align-items: center;
  margin-bottom: 0.6rem;
  flex-wrap: wrap;
  gap: 1rem;
}

.stored-positions-section h2 {
  margin: 0;
  color: #ffffff;
  font-weight: normal;
  font-size: 1.3rem;
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

.number-keys-btn.armed-green {
  background-color: #2e7d32;
  border-color: #43a047;
  color: white;
  animation: flashGreen 1.6s ease-in-out infinite;
}

.number-keys-btn.armed-green:hover {
  background-color: #1b5e20;
  border-color: #2e7d32;
}

@keyframes flashGreen {
  0%, 100% {
    background-color: #1b5e20;
    border-color: #2e7d32;
    box-shadow: 0 0 5px rgba(46, 125, 50, 0.4);
  }
  50% {
    background-color: #2a7d44;
    border-color: #388e3c;
    box-shadow: 0 0 16px rgba(0, 230, 118, 0.25), 0 0 24px rgba(105, 240, 174, 0.2);
  }
}

.export-btn,
.import-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 0.6rem;
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
  font-size: 0.95rem;
}

.position-transport {
  color: #b0b0b0;
  font-size: 0.8rem;
  background-color: #333333;
  border: 1px solid #424242;
  border-radius: 3px;
  padding: 0.05rem 0.4rem;
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

.app-footer {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  color: #757575;
  font-size: 0.75rem;
  padding: 1rem 0 0.5rem;
}

.app-author {
  margin-top: 0.15rem;
}

/* Mobile styles - reduce horizontal margins for maximum width */
@media (max-width: 768px) {
  .app {
    padding: 0;
  }

  .transport-config-section,
  .stored-positions-section {
    margin-top: 0.3rem;
    margin-bottom: 0.3rem;
    margin-left: 0;
    margin-right: 0;
  }

  .position-item {
    gap: 0.75rem;
  }
}
</style>
