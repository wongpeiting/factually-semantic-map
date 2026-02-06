<script>
  import { createEventDispatcher } from 'svelte';

  export let min = 0;
  export let max = 100;
  export let startValue;
  export let endValue;
  export let markers = []; // Array of { index, label } for important dates

  const dispatch = createEventDispatcher();
  
  let slider;
  let startThumb;
  let endThumb;
  let isDragging = false;
  let currentThumb = null;
  let sliderRect = null;
  let rangeWidth = 0; // Store width of range when dragging center
  
  $: startPercent = max > min ? ((startValue - min) / (max - min)) * 100 : 0;
  $: endPercent = max > min ? ((endValue - min) / (max - min)) * 100 : 100;

  // Calculate marker positions
  $: markerPositions = markers.map(m => ({
    ...m,
    percent: max > min ? ((m.index - min) / (max - min)) * 100 : 0
  }));
  
  function handleMouseDown(event, thumb) {
    isDragging = true;
    currentThumb = thumb;
    sliderRect = slider.getBoundingClientRect();
    
    if (thumb === 'range') {
      // Store the width of the range for maintaining during drag
      rangeWidth = endValue - startValue;
    }
    
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  }
  
  function handleMouseMove(event) {
    if (!isDragging) return;
    
    const percentage = Math.min(Math.max(0, (event.clientX - sliderRect.left) / sliderRect.width), 1);
    const newValue = Math.round(percentage * (max - min) + min);
    
    if (currentThumb === 'start') {
      startValue = Math.min(newValue, endValue);
      dispatch('startChange', startValue);
    } else if (currentThumb === 'end') {
      endValue = Math.max(newValue, startValue);
      dispatch('endChange', endValue);
    } else if (currentThumb === 'range') {
      // Move entire range, keeping width constant
      let newStart = newValue - Math.floor(rangeWidth / 2);
      let newEnd = newValue + Math.ceil(rangeWidth / 2);
      
      // Handle boundary conditions
      if (newStart < min) {
        newStart = min;
        newEnd = min + rangeWidth;
      }
      
      if (newEnd > max) {
        newEnd = max;
        newStart = max - rangeWidth;
      }
      
      // Final boundary check
      newStart = Math.max(min, newStart);
      newEnd = Math.min(max, newEnd);
      
      // Update values and dispatch events
      startValue = newStart;
      endValue = newEnd;
      dispatch('startChange', startValue);
      dispatch('endChange', endValue);
    }
  }
  
  function handleMouseUp() {
    isDragging = false;
    window.removeEventListener('mousemove', handleMouseMove);
    window.removeEventListener('mouseup', handleMouseUp);
  }
  
  // Touch support
  function handleTouchStart(event, thumb) {
    event.preventDefault();
    isDragging = true;
    currentThumb = thumb;
    sliderRect = slider.getBoundingClientRect();
    
    if (thumb === 'range') {
      rangeWidth = endValue - startValue;
    }
    
    window.addEventListener('touchmove', handleTouchMove, { passive: false });
    window.addEventListener('touchend', handleTouchEnd);
  }
  
  function handleTouchMove(event) {
    event.preventDefault();
    if (!isDragging) return;
    
    const touch = event.touches[0];
    const percentage = Math.min(Math.max(0, (touch.clientX - sliderRect.left) / sliderRect.width), 1);
    const newValue = Math.round(percentage * (max - min) + min);
    
    if (currentThumb === 'start') {
      startValue = Math.min(newValue, endValue);
      dispatch('startChange', startValue);
    } else if (currentThumb === 'end') {
      endValue = Math.max(newValue, startValue);
      dispatch('endChange', endValue);
    } else if (currentThumb === 'range') {
      // Move entire range, keeping width constant
      let newStart = newValue - Math.floor(rangeWidth / 2);
      let newEnd = newValue + Math.ceil(rangeWidth / 2);
      
      // Handle boundary conditions
      if (newStart < min) {
        newStart = min;
        newEnd = min + rangeWidth;
      }
      
      if (newEnd > max) {
        newEnd = max;
        newStart = max - rangeWidth;
      }
      
      // Final boundary check
      newStart = Math.max(min, newStart);
      newEnd = Math.min(max, newEnd);
      
      // Update values and dispatch events
      startValue = newStart;
      endValue = newEnd;
      dispatch('startChange', startValue);
      dispatch('endChange', endValue);
    }
  }
  
  function handleTouchEnd() {
    isDragging = false;
    window.removeEventListener('touchmove', handleTouchMove);
    window.removeEventListener('touchend', handleTouchEnd);
  }
</script>

<div
  class="range-slider"
  bind:this={slider}
  style="--start-percent: {startPercent}%; --end-percent: {endPercent}%;"
>
  <div class="track">
    <div
      class="track-inner"
      on:mousedown={(e) => handleMouseDown(e, 'range')}
      on:touchstart={(e) => handleTouchStart(e, 'range')}
    ></div>
  </div>

  <!-- Election date markers -->
  {#each markerPositions as marker}
    <div
      class="marker"
      style="left: {marker.percent}%"
      title={marker.label}
    >
      <div class="marker-line"></div>
      <div class="marker-label">{marker.label}</div>
    </div>
  {/each}

  <div
    class="thumb start-thumb"
    bind:this={startThumb}
    style="left: {startPercent}%"
    on:mousedown={(e) => handleMouseDown(e, 'start')}
    on:touchstart={(e) => handleTouchStart(e, 'start')}
  ></div>

  <div
    class="thumb end-thumb"
    bind:this={endThumb}
    style="left: {endPercent}%"
    on:mousedown={(e) => handleMouseDown(e, 'end')}
    on:touchstart={(e) => handleTouchStart(e, 'end')}
  ></div>
</div>

<style>
  .range-slider {
    position: relative;
    height: 24px;
    padding: 8px 0;
    width: 100%;
    user-select: none;
  }

  .track {
    position: absolute;
    width: 100%;
    height: 4px;
    background: rgba(0, 0, 0, 0.08);
    border-radius: 2px;
    top: 50%;
    transform: translateY(-50%);
  }

  .track-inner {
    position: absolute;
    height: 100%;
    background: var(--accent, #3b82f6);
    left: var(--start-percent);
    right: calc(100% - var(--end-percent));
    border-radius: 2px;
    cursor: grab;
    transition: background 0.15s ease;
  }

  .track-inner:hover {
    background: #2563eb;
  }

  .track-inner:active {
    cursor: grabbing;
  }

  .thumb {
    position: absolute;
    width: 14px;
    height: 14px;
    background: white;
    border: 2px solid var(--accent, #3b82f6);
    border-radius: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    cursor: pointer;
    z-index: 2;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
  }

  .start-thumb {
    z-index: 3;
  }

  .end-thumb {
    z-index: 3;
  }

  .thumb:hover {
    transform: translate(-50%, -50%) scale(1.15);
    box-shadow: 0 0 0 4px var(--accent-light, rgba(59, 130, 246, 0.15));
  }

  .thumb:focus {
    outline: none;
    box-shadow: 0 0 0 4px var(--accent-light, rgba(59, 130, 246, 0.25));
  }

  /* Election date markers */
  .marker {
    position: absolute;
    top: 50%;
    transform: translateX(-50%);
    z-index: 1;
    pointer-events: none;
  }

  .marker-line {
    width: 1px;
    height: 16px;
    background: #ef4444;
    transform: translateY(-50%);
    opacity: 0.7;
  }

  .marker-label {
    position: absolute;
    top: 12px;
    left: 50%;
    transform: translateX(-50%);
    font-size: 0.55rem;
    color: #ef4444;
    white-space: nowrap;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.02em;
  }
</style>
