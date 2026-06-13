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
          <input
            type="text"
            v-model="notePrefix"
            placeholder="Note prefix"
            class="note-prefix-input"
            title="Prepended (with an underscore) to every note sent to d3, e.g. SHOW_ -> SHOW_cue1"
          />
          <button @click="sendNotesToD3" class="send-d3-btn" title="Send markers to d3 as timeline notes">
            Send to d3
          </button>
          <button @click="exportPositions" class="export-btn" title="Copy positions as YAML" aria-label="Copy positions as YAML">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 3v12" />
              <path d="M7 10l5 5 5-5" />
              <path d="M5 21h14" />
            </svg>
          </button>
          <button @click="openImport" class="import-btn" title="Import YAML (paste)" aria-label="Import YAML">
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
            @change="loadFileIntoImport"
            style="display: none"
          />
        </div>
      </div>
      <div v-if="copyStatus" class="copy-status">{{ copyStatus }}</div>
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
    
    <!-- Manual-copy fallback: shown only when the clipboard is blocked by the
         sandbox. The user select-alls the YAML and copies it by hand. -->
    <div v-if="exportText" class="export-overlay" @click.self="closeExportOverlay">
      <div class="export-panel">
        <div class="export-panel-header">
          <span>Copy this YAML</span>
          <span class="export-panel-hint">Clipboard was blocked — select all and copy manually</span>
        </div>
        <textarea
          ref="exportTextarea"
          class="export-panel-text"
          readonly
          :value="exportText"
        ></textarea>
        <div class="export-panel-buttons">
          <button @click="copyExportText" class="send-d3-btn">Copy</button>
          <button @click="closeExportOverlay" class="remove-btn">Close</button>
        </div>
      </div>
    </div>

    <!-- Paste-in import: the sandbox blocks the file dialog and confirm(), so
         the user pastes YAML and picks Replace or Append here. -->
    <div v-if="showImportOverlay" class="export-overlay" @click.self="closeImport">
      <div class="export-panel">
        <div class="export-panel-header">
          <span>Paste YAML to import</span>
          <span class="export-panel-hint">Paste exported YAML below, then choose Replace or Append</span>
        </div>
        <textarea
          ref="importTextarea"
          class="export-panel-text"
          placeholder="positions:&#10;  - position: 12.34&#10;    ..."
          v-model="importText"
        ></textarea>
        <div v-if="importError" class="import-error">{{ importError }}</div>
        <div class="export-panel-buttons">
          <button @click="fileInput?.click()" class="import-btn-text" title="Load from a .yaml file">Load file…</button>
          <span class="import-buttons-spacer"></span>
          <button @click="applyImport('replace')" class="send-d3-btn">Replace</button>
          <button @click="applyImport('append')" class="send-d3-btn">Append</button>
          <button @click="closeImport" class="remove-btn">Cancel</button>
        </div>
      </div>
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
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
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

// localStorage keys for persisting state across plugin reloads
const STORAGE_KEY_POSITIONS = 'markerMadness.positions'
const STORAGE_KEY_PREFIX = 'markerMadness.notePrefix'

// Read a persisted value from localStorage, tolerating the sandboxed webview
// where storage may be unavailable or empty.
const loadStored = (key, fallback) => {
  try {
    const raw = localStorage.getItem(key)
    return raw === null ? fallback : JSON.parse(raw)
  } catch (error) {
    console.warn(`Could not load "${key}" from localStorage:`, error)
    return fallback
  }
}

// Write a value to localStorage, ignoring failures (private mode, quota, etc.)
const saveStored = (key, value) => {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch (error) {
    console.warn(`Could not save "${key}" to localStorage:`, error)
  }
}

// Store the list of captured playhead positions (restored from localStorage)
const restoredPositions = loadStored(STORAGE_KEY_POSITIONS, [])
const storedPositions = ref(Array.isArray(restoredPositions) ? restoredPositions : [])

// Ref for file input element
const fileInput = ref(null)

// Transient status line shown under the toolbar (e.g. "Copied 3 position(s)").
const copyStatus = ref('')
let copyStatusTimer = null
const flashStatus = (message) => {
  copyStatus.value = message
  if (copyStatusTimer) clearTimeout(copyStatusTimer)
  copyStatusTimer = setTimeout(() => { copyStatus.value = '' }, 3000)
}

// When the clipboard is unavailable (sandboxed webview blocks both the async
// Clipboard API and execCommand), we surface the YAML in this overlay so the
// user can select-all and copy it manually. Non-empty => overlay visible.
const exportText = ref('')
const exportTextarea = ref(null)

// Paste-in import overlay state. The file <input> and confirm()/alert() are
// blocked in the sandbox, so import is driven by pasted YAML + in-DOM buttons.
const showImportOverlay = ref(false)
const importText = ref('')
const importError = ref('')
const importTextarea = ref(null)

// State for number key shortcuts (1-9 to jump to markers)
const numberKeysArmed = ref(false)

// State for the marker hotkey (` to add a marker)
const markerKeyArmed = ref(false)

// Global prefix applied to every note written to d3, so plugin-added notes can
// be told apart from manually-added ones. A '_' is appended after the
// user-typed prefix, e.g. prefix "SHOW" -> note "SHOW_<label>".
const restoredPrefix = loadStored(STORAGE_KEY_PREFIX, '')
const notePrefix = ref(typeof restoredPrefix === 'string' ? restoredPrefix : '')

// Persist markers and prefix to localStorage whenever they change so they
// survive plugin reloads. Deep-watch positions since labels/order mutate.
watch(storedPositions, value => saveStored(STORAGE_KEY_POSITIONS, value), { deep: true })
watch(notePrefix, value => saveStored(STORAGE_KEY_PREFIX, value))

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
const capturePosition = async (position, transport, timecode, beat) => {
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
    // The d3 timeline beat at capture time. Stored so the marker can be written
    // back to d3 as a note via track.setNoteAtBeat() with no time->beat math.
    beat: typeof beat === 'number' ? beat : null,
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

// POST a block of Python to the director and verify it ran. The execute API
// returns { status, d3Log, pythonLog, returnValue }; a non-zero status.code
// means the script raised. NOTE: scripts run as Python 2.7 on the server.
const executePython = async (script) => {
  const response = await fetch(`${apiBase()}/api/session/python/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ script })
  })

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  const result = await response.json()
  if (result.status && result.status.code !== 0) {
    throw new Error(`Python execute failed: ${result.status.message || JSON.stringify(result.status)}`)
  }
  return result
}

// Send the stored markers to d3 as timeline notes. Each marker carries the
// beat it was captured at, so we write it directly with track.setNoteAtBeat()
// — no time->beat conversion needed. Markers are grouped by track so each note
// lands on the track it was captured on, loaded by uid (preferred) or name.
const sendNotesToD3 = async () => {
  // Only markers that have both a beat and a label are meaningful as notes.
  const writable = storedPositions.value.filter(
    m => typeof m.beat === 'number' && (m.label || '').trim() !== ''
  )

  if (writable.length === 0) {
    console.warn('No markers with a beat and a label to send.')
    return
  }

  // Prefix to distinguish plugin-added notes from manual ones. When set, each
  // note becomes "<prefix>_<label>".
  const prefix = notePrefix.value.trim()

  // Group markers by the track they belong to.
  const byTrack = new Map()
  for (const m of writable) {
    const key = m.trackUid || m.track || ''
    if (!byTrack.has(key)) {
      byTrack.set(key, { uid: m.trackUid || '', notes: [] })
    }
    const note = prefix ? `${prefix}_${m.label}` : m.label
    byTrack.get(key).notes.push({ beat: m.beat, note })
  }

  // Build a Python 2.7 script that resolves each track and sets its notes.
  // Values are JSON-encoded so strings are safely escaped inside the Python
  // source. A track is resolved by its UID (UidManager) when we have one,
  // otherwise we fall back to the director's currently-loaded track.
  const groups = Array.from(byTrack.values())
  const script = [
    'import json',
    `groups = json.loads(${JSON.stringify(JSON.stringify(groups))})`,
    'uidMgr = UidManager.get()',
    'written = 0',
    'for g in groups:',
    '    track = None',
    "    if g['uid']:",
    '        try:',
    "            track = uidMgr.getResource(int(g['uid']))",
    '        except Exception:',
    '            track = None',
    '    if track is None:',
    '        track = state.localOrDirectorState().track',
    '    if track is None:',
    '        continue',
    "    for n in g['notes']:",
    "        track.setNoteAtBeat(float(n['beat']), n['note'])",
    '        written += 1',
    'return written'
  ].join('\n')

  try {
    const result = await executePython(script)
    console.log(`Sent ${writable.length} note(s) to d3. returnValue:`, result.returnValue)
  } catch (error) {
    console.error('Error sending notes to d3:', error)
  }
}

// Serialize the stored positions to a Marker Madness YAML string.
const buildExportYaml = () => {
  const data = {
    positions: storedPositions.value.map(item => ({
      position: item.position,
      transport: item.transport || 'default',
      track: item.track || '',
      trackUid: item.trackUid || '',
      // The d3-computed timecode string shown for the marker
      timecode: item.timecode || '',
      // The d3 timeline beat at capture time (used for setNoteAtBeat)
      beat: typeof item.beat === 'number' ? item.beat : null,
      // The per-marker note shown in the UI label input
      label: item.label || ''
    }))
  }
  return dump(data, { indent: 2 })
}

// Copy text to the clipboard, returning whether it succeeded. d3's CEF webview
// never accepts file downloads, so "export" is a clipboard copy. We try the
// modern async Clipboard API first, then fall back to a hidden <textarea> +
// execCommand('copy') for older/locked-down hosts.
const copyText = async (text) => {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch (error) {
    console.warn('Clipboard API write failed, trying execCommand fallback:', error)
  }

  try {
    const textarea = document.createElement('textarea')
    textarea.value = text
    // Keep it off-screen but selectable.
    textarea.style.position = 'fixed'
    textarea.style.top = '-9999px'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.focus()
    textarea.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(textarea)
    return ok
  } catch (error) {
    console.warn('execCommand copy fallback failed:', error)
    return false
  }
}

// "Export" the stored positions by copying their YAML to the clipboard. If both
// clipboard paths are blocked, open the manual-copy overlay as a last resort.
const exportPositions = async () => {
  let yamlString
  try {
    yamlString = buildExportYaml()
  } catch (error) {
    console.error('Error serializing positions:', error)
    flashStatus('Failed to export positions (see console).')
    return
  }

  const count = storedPositions.value.length
  if (await copyText(yamlString)) {
    flashStatus(`Copied ${count} position(s) as YAML.`)
  } else {
    // Couldn't copy programmatically — show the YAML for manual select-and-copy.
    exportText.value = yamlString
    await nextTick()
    exportTextarea.value?.focus()
    exportTextarea.value?.select()
  }
}

// Retry the copy from inside the manual-copy overlay.
const copyExportText = async () => {
  if (await copyText(exportText.value)) {
    flashStatus('Copied to clipboard.')
    exportText.value = ''
  } else {
    // Still blocked: re-select so the user can Ctrl+C themselves.
    exportTextarea.value?.focus()
    exportTextarea.value?.select()
  }
}

// Close the manual-copy overlay.
const closeExportOverlay = () => {
  exportText.value = ''
}

// Normalize a raw imported position into our internal marker shape.
const normalizeImported = pos => ({
  position: pos.position,
  transport: pos.transport || 'default',
  track: pos.track || '',
  trackUid: pos.trackUid || '',
  timecode: pos.timecode || '',
  beat: typeof pos.beat === 'number' ? pos.beat : null,
  label: pos.label || ''
})

// Open the paste-in import overlay. This mirrors the export overlay and is the
// sandbox-robust path: the file <input> and native dialogs (confirm/alert) are
// blocked inside d3's webview, so the user pastes YAML and chooses Replace or
// Append with in-DOM buttons.
const openImport = () => {
  importText.value = ''
  importError.value = ''
  showImportOverlay.value = true
  nextTick(() => importTextarea.value?.focus())
}

const closeImport = () => {
  showImportOverlay.value = false
}

// Parse the pasted YAML into validated, normalized positions, or throw.
const parseImportText = () => {
  const data = load(importText.value)
  if (!data || !Array.isArray(data.positions)) {
    throw new Error('Invalid YAML. Expected an object with a "positions" array.')
  }
  const valid = data.positions.filter(
    pos => typeof pos.position === 'number' && pos.position >= 0
  )
  if (valid.length === 0) {
    throw new Error('No valid positions found.')
  }
  return valid.map(normalizeImported)
}

// Apply the pasted YAML, either replacing or appending to existing markers.
const applyImport = (mode) => {
  let positions
  try {
    positions = parseImportText()
  } catch (error) {
    console.error('Error importing positions:', error)
    importError.value = error.message
    return
  }

  if (mode === 'replace') {
    storedPositions.value = positions
  } else {
    storedPositions.value.push(...positions)
  }
  showImportOverlay.value = false
  flashStatus(`Imported ${positions.length} position(s) (${mode}).`)
}

// Convenience for the desktop browser: read a chosen file into the paste box.
// File selection may not work inside the sandbox, hence it's optional.
const loadFileIntoImport = async (event) => {
  const file = event.target.files[0]
  if (!file) {
    return
  }
  try {
    importText.value = await file.text()
    importError.value = ''
  } catch (error) {
    console.error('Could not read file:', error)
    importError.value = `Could not read file: ${error.message}`
  }
  // Reset so the same file can be chosen again.
  event.target.value = ''
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
  if (copyStatusTimer) clearTimeout(copyStatusTimer)
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

.note-prefix-input {
  width: 9rem;
  padding: 0.5rem 0.6rem;
  border: 1px solid #424242;
  border-radius: 4px;
  font-size: 0.9rem;
  color: #e0e0e0;
  background-color: #2a2a2a;
  font-family: inherit;
  transition: border-color 0.2s ease;
}

.note-prefix-input:focus {
  outline: none;
  border-color: #64b5f6;
}

.note-prefix-input::placeholder {
  color: #757575;
  font-style: italic;
}

.send-d3-btn {
  padding: 0.5rem 1rem;
  background-color: #1976d2;
  color: white;
  border: 1px solid #1565c0;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: background-color 0.2s ease, border-color 0.2s ease;
}

.send-d3-btn:hover {
  background-color: #1565c0;
  border-color: #0d47a1;
}

.copy-status {
  text-align: center;
  color: #81c784;
  font-size: 0.85rem;
  margin: 0 0 0.4rem;
}

.export-overlay {
  position: fixed;
  inset: 0;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  z-index: 1000;
}

.export-panel {
  width: 100%;
  max-width: 640px;
  background-color: #1e1e1e;
  border: 1px solid #424242;
  border-radius: 6px;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.export-panel-header {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  color: #ffffff;
  font-size: 1rem;
}

.export-panel-hint {
  color: #9e9e9e;
  font-size: 0.8rem;
  font-style: italic;
}

.export-panel-text {
  width: 100%;
  height: 40vh;
  resize: vertical;
  padding: 0.6rem;
  border: 1px solid #424242;
  border-radius: 4px;
  background-color: #121212;
  color: #e0e0e0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.85rem;
  white-space: pre;
}

.export-panel-buttons {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.5rem;
}

.import-buttons-spacer {
  flex: 1;
}

.import-btn-text {
  padding: 0.5rem 0.8rem;
  background-color: #424242;
  color: #e0e0e0;
  border: 1px solid #616161;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: background-color 0.2s ease, border-color 0.2s ease;
}

.import-btn-text:hover {
  background-color: #4a4a4a;
  border-color: #757575;
}

.import-error {
  color: #ef9a9a;
  font-size: 0.85rem;
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
