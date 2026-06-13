<!-- This handles real-time updates from Designer. This is from the Disguise Developer website https://developer.disguise.one/plugins/getting-started/ -->

<template>
   <div class="playhead-section">
      <div class="playhead-header">
        <button @click="handleCapture" class="capture-btn">Add Marker</button>
        <span class="playhead-label">Playhead Position</span>
        <span class="time-code">{{ timecode || '--:--:--:--' }}</span>
      </div>
   </div>
</template>
  
<script setup>
  import { onMounted, onUnmounted } from 'vue'

  // Define the liveUpdate prop
  const props = defineProps({
    liveUpdate: {
      type: Object,
      required: true
    },
    transportName: {
      type: String,
      default: 'default'
    },
    // When true, the ` key adds a marker
    hotkeyArmed: {
      type: Boolean,
      default: false
    }
  })

  // Define emits
  const emit = defineEmits(['capture-position'])

  // Get the transport name (defaults to 'default')
  const transportNameValue = props.transportName || 'default'
  const transportManagerKey = `transportManager:${transportNameValue}`
  
  // Auto-subscribe to playhead position (seconds) — the canonical value used
  // for capturing markers and seeking.
  const { player_tRender } = props.liveUpdate.autoSubscribe(transportManagerKey, ['object.player.tRender'])

  // Subscribe to the d3-computed timecode for display, plus the underlying
  // timeline beat. d3 evaluates these on the server, baking in the timeline's
  // TC tags, offset starts, tag regions, and frame rate, so they match d3's own
  // transport readout exactly. The beat is captured alongside the marker so it
  // can be written back as a note via track.setNoteAtBeat() without any
  // client-side time->beat conversion. autoSubscribe can't name a compound
  // expression, so we use subscribe() with explicit names.
  const { timecode, beat } = props.liveUpdate.subscribe(transportManagerKey, {
    timecode:
      'object.beatToTimecode(object.player.track.timeToBeat(object.player.tRender)).__str__()',
    beat: 'object.player.track.timeToBeat(object.player.tRender)'
  })

  // Handle capture button click
  const handleCapture = () => {
    console.log('Capture button clicked, player_tRender:', player_tRender.value)
    if (player_tRender.value !== undefined) {
      emit('capture-position', player_tRender.value, transportNameValue, timecode.value, beat.value)
      console.log('Emitted capture-position event with value:', player_tRender.value)
    } else {
      console.warn('player_tRender is undefined, cannot capture position')
    }
  }

  // Hotkey: ` adds a marker when armed (ignored while typing in a field)
  const handleHotkey = (event) => {
    if (!props.hotkeyArmed || event.key !== '`') return
    const tag = event.target?.tagName
    if (tag === 'INPUT' || tag === 'TEXTAREA') return
    event.preventDefault()
    handleCapture()
  }

  onMounted(() => {
    window.addEventListener('keydown', handleHotkey)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', handleHotkey)
  })
</script>
  
<style scoped>
  .playhead-section {
    margin: 0.3rem 0.5rem;
    padding: 0.6rem 1rem;
    border: 1px solid #424242;
    border-radius: 4px;
    background-color: #1e1e1e;
    color: #e0e0e0;
  }

  .playhead-header {
    display: flex;
    justify-content: flex-start;
    align-items: center;
    gap: 0.75rem;
  }

  .playhead-label {
    color: #b0b0b0;
    font-size: 0.9rem;
    font-weight: normal;
  }

  .time-code {
    font-size: 0.9rem;
    font-weight: normal;
    color: #ffffff;
    font-variant-numeric: tabular-nums;
  }

  .capture-btn {
    padding: 0.5rem 1rem;
    background-color: #388e3c;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 1rem;
    transition: background-color 0.2s ease;
  }

  .capture-btn:hover {
    background-color: #2e7d32;
  }

  /* Mobile styles - reduce horizontal margins for maximum width */
  @media (max-width: 768px) {
    .playhead-section {
      margin-top: 0.3rem;
      margin-bottom: 0.3rem;
      margin-left: 0;
      margin-right: 0;
    }
  }
</style>
