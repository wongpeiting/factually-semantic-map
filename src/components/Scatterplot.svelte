<script>
    import { onMount } from 'svelte';
    import { scaleLinear, scaleOrdinal } from 'd3-scale';
    import { max, min } from 'd3-array';
  import { schemeTableau10 } from 'd3-scale-chromatic';
  import { select, zoom, zoomIdentity } from 'd3';

  export let data = [];
  export let domainColumn = "category";
  export let opacity = 1;
  export let selectedValues = new Set();
  export let searchQuery = "";
  export let showAnnotations = true;
  export let highlightedData = [];
  export let startDate = null;  // Add these new props
  export let endDate = null;    // Add these new props
  export let uniqueValues = [];
  export let hoveredData = null; // Export hoveredData for binding
  export let selectedData = null; // Export selectedData for pinning
  export let clusterLabels = []; // Labels to show on map regions


    // let annotations = [
    //     { x: 60, y: 140, radius: 40, label: "Articles about motor vehicle crashes.", label_x: -50, label_y: 130 },
    //     { x: 970, y: 320, radius: 70, label: "Sports Articles", label_x: -50, label_y: -100 }
    // ];

    let annotations = [];

  let canvas;
  let containerEl; // wrapper element whose size controls the canvas
    let ctx;

    let containerWidth = 800;
    let containerHeight = 600;

    const margin = { top: 40, right: 400, bottom: 60, left: 320 };
    const radius = 10;

  let lastHoveredData = null;
  let t = zoomIdentity; // d3-zoom transform
  const MIN_SCALE = 0.5;
  const MAX_SCALE = 20;
    $: highlightedSet = new Set(highlightedData.map(d => d.id));
  $: uniqueDomainCount = new Set(data.map(d => d[domainColumn])).size;

  // Jiggle animation state
  let isJiggling = false;
  let jiggleStartTime = 0;
  let jiggleAnimationId = null;
  const JIGGLE_DURATION = 800; // ms

  // Watch for selectedValues changes to trigger jiggle
  // Track the actual content, not just size, so switching between options triggers jiggle
  let prevSelectedKey = "";
  $: {
    const currentKey = [...selectedValues].sort().join("|");
    if (currentKey !== prevSelectedKey) {
      prevSelectedKey = currentKey;
      if (selectedValues.size > 0) {
        startJiggle();
      }
    }
  }

  function startJiggle() {
    isJiggling = true;
    jiggleStartTime = performance.now();
    if (jiggleAnimationId) cancelAnimationFrame(jiggleAnimationId);
    animateJiggle();
  }

  function animateJiggle() {
    const elapsed = performance.now() - jiggleStartTime;
    if (elapsed < JIGGLE_DURATION) {
      draw();
      jiggleAnimationId = requestAnimationFrame(animateJiggle);
    } else {
      isJiggling = false;
      draw();
    }
  }

  // d3-zoom behavior and selection to allow programmatic zooming
  let zoomBehavior;
  let canvasSel;

    // Helper function to check if text matches search query (supports regex)
    function matchesSearchQuery(text, query) {
        if (!query || !text) return false;
        
        try {
            // Try to use the query as a regex pattern
            const regex = new RegExp(query, 'i'); // case-insensitive
            return regex.test(text);
        } catch (e) {
            // If regex is invalid, fall back to simple string search
            return text.toLowerCase().includes(query.toLowerCase());
        }
    }


    
    $: innerWidth = containerWidth - margin.left - margin.right;
    $: innerHeight = containerHeight - margin.top - margin.bottom;
    
    // Guard scales against degenerate domains
    $: xDomainRaw = [min(data, d => d.x), max(data, d => d.x)];
    $: xDomain = (xDomainRaw[0] === xDomainRaw[1])
      ? [xDomainRaw[0] - 1, xDomainRaw[1] + 1]
      : xDomainRaw;
    $: xScale = scaleLinear()
      .domain(xDomain)
      .range([0, innerWidth]);
    
    $: yDomainRaw = [min(data, d => d.y), max(data, d => d.y)];
    $: yDomain = (yDomainRaw[0] === yDomainRaw[1])
      ? [yDomainRaw[0] - 1, yDomainRaw[1] + 1]
      : yDomainRaw;
    $: yScale = scaleLinear()
      .domain(yDomain)
      .range([innerHeight, 0]);
    
    // Reactive color scale to follow domainColumn and uniqueValues changes
    let colorScale;
    $: colorScale = scaleOrdinal(schemeTableau10)
      .domain(domainColumn ? uniqueValues : []);

  // Precompute date bounds (used for defaults when needed)
  $: minDate = data.length ? new Date(Math.min(...data.map(d => d.date.getTime()))) : null;
  $: maxDate = data.length ? new Date(Math.max(...data.map(d => d.date.getTime()))) : null;

    // HiDPI setup and responsive sizing based on container element
    let dpr = 1;
    function setupCanvasDPI() {
      if (!canvas || !containerEl) return;
      const rect = containerEl.getBoundingClientRect();
      // Keep containerWidth/Height in CSS pixels to sync scales and mouse events
      if (rect.width > 0 && rect.height > 0) {
        containerWidth = Math.floor(rect.width);
        containerHeight = Math.floor(rect.height);
      }
      dpr = Math.max(window.devicePixelRatio || 1, 1);
      // Visually fill container; internal pixel size scaled for crispness
      canvas.style.width = '100%';
      canvas.style.height = '100%';
      canvas.width = Math.max(1, Math.floor(containerWidth * dpr));
      canvas.height = Math.max(1, Math.floor(containerHeight * dpr));
      ctx = canvas.getContext('2d');
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

  function draw() {
      console.log("Scatterplot draw() called, data.length:", data.length);
      if (!ctx || !data.length) return;

      ctx.clearRect(0, 0, containerWidth, containerHeight);
      ctx.save();
      // Apply d3 zoom/pan transform
      ctx.translate(t.x, t.y);
      ctx.scale(t.k, t.k);

      // Calculate jiggle offset if animating
      let jiggleOffset = 0;
      let jiggleScale = 1;
      if (isJiggling) {
        const elapsed = performance.now() - jiggleStartTime;
        const progress = elapsed / JIGGLE_DURATION;
        // Decaying oscillation: amplitude decreases over time
        const decay = Math.max(0, 1 - progress);
        // Multiple oscillations during the animation
        const oscillation = Math.sin(progress * Math.PI * 8);
        jiggleOffset = oscillation * decay * 4; // max 4 pixel offset
        jiggleScale = 1 + oscillation * decay * 0.3; // max 30% size increase
      }

      data.forEach(d => {
        // Use isActive and isHighlighted from filteredData
        ctx.beginPath();

        // Apply jiggle to active dots
        let dotX = margin.left + xScale(d.x);
        let dotY = margin.top + yScale(d.y);
        let dotRadius = Math.max(0.5, radius / t.k);

        if (isJiggling && d.isActive) {
          // Add jiggle offset and scale for active dots
          dotX += jiggleOffset / t.k;
          dotY += (jiggleOffset * 0.5) / t.k; // Slight vertical movement too
          dotRadius *= jiggleScale;
        }

        ctx.arc(dotX, dotY, dotRadius, 0, Math.PI * 2);
        // Handle semicolon-separated values by using the first value for color
        const domainVal = d[domainColumn] || "";
        const colorKey = domainVal.includes(";") ? domainVal.split(";")[0].trim() : domainVal;
        ctx.fillStyle = colorScale(colorKey);
        // Opacity logic:
        // - Active dots use slider value
        // - Inactive dots are much fainter
        const baseAlpha = Math.max(0.1, Math.min(1, opacity));
        ctx.globalAlpha = d.isActive ? baseAlpha : baseAlpha * 0.15;
        ctx.fill();
        ctx.globalAlpha = 1; // reset for next operations
      });

      // Draw cluster/region labels on the map (hide on small screens)
      if (clusterLabels && clusterLabels.length > 0 && containerWidth > 600) {
        ctx.globalAlpha = 0.85;
        ctx.textAlign = 'center';

        clusterLabels.forEach(label => {
          const screenX = margin.left + xScale(label.x);
          const screenY = margin.top + yScale(label.y);

          // Parse label to split main and "(Read: ...)" subtitle
          const match = label.label.match(/^(.+?)\s*\(Read:\s*(.+?)\)\s*$/);
          const mainText = match ? match[1].trim() : label.label;
          const subText = match ? match[2].trim() : null;

          // Draw main label (larger, bold)
          const mainFontSize = Math.max(12, 15 / t.k);
          ctx.font = `bold ${mainFontSize}px Arial`;
          ctx.textBaseline = subText ? 'bottom' : 'middle';

          // Draw text with white outline for readability
          ctx.strokeStyle = 'white';
          ctx.lineWidth = Math.max(2, 3 / t.k);
          ctx.strokeText(mainText, screenX, screenY);
          ctx.fillStyle = '#333';
          ctx.fillText(mainText, screenX, screenY);

          // Draw subtitle below (smaller)
          if (subText) {
            const subFontSize = Math.max(9, 11 / t.k);
            ctx.font = `${subFontSize}px Arial`;
            ctx.textBaseline = 'top';
            const subY = screenY + 2 / t.k; // Small gap below main text

            ctx.strokeStyle = 'white';
            ctx.lineWidth = Math.max(1.5, 2.5 / t.k);
            ctx.strokeText(subText, screenX, subY);
            ctx.fillStyle = '#555';
            ctx.fillText(subText, screenX, subY);
          }
        });
      }

      // Draw annotations only if showAnnotations is true
      if (showAnnotations) {
        annotations.forEach(annotation => {
          ctx.globalAlpha = 1;

          // Draw annotation circle
          ctx.beginPath();
          ctx.arc(annotation.x, annotation.y, annotation.radius, 0, Math.PI * 2);
          ctx.strokeStyle = "red";
          ctx.lineWidth = 2;
          ctx.setLineDash([5, 5]);
          ctx.stroke();

          // Set text properties for measuring
          const maxWidth = 180; // Maximum width for the label
          const lineHeight = 12; // Line height for wrapped text
          ctx.font = "16px Arial";
          
          // Calculate label bounding box
          const labelX = annotation.x + annotation.label_x;
          const labelY = annotation.y + annotation.label_y;
          
          // Determine text bounds by measuring and wrapping text
          let textWidth = 0;
          let textHeight = 0;
          let lines = [];
          let currentLine = "";
          
          // Process text wrapping to calculate height and width
          if (annotation.label) {
            const words = annotation.label.split(" ");
            let line = "";
            
            words.forEach((word, index) => {
              const testLine = line + word + " ";
              const testWidth = ctx.measureText(testLine).width;
              
              if (testWidth > maxWidth && index > 0) {
                lines.push(line);
                textWidth = Math.max(textWidth, ctx.measureText(line).width);
                line = word + " ";
              } else {
                line = testLine;
              }
            });
            
            lines.push(line);
            textWidth = Math.max(textWidth, ctx.measureText(line).width);
            textHeight = lineHeight * lines.length;
          }
          
          // Label rectangle bounds
          const rectX = labelX;
          const rectY = labelY - lineHeight; // Offset to account for text baseline
          const rectWidth = textWidth;
          const rectHeight = textHeight;
          
          // Find closest point on the rectangle to the circle center
          // First determine which side of the rectangle is closest to the circle center
          let closestX, closestY;
          
          // Calculate x-coordinate of closest point
          if (annotation.x < rectX) {
            closestX = rectX;
          } else if (annotation.x > rectX + rectWidth) {
            closestX = rectX + rectWidth;
          } else {
            closestX = annotation.x;
          }
          
          // Calculate y-coordinate of closest point
          if (annotation.y < rectY) {
            closestY = rectY;
          } else if (annotation.y > rectY + rectHeight) {
            closestY = rectY + rectHeight;
          } else {
            closestY = annotation.y;
          }
          
          // Calculate the starting point of the line on the circle's outline
          const angle = Math.atan2(closestY - annotation.y, closestX - annotation.x);
          const startX = annotation.x + annotation.radius * Math.cos(angle);
          const startY = annotation.y + annotation.radius * Math.sin(angle);

          // Draw line connecting the circle outline to the closest point on the rectangle
          ctx.setLineDash([]); // Solid line for the connector
          ctx.beginPath();
          ctx.moveTo(startX, startY);
          ctx.lineTo(closestX, closestY);
          ctx.strokeStyle = "red";
          ctx.lineWidth = 1;
          ctx.stroke();

          // Draw label with wrapping
          if (annotation.label) {
            ctx.font = "16px Arial";
            ctx.fillStyle = "red";
            // increase line height between lines of t3ext
            const lineHeight = 16; // Adjusted line height for better readability

            // Draw each line of text
            lines.forEach((line, index) => {
              ctx.fillText(line, labelX, labelY + index * lineHeight);
            });
          }
        });
      }

      ctx.setLineDash([]); // Reset line dash

      // Draw selected (pinned) point with distinct styling
      if (selectedData) {
        const baseX = margin.left + xScale(selectedData.x);
        const baseY = margin.top + yScale(selectedData.y);
        ctx.beginPath();
        ctx.arc(baseX, baseY, Math.max(0.5, (radius + 2) / t.k), 0, Math.PI * 2);
        ctx.fillStyle = colorScale(selectedData[domainColumn]);
        ctx.globalAlpha = 1;
        ctx.fill();
        ctx.strokeStyle = '#1976d2';
        ctx.lineWidth = Math.max(1, 3 / t.k);
        ctx.stroke();
      }

      // Draw hovered point (only if different from selected)
      if (hoveredData && hoveredData !== selectedData) {
        const baseX = margin.left + xScale(hoveredData.x);
        const baseY = margin.top + yScale(hoveredData.y);
        ctx.beginPath();
        ctx.arc(baseX, baseY, Math.max(0.5, radius / t.k), 0, Math.PI * 2);
        ctx.fillStyle = colorScale(hoveredData[domainColumn]);
        ctx.globalAlpha = 1;
        ctx.fill();
        ctx.strokeStyle = 'black';
        ctx.lineWidth = Math.max(1, 2 / t.k);
        ctx.stroke();
      }

      ctx.restore();
    }
    
  // Removed stale click handler from pre d3-zoom implementation
    
  function handleMouseMove(event) {
      const rect = canvas.getBoundingClientRect();
      
      // Calculate scaling ratio between internal canvas dimensions and displayed dimensions
      const scaleX = containerWidth / rect.width;
      const scaleY = containerHeight / rect.height;
      
  // Adjust mouse coordinates based on the scaling ratio (canvas pixel coords)
  const mouseX = (event.clientX - rect.left) * scaleX;
  const mouseY = (event.clientY - rect.top) * scaleY;
    
  // Inverse transform via d3-zoom
  const [adjustedX, adjustedY] = t.invert([mouseX, mouseY]);
    
      const foundData = data.find(d => {
        const worldX = margin.left + xScale(d.x);
        const worldY = margin.top + yScale(d.y);
        const dx = worldX - adjustedX;
        const dy = worldY - adjustedY;
        const isInRange = Math.sqrt(dx * dx + dy * dy) < (radius + 3) / t.k;

        // Apply the same intersection logic for interactivity
        const hasSearch = !!(searchQuery && String(searchQuery).trim().length);
        const inSearch = hasSearch
          ? (matchesSearchQuery(d.title ?? '', searchQuery) || matchesSearchQuery(d.text ?? '', searchQuery) || matchesSearchQuery(d.article_text ?? '', searchQuery) || matchesSearchQuery(d.summary ?? '', searchQuery))
          : true;
        const hasSelection = selectedValues && selectedValues.size > 0 && selectedValues.size < uniqueDomainCount;
        // Handle multi-target articles (semicolon-separated values)
        const fieldValue = d[domainColumn] ?? "";
        let inSelection = true;
        if (hasSelection) {
          if (fieldValue.startsWith("No target;")) {
            inSelection = selectedValues.has(fieldValue);
          } else {
            inSelection = selectedValues.has(fieldValue) ||
              [...selectedValues].some(sv => fieldValue.includes(sv));
          }
        }
        const inDateRange = (startDate && endDate)
          ? (d.date >= startDate && d.date <= endDate)
          : true;
        const isActive = inSearch && inSelection && inDateRange;

        return isInRange && isActive;
      });

  if (foundData) {
        hoveredData = foundData;
        lastHoveredData = foundData;
        // indicate interactivity
        canvas.style.cursor = 'pointer';
      } else {
        hoveredData = null;
        lastHoveredData = null;
        canvas.style.cursor = 'crosshair';
      }

      draw();
    }

    function handleClick(event) {
      const rect = canvas.getBoundingClientRect();
      const scaleX = containerWidth / rect.width;
      const scaleY = containerHeight / rect.height;
  const mouseX = (event.clientX - rect.left) * scaleX;
  const mouseY = (event.clientY - rect.top) * scaleY;
      const [adjustedX, adjustedY] = t.invert([mouseX, mouseY]);

      const foundData = data.find(d => {
        const worldX = margin.left + xScale(d.x);
        const worldY = margin.top + yScale(d.y);
        const dx = worldX - adjustedX;
        const dy = worldY - adjustedY;
        // Keep hit radius in screen pixels by scaling threshold by 1/k
        const isInRange = Math.sqrt(dx * dx + dy * dy) < (radius + 3) / t.k;

        // Apply the same intersection logic for clicks
        const hasSearch = !!(searchQuery && String(searchQuery).trim().length);
        const inSearch = hasSearch
          ? (matchesSearchQuery(d.title ?? '', searchQuery) || matchesSearchQuery(d.text ?? '', searchQuery) || matchesSearchQuery(d.article_text ?? '', searchQuery) || matchesSearchQuery(d.summary ?? '', searchQuery))
          : true;
        const hasSelection = selectedValues && selectedValues.size > 0 && selectedValues.size < uniqueDomainCount;
        // Handle multi-target articles (semicolon-separated values)
        const fieldValue = d[domainColumn] ?? "";
        let inSelection = true;
        if (hasSelection) {
          if (fieldValue.startsWith("No target;")) {
            inSelection = selectedValues.has(fieldValue);
          } else {
            inSelection = selectedValues.has(fieldValue) ||
              [...selectedValues].some(sv => fieldValue.includes(sv));
          }
        }
        const inDateRange = (startDate && endDate)
          ? (d.date >= startDate && d.date <= endDate)
          : true;
        const isActive = inSearch && inSelection && inDateRange;

        return isInRange && isActive;
      });

      if (!foundData) {
        // Clicking on empty space unpins
        selectedData = null;
        draw();
        return;
      }

      // If Ctrl/Cmd is held, open URL in new tab (if available)
      if (event.ctrlKey || event.metaKey) {
        const url = foundData.url || foundData.link || foundData.href || foundData.permalink || foundData.item_url;
        if (url && typeof window !== 'undefined') {
          window.open(url, '_blank', 'noopener,noreferrer');
        }
        return;
      }

      // Otherwise, pin/unpin the clicked point
      if (selectedData === foundData) {
        // Clicking the same point again unpins it
        selectedData = null;
      } else {
        // Pin the new point
        selectedData = foundData;
      }
      draw();
    }
    
    function handleMouseLeave() {
      hoveredData = lastHoveredData;
      draw();
    }
    
  let resizeObserver;
    onMount(() => {
      console.log("Scatterplot mounted, canvas:", canvas);
      ctx = canvas.getContext('2d');
      console.log("Canvas context:", ctx);
      setupCanvasDPI();
      // Observe size changes for responsiveness / DPR changes
      if (window.ResizeObserver) {
    resizeObserver = new ResizeObserver(() => {
          setupCanvasDPI();
          draw();
        });
    resizeObserver.observe(containerEl);
      }
      // Setup d3-zoom for wheel, double-click, and touch/pinch
  zoomBehavior = zoom()
        .scaleExtent([MIN_SCALE, MAX_SCALE])
        .filter((event) => {
          // Allow wheel, touch, and dblclick; allow panning with primary button without modifiers
          const e = event;
          if (e.type === 'wheel' || e.type === 'touchstart' || e.type === 'touchmove') return true;
          if (e.type === 'mousedown') return e.button === 0 && !e.ctrlKey && !e.metaKey && !e.shiftKey;
          return !e.ctrlKey && !e.metaKey && !e.shiftKey;
        })
        .on('zoom', (event) => {
          t = event.transform;
          draw();
        });
  canvasSel = select(canvas);
  canvasSel.call(zoomBehavior);
      draw();
      return () => {
        if (resizeObserver) resizeObserver.disconnect();
      };
    });

  // (Manual pan/zoom handlers removed in favor of d3-zoom)
    
    $: if (ctx) {
        opacity, selectedValues, searchQuery, showAnnotations, domainColumn, startDate, endDate, selectedData, clusterLabels; // Watch these props
        if (data.length) draw(); // Redraw when any of these change
    }

    // Programmatic zoom controls
    function zoomBy(factor, evt) {
      evt?.stopPropagation?.();
      if (!canvasSel || !zoomBehavior) return;
      const cx = containerWidth / 2;
      const cy = containerHeight / 2;
      canvasSel.transition().duration(200).call(zoomBehavior.scaleBy, factor, [cx, cy]);
    }
    function zoomIn(evt) { zoomBy(1.25, evt); }
    function zoomOut(evt) { zoomBy(1/1.25, evt); }
    function resetZoom(evt) {
      evt?.stopPropagation?.();
      if (!canvasSel || !zoomBehavior) return;
      canvasSel.transition().duration(200).call(zoomBehavior.transform, zoomIdentity);
    }
</script>

<div class="chart-container" bind:this={containerEl}>
    <div class="zoom-controls" aria-label="Zoom controls">
      <button class="zoom-btn" aria-label="Zoom in" title="Zoom in" on:click={zoomIn}>+</button>
      <button class="zoom-btn" aria-label="Zoom out" title="Zoom out" on:click={zoomOut}>−</button>
      <button class="zoom-btn" aria-label="Reset zoom" title="Reset zoom" on:click={resetZoom}>⟲</button>
    </div>
    <canvas
      bind:this={canvas}
      width={containerWidth}
      height={containerHeight}
      on:mousemove={handleMouseMove}
      on:mouseleave={handleMouseLeave}
      on:click={handleClick}
    ></canvas>
</div>

<style>
    .chart-container {
      position: relative;
      display: flex;
      justify-content: center;
      align-items: center;
      flex-direction: column;
      width: 100%;
      height: 100%;
    }

    canvas {
      cursor: crosshair;
      border-radius: 0;
      background-color: var(--bg-canvas, #fafbfc);
      width: 100%;
      height: 100%;
      display: block;
    }

    .zoom-controls {
      position: absolute;
      bottom: 16px;
      right: 16px;
      display: flex;
      flex-direction: row;
      gap: 4px;
      z-index: 20;
      pointer-events: auto;
    }

    .zoom-btn {
      width: 32px;
      height: 32px;
      border-radius: 6px;
      border: 1px solid var(--border-subtle, rgba(0, 0, 0, 0.08));
      background: var(--bg-panel, rgba(255, 255, 255, 0.95));
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
      cursor: pointer;
      font-size: 16px;
      line-height: 1;
      padding: 0;
      color: var(--text-secondary, #4a5568);
      transition: all 0.15s ease;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .zoom-btn:hover {
      background: white;
      border-color: var(--accent, #3b82f6);
      color: var(--accent, #3b82f6);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
    }

    .zoom-btn:active {
      transform: scale(0.95);
    }

    @media (max-width: 768px) {
      .zoom-controls {
        bottom: 12px;
        right: 12px;
      }

      .zoom-btn {
        width: 36px;
        height: 36px;
        font-size: 18px;
      }
    }
</style>