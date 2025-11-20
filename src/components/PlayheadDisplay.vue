<!-- This handles real-time updates from Designer. This is from the Disguise Developer website https://developer.disguise.one/plugins/getting-started/ -->

<template>
   <div class="playhead-section">
      <h2>Playhead Position</h2>
      <div class="playhead-value">
        <div class="time-display">
          <span class="time-seconds">{{ player_tRender !== undefined ? player_tRender.toFixed(2) : '0.00' }}s</span>
          <span class="time-timecode">{{ timecodeValue }}</span>
        </div>
      </div>
      <button @click="handleCapture" class="capture-btn">Capture Position</button>
   </div>
</template>
  
<script setup>
  import { computed } from 'vue'

  // Define the liveUpdate prop
  const props = defineProps({
    liveUpdate: {
      type: Object,
      required: true
    }
  })

  // Define emits
  const emit = defineEmits(['capture-position'])

  // Auto-subscribe to playhead position
  const { player_tRender } = props.liveUpdate.autoSubscribe('transportManager:default', ['object.player.tRender'])
  
  // Subscribe to timecode from the transport (the actual timecode from the timecode cue)
  // Try different property paths to get the timecode from the track
  const { value: transportTimecode1 } = props.liveUpdate.autoSubscribe('transportManager:default', ['object.getTransport("default").timecode'])
  const { value: transportTimecode2 } = props.liveUpdate.autoSubscribe('transportManager:default', ['object.getTransport("default").tcStatusString'])
  // Try getting timecode from the current track
  const { value: trackTimecode } = props.liveUpdate.autoSubscribe('transportManager:default', ['object.getTransport("default").track.timecode'])
  
  // Convert seconds to timecode format (HH:MM:SS:FF) as fallback
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
  
  // Use the actual timecode from transport/track, or fall back to calculated
  const timecodeValue = computed(() => {
    // Try track timecode first (from timecode cue), then transport timecode, then tcStatusString, then calculated
    return trackTimecode?.value || transportTimecode1?.value || transportTimecode2?.value || formatTimecode(player_tRender.value)
  })

  // Handle capture button click
  const handleCapture = () => {
    console.log('Capture button clicked, player_tRender:', player_tRender.value)
    if (player_tRender.value !== undefined) {
      emit('capture-position', player_tRender.value)
      console.log('Emitted capture-position event with value:', player_tRender.value)
    } else {
      console.warn('player_tRender is undefined, cannot capture position')
    }
  }
</script>
  
<style scoped>
  .playhead-section {
    margin: 1rem;
    padding: 1rem;
    border: 1px solid #ccc;
    border-radius: 4px;
  }
  
  .playhead-value {
    font-size: 1.2rem;
    font-weight: bold;
    margin-bottom: 1rem;
  }

  .time-display {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .time-seconds {
    font-size: 1.2rem;
  }

  .time-timecode {
    font-size: 1rem;
    font-family: 'Courier New', monospace;
    color: #666;
  }

  .capture-btn {
    padding: 0.5rem 1rem;
    background-color: #4CAF50;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 1rem;
  }

  .capture-btn:hover {
    background-color: #45a049;
  }
</style>
