<!-- This handles real-time updates from Designer. This is from the Disguise Developer website https://developer.disguise.one/plugins/getting-started/ -->

<template>
   <div class="playhead-section">
      <h2>Playhead Position</h2>
      <div class="playhead-value">
        <div class="time-display">
          <span class="time-seconds">{{ player_tRender !== undefined ? player_tRender.toFixed(2) : '0.00' }}s</span>
        </div>
      </div>
      <button @click="handleCapture" class="capture-btn">Capture Position</button>
   </div>
</template>
  
<script setup>

  // Define the liveUpdate prop
  const props = defineProps({
    liveUpdate: {
      type: Object,
      required: true
    },
    transportName: {
      type: String,
      default: 'default'
    }
  })

  // Define emits
  const emit = defineEmits(['capture-position'])

  // Get the transport name (defaults to 'default')
  const transportNameValue = props.transportName || 'default'
  const transportManagerKey = `transportManager:${transportNameValue}`
  
  // Auto-subscribe to playhead position
  const { player_tRender } = props.liveUpdate.autoSubscribe(transportManagerKey, ['object.player.tRender'])

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
    margin: 0.5rem 0;
    margin-left: 0.5rem;
    margin-right: 0.5rem;
    padding: 1rem;
    border: 1px solid #424242;
    border-radius: 4px;
    background-color: #1e1e1e;
    color: #e0e0e0;
  }

  .playhead-section h2 {
    color: #ffffff;
    margin-top: 0;
    margin-bottom: 0.5rem;
    text-align: center;
  }
  
  .playhead-value {
    font-size: 1.2rem;
    font-weight: bold;
    margin-bottom: 1rem;
    margin-top: 0;
    color: #e0e0e0;
    display: flex;
    justify-content: center;
  }

  .time-display {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.25rem;
  }

  .time-seconds {
    font-size: 1.2rem;
    color: #ffffff;
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
    display: block;
    margin: 0 auto;
  }

  .capture-btn:hover {
    background-color: #2e7d32;
  }

  /* Mobile styles - reduce horizontal margins for maximum width */
  @media (max-width: 768px) {
    .playhead-section {
      margin-top: 0.5rem;
      margin-bottom: 0.5rem;
      margin-left: 0;
      margin-right: 0;
    }
  }
</style>
