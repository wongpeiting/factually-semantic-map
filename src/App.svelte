<script>
  import { onMount } from "svelte";
  import Papa from "papaparse";
  import Scatterplot from "./components/Scatterplot.svelte";
  import RangeSlider from "./components/RangeSlider.svelte";
  import DetailCard from "./components/DetailCard.svelte";
  import { scaleOrdinal } from 'd3-scale';
  import { schemeTableau10 } from 'd3-scale-chromatic';

  // Resolve data URL from query params (url | filename [+ bucket]) or env fallback
  let resolvedDataUrl = "";
  $: isDefaultRemote = /^https?:\/\//i.test(resolvedDataUrl);
  function resolveDataUrl() {
    try {
      const params = new URLSearchParams(window.location.search);
      const directUrl = params.get("url");
      const filename = params.get("filename");
      const bucket = params.get("bucket");

      // Highest priority: full URL provided
      if (directUrl && /^https?:\/\//i.test(directUrl)) return directUrl;

      // Build from filename and (optional) bucket
      if (filename) {
        // Determine base from bucket param or env
        let base = "";
        if (bucket) {
          if (/^https?:\/\//i.test(bucket)) {
            base = bucket;
          } else if (bucket.includes(".")) {
            // Looks like a host (e.g. my-bucket.s3.amazonaws.com or custom domain)
            base = `https://${bucket}`;
          } else {
            // Treat as bare S3 bucket name
            base = `https://${bucket}.s3.amazonaws.com`;
          }
        } else {
          // Env-configured default base (e.g. https://my-bucket.s3.amazonaws.com/)
          base =
            import.meta.env.VITE_S3_BASE_URL ||
            import.meta.env.VITE_DATA_BASE_URL ||
            "https://pink-slime-public.s3.amazonaws.com/";
        }
        if (base && !base.endsWith("/")) base += "/";
        return base ? base + filename : filename;
      }

      // Fallbacks: explicit env or local file in /public
      return import.meta.env.VITE_DATA_URL || "data.csv";
    } catch (e) {
      console.warn("Failed to resolve data URL from query params:", e);
      return import.meta.env.VITE_DATA_URL || "data.csv";
    }
  }

  let data = [],
    columns = [],
    domainColumn = "target",
    uniqueValues = [];
  let selectedValues = new Set();
  let opacity = 0.6,
    startDate = null,
    endDate = null;
  let filteredData = [],
    allDates = [];
  let startDateIndex = 0;
  let endDateIndex = 0;
  let isPlaying = false;
  let playInterval = null;
  let highlightedData = [];
  $: highlightedSet = new Set(highlightedData.map((d) => d.id));

  let searchQuery = "";
  let showAnnotations = false;
  let hoveredData = null;
  let clusterLabels = []; // Labels to show on map regions
  let selectedData = null; // Pinned/clicked data
  let filterCollapsed = false; // For mobile filter panel toggle

  // Display selected data if available, otherwise show hovered data
  $: displayedData = selectedData || hoveredData;

  // Color scale for the detail card
  $: colorScale = scaleOrdinal(schemeTableau10)
    .domain(domainColumn ? uniqueValues : []);

  // Computed min/max dates from actual data
  $: minDateFromData = allDates.length > 0 ? allDates[0] : null;
  $: maxDateFromData = allDates.length > 0 ? allDates[allDates.length - 1] : null;

  // Allow target, org, state, or pofma_ed as colour-by options
  $: allowedDomainColumns = columns.filter(
    (c) => c === "target" || c === "org" || c === "state" || c === "pofma_ed" || c === "directed_at",
  );

  // Display labels for column names
  const columnLabels = {
    target: "Directed at",
    directed_at: "Directed at",
    org: "Organisation",
    state: "State",
    pofma_ed: "POFMA ED",
  };

  // Strip "(Read: ...)" from topic labels for cleaner display
  // Highlight interesting categories with a star
  const featuredValues = ['General Clarification', 'General Explainer'];
  function formatValueLabel(val) {
    if (!val) return val;
    const str = String(val);
    const match = str.match(/^(.+?)\s*\(Read:\s*.+?\)\s*$/);
    const label = match ? match[1].trim() : str;
    // Add star for featured values
    if (featuredValues.includes(label)) {
      return `★ ${label}`;
    }
    return label;
  }
  $: {
    // Wait until columns are known before adjusting the selected domain
    if (!columns || columns.length === 0) {
      // do nothing until parsed
    } else if (
      allowedDomainColumns.length &&
      !allowedDomainColumns.includes(domainColumn)
    ) {
      domainColumn = allowedDomainColumns[0];
    } else if (allowedDomainColumns.length === 0) {
      domainColumn = "";
    }
  }

  // Update uniqueValues reactively when domainColumn or data changes
  // Split semicolon-separated values into individual options (for multi-target articles)
  // But keep "No target; ..." values intact
  $: if (domainColumn && data.length > 0) {
    uniqueValues = [
      ...new Set(
        data
          .flatMap((d) => {
            const val = d[domainColumn];
            if (val === undefined || val === null || val === "") return [];
            const strVal = String(val);
            // Don't split "No target; ..." values - keep them intact
            if (strVal.startsWith("No target;")) {
              return [strVal];
            }
            // Split other semicolon-separated values
            return strVal.includes(";")
              ? strVal.split(";").map(v => v.trim())
              : [strVal];
          })
      ),
    ].sort((a, b) => String(a).localeCompare(String(b)));
  }

  // Election date markers for the slider
  const electionDates = [
    { date: new Date('2020-07-10'), label: 'GE2020' },
    { date: new Date('2025-05-03'), label: 'GE2025' },
  ];

  // Calculate marker indices based on allDates array
  $: electionMarkers = allDates.length > 0 ? electionDates
    .map(ed => {
      // Find the closest date index
      let closestIndex = 0;
      let closestDiff = Infinity;
      allDates.forEach((d, i) => {
        const diff = Math.abs(d.getTime() - ed.date.getTime());
        if (diff < closestDiff) {
          closestDiff = diff;
          closestIndex = i;
        }
      });
      return { index: closestIndex, label: ed.label };
    })
    .filter(m => m.index >= 0 && m.index <= allDates.length - 1)
    : [];

  // Loading/progress state
  let isLoading = false;
  let loadPhase = "idle"; // 'downloading' | 'parsing' | 'idle'
  let loadBytes = 0;
  let loadTotal = 0;
  let loadProgress = 0; // 0-100 when total known

  function formatBytes(bytes) {
    if (!bytes || bytes <= 0) return "0 KB";
    const units = ["B", "KB", "MB", "GB", "TB"];
    let v = bytes;
    let i = 0;
    while (v >= 1024 && i < units.length - 1) {
      v /= 1024;
      i++;
    }
    const dp = i === 0 ? 0 : 1;
    return `${v.toFixed(dp)} ${units[i]}`;
  }

  onMount(async () => {
    try {
      isLoading = true;
      loadPhase = "downloading";
      loadBytes = 0;
      loadTotal = 0;
      loadProgress = 0;

      // Determine the final CSV URL once on mount
      resolvedDataUrl = resolveDataUrl();
      console.log("Loading data from:", resolvedDataUrl);

      const response = await fetch(resolvedDataUrl, {
        mode: "cors",
        cache: "no-store",
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const len = response.headers.get("content-length");
      loadTotal = len ? parseInt(len, 10) : 0;

      let csvText = "";
      if (response.body && response.body.getReader) {
        const reader = response.body.getReader();
        const chunks = [];
        let received = 0;
        // Stream and accumulate while reporting progress
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          chunks.push(value);
          received += value.byteLength;
          loadBytes = received;
          if (loadTotal) {
            loadProgress = Math.round((received / loadTotal) * 100);
          }
        }
        const full = new Uint8Array(received);
        let offset = 0;
        for (const c of chunks) {
          full.set(c, offset);
          offset += c.byteLength;
        }
        csvText = new TextDecoder().decode(full);
        console.log("CSV head:", csvText.split("\n").slice(0, 5).join("\n"));
      } else {
        // Fallback without streaming/progress
        csvText = await response.text();
      }

      // Parse phase (indeterminate)
      loadPhase = "parsing";
      await Promise.resolve(parseCSV(csvText));

      // Load cluster labels for map regions
      try {
        const labelsResponse = await fetch("cluster_labels.json");
        if (labelsResponse.ok) {
          clusterLabels = await labelsResponse.json();
          console.log("Loaded cluster labels:", clusterLabels);
        }
      } catch (e) {
        console.warn("Could not load cluster labels:", e);
      }

      loadPhase = "idle";
    } catch (err) {
      console.error("Failed to load CSV:", err);
    } finally {
      isLoading = false;
    }

    return () => {
      if (playInterval) clearInterval(playInterval);
    };
  });

  $: {
    // Determine if any filter is active
    const fullDateRange = allDates.length && startDateIndex === 0 && endDateIndex === allDates.length - 1;
    const hasSelection = selectedValues.size > 0 && selectedValues.size < uniqueValues.length;
    const hasSearch = searchQuery && searchQuery.trim().length > 0;

    filteredData = data.map((d) => {
      const inDateRange = (!startDate || d.date >= startDate) && (!endDate || d.date <= endDate);
      // Check if any selected value matches (exact match OR contained in semicolon-separated list)
      let inSelection = true;
      if (hasSelection) {
        const fieldValue = d[domainColumn] ?? "";
        // For "No target; ..." values, only do exact match
        // For others, also check if selected value is contained in semicolon-separated list
        if (fieldValue.startsWith("No target;")) {
          inSelection = selectedValues.has(fieldValue);
        } else {
          inSelection = selectedValues.has(fieldValue) ||
            [...selectedValues].some(sv => fieldValue.includes(sv));
        }
      }
      let inSearch = true;
      if (hasSearch) {
        try {
          const regex = new RegExp(searchQuery, "i");
          inSearch = regex.test(d.title ?? "") || regex.test(d.text ?? "") || regex.test(d.article_text ?? "") || regex.test(d.summary ?? "");
        } catch {
          const q = searchQuery.toLowerCase();
          inSearch = (d.title ?? "").toLowerCase().includes(q) ||
                     (d.text ?? "").toLowerCase().includes(q) ||
                     (d.article_text ?? "").toLowerCase().includes(q) ||
                     (d.summary ?? "").toLowerCase().includes(q);
        }
      }
      // Points are active if they pass all filters
      // Date range always applies, selection and search only if active
      const isActive = inDateRange && inSelection && inSearch;
      return {
        ...d,
        isActive,
        isHighlighted: isActive,
      };
    });
    console.log("filteredData length:", filteredData.length, "active:", filteredData.filter(d => d.isActive).length);
  }

  $: startPercent =
    allDates.length > 1 ? (startDateIndex / (allDates.length - 1)) * 100 : 0;
  $: endPercent =
    allDates.length > 1 ? (endDateIndex / (allDates.length - 1)) * 100 : 100;

  // Use actual max date from data instead of arbitrary cap
  $: maxAllowedIndex = allDates.length > 0 ? allDates.length - 1 : 0;

  function parseCSV(csvText) {
    // Lowercase headers before parsing
    const lines = csvText.split(/\r?\n/);
    if (lines.length > 0) {
      const headerLine = lines[0];
      const lowerHeader = headerLine
        .split(",")
        .map((h) => h.trim().toLowerCase())
        .join(",");
      lines[0] = lowerHeader;
      csvText = lines.join("\n");
    }
    const result = Papa.parse(csvText, { header: true });
    console.log("Parsed CSV fields:", result.meta.fields);
    console.log("Parsed rows (before filter):", result.data.length);
    console.log("Sample row:", result.data[0]);

    data = result.data
      .filter((d) => d.x && d.y && d.date)
      .map((d, i) => ({
        ...d,
        x: +d.x,
        y: +d.y,
        date: new Date(d.date),
        id: i,
      }));

    console.log("Data after filter:", data.length);
    console.log("Sample data point:", data[0]);
    console.log("domainColumn:", domainColumn);
    console.log("columns:", columns);
    console.log("allDates:", allDates.length, "from", allDates[0], "to", allDates[allDates.length-1]);

    columns = result.meta.fields || [];
    allDates = [...new Set(data.map((d) => d.date.getTime()))]
      .sort((a, b) => a - b)
      .map((t) => new Date(t));

    startDate = allDates[0];
    endDate = allDates[allDates.length - 1];
    startDateIndex = 0;
    endDateIndex = allDates.length - 1;
    updateDateIndices();

    if (domainColumn) {
      uniqueValues = [
        ...new Set(
          data
            .map((d) => d[domainColumn])
            .filter((v) => v !== undefined && v !== null && v !== ""),
        ),
      ].sort((a, b) => String(a).localeCompare(String(b)));
    }
  }

  function handleDomainChange(event) {
    domainColumn = event.target.value;
    uniqueValues = domainColumn
      ? [...new Set(data.map((d) => d[domainColumn]).filter(Boolean))].sort(
          (a, b) => String(a).localeCompare(String(b)),
        )
      : [];
    selectedValues = new Set();
    showAnnotations = false;
  }

  function handleSelectionChange(event) {
    const selectedOptions = [...event.target.selectedOptions].map(
      (o) => o.value,
    );

    // Check if "All" is selected or if all values are selected
    const hasAll = selectedOptions.includes("__ALL__");
    const allSelected = selectedOptions.length === uniqueValues.length;

    if (hasAll || allSelected || selectedOptions.length === 0) {
      // If "All" is selected, all values are selected, or none are selected, clear the selection
      selectedValues = new Set();
      highlightedData = [];
    } else {
      // Only update selection if a subset is chosen
      selectedValues = new Set(selectedOptions);
      highlightedData = data.filter(
        (d) =>
          selectedValues.has(d[domainColumn]) &&
          (!startDate || d.date >= startDate) &&
          (!endDate || d.date <= endDate),
      );
    }

    showAnnotations = false;
  }

  // Keep highlightedData in sync is handled by selection handlers for multi-select

  function updateSelectedDates(start, end, fromIndices = false) {
    if (fromIndices) {
      startDate = allDates[start] || allDates[0];
      endDate = allDates[end] || allDates[allDates.length - 1];
    } else {
      startDate = start;
      endDate = end;
    }
    showAnnotations = false;
    updateDateIndices();
  }

  function updateDateIndices() {
    if (startDate) {
      const timestamp = startDate.getTime();
      startDateIndex = Math.max(
        0,
        allDates.findIndex((d) => d.getTime() >= timestamp),
      );
    } else {
      startDateIndex = 0;
    }

    if (endDate) {
      const timestamp = endDate.getTime();
      let ei = -1;
      for (let i = allDates.length - 1; i >= 0; i--) {
        if (allDates[i].getTime() <= timestamp) {
          ei = i;
          break;
        }
      }
      endDateIndex = ei >= 0 ? ei : allDates.length - 1;
    } else {
      endDateIndex = allDates.length - 1;
    }

    if (startDateIndex > endDateIndex) startDateIndex = endDateIndex;
    if (endDateIndex < startDateIndex) endDateIndex = startDateIndex;
  }

  function handleDateChange(e, type) {
    if (e.detail !== undefined) {
      // Handle slider events
      if (type === "start") {
        startDateIndex = e.detail;
        if (startDateIndex > endDateIndex) startDateIndex = endDateIndex;
      } else {
        endDateIndex = e.detail;
        if (endDateIndex < startDateIndex) endDateIndex = startDateIndex;
      }
      // Update dates based on the indices
      updateSelectedDates(startDateIndex, endDateIndex, true);
    } else {
      // Handle date input events
      const newDate = e.target.value ? new Date(e.target.value) : null;

      if (type === "start") {
        updateSelectedDates(newDate, endDate);
      } else {
        updateSelectedDates(startDate, newDate);
      }

      // Update indices based on the new dates
      updateDateIndices();
    }
  }

  function formatDateInput(date) {
    return date ? date.toISOString().split("T")[0] : "";
  }

  function handleFileUpload(event) {
    const file = event.target.files[0];
    if (file) {
      const reader = new FileReader();
      showAnnotations = false;
      reader.onload = (e) => parseCSV(e.target.result);
      reader.readAsText(file);
    }
  }

  function shiftDateRange(days) {
    const rangeDuration = endDateIndex - startDateIndex;
    let newStartIndex = startDateIndex + days;
    let newEndIndex = endDateIndex + days;

    // Handle boundary conditions
    if (newStartIndex < 0) {
      newStartIndex = 0;
      newEndIndex = Math.min(rangeDuration, allDates.length - 1);
    }

    if (newEndIndex >= allDates.length) {
      newEndIndex = allDates.length - 1;
      newStartIndex = Math.max(0, newEndIndex - rangeDuration);
    }

    startDateIndex = newStartIndex;
    endDateIndex = newEndIndex;
    updateSelectedDates(startDateIndex, endDateIndex, true);
  }

  function togglePlayPause() {
    if (isPlaying) {
      clearInterval(playInterval);
      isPlaying = false;
    } else {
      isPlaying = true;
      showAnnotations = false;
      playInterval = setInterval(() => {
        if (endDateIndex >= allDates.length - 1) {
          clearInterval(playInterval);
          isPlaying = false;
          return;
        }
        shiftDateRange(1);
      }, 500);
    }
  }

  function handleSearch(event) {
    searchQuery = event.target.value;
    showAnnotations = false;
  }

  function handleOpacityChange() {
    showAnnotations = false;
  }

  function resetFilters() {
    // Stop playback if running
    if (isPlaying && playInterval) {
      clearInterval(playInterval);
      isPlaying = false;
    }

    // Reset domain to default ('target' if available, then 'org', otherwise first allowed)
    const defaultDomain = columns.includes("target")
      ? "target"
      : columns.includes("org")
      ? "org"
      : allowedDomainColumns[0] || "";
    domainColumn = defaultDomain;

    // Clear selection and highlights
    selectedValues = new Set();
    highlightedData = [];

    // Reset search and annotations
    searchQuery = "";
    showAnnotations = false;

    // Reset opacity to initial default
    opacity = 0.02;

    // Force Svelte to update opacity binding
    opacity = +opacity;

    // Reset date range to full
    if (allDates.length) {
      startDateIndex = 0;
      endDateIndex = allDates.length - 1;
      updateSelectedDates(startDateIndex, endDateIndex, true);
    } else {
      startDate = null;
      endDate = null;
      startDateIndex = 0;
      endDateIndex = 0;
    }
  }
</script>

<!-- App Layout - Modern Minimalist Design -->
<div class="app-container">
  <!-- Compact Header -->
  <header class="header">
    <div class="title-row">
      <h1 class="title">What Factually Moves to Correct 👀</h1>
      <div class="header-right">
        <a href="https://github.com/wongpeiting/factually-semantic-map" target="_blank" rel="noopener noreferrer" class="help-btn" title="View on GitHub">?</a>
        <span class="data-date">Data as of Feb 5, 2026.</span>
      </div>
    </div>
    <p class="tagline">Drawing on cases published on Factually — Singapore's state-run fact-checking site used alongside the Protection from Online Falsehoods and Manipulation Act (POFMA) — this semantic map shows how government-identified falsehoods cluster.</p>
    <p class="subtitle">
      Each dot represents a disputed claim, revealing where official corrections concentrate.
    </p>
  </header>

  <!-- Main visualization area with floating panels -->
  <main class="main-content">
    <!-- Scatterplot fills the entire area -->
    <div class="scatterplot-wrapper">
      {#if filteredData.length}
        <Scatterplot
          data={filteredData}
          {domainColumn}
          {selectedValues}
          {opacity}
          {searchQuery}
          {showAnnotations}
          {highlightedData}
          {startDate}
          {endDate}
          uniqueValues={uniqueValues}
          {clusterLabels}
          bind:hoveredData
          bind:selectedData
        />
      {:else if isLoading}
        <div class="loading-overlay">
          <div class="progress-wrap">
            <div class="progress-header">
              {#if loadPhase === "downloading"}
                Downloading data...
              {:else if loadPhase === "parsing"}
                Processing...
              {:else}
                Loading...
              {/if}
            </div>
            {#if loadPhase === "downloading"}
              {#if loadTotal}
                <div class="progress-bar">
                  <div class="progress-fill" style="width: {loadProgress}%"></div>
                </div>
                <div class="progress-label">
                  {loadProgress}% ({formatBytes(loadBytes)} / {formatBytes(loadTotal)})
                </div>
              {:else}
                <div class="progress-bar indeterminate"></div>
                <div class="progress-label">{formatBytes(loadBytes)}</div>
              {/if}
            {:else}
              <div class="progress-bar indeterminate"></div>
            {/if}
          </div>
        </div>
      {:else}
        <div class="loading-overlay">
          <p class="waiting-text">Waiting for data...</p>
        </div>
      {/if}
    </div>

    <!-- Floating Filter Panel (Left) -->
    <aside class="floating-panel filter-panel" class:collapsed={filterCollapsed}>
      <button class="panel-toggle" on:click={() => filterCollapsed = !filterCollapsed} aria-label="Toggle filters">
        {#if filterCollapsed}
          <span class="toggle-arrow">›</span>
        {:else}
          <span class="toggle-arrow">‹</span>
        {/if}
      </button>

      {#if !filterCollapsed}
        <div class="panel-content">
          <div class="panel-header">
            <span class="panel-title">Filters</span>
            <button class="reset-btn" on:click={resetFilters}>Reset</button>
          </div>

          <div class="filter-section">
            <label class="filter-label" for="search-input">Search</label>
            <input
              id="search-input"
              type="text"
              class="filter-input"
              placeholder="Search keywords..."
              bind:value={searchQuery}
              on:input={handleSearch}
            />
          </div>

          {#if allowedDomainColumns.length}
            <div class="filter-section">
              <label class="filter-label" for="domain-column">Colour by</label>
              <select
                id="domain-column"
                class="filter-select"
                on:change={handleDomainChange}
                bind:value={domainColumn}
              >
                <option value="" disabled>Select column</option>
                {#each allowedDomainColumns as column}
                  <option value={column}>{columnLabels[column] || column}</option>
                {/each}
              </select>
            </div>
          {/if}

          {#if uniqueValues.length}
            <div class="filter-section">
              <label class="filter-label" for="value-select">Highlight</label>
              <select
                id="value-select"
                multiple
                size="5"
                class="filter-select multi-select"
                on:change={handleSelectionChange}
              >
                <option value="__ALL__" selected={selectedValues.size === 0}>★ Show All</option>
                {#each uniqueValues as item}
                  <option value={item} selected={selectedValues.has(item)}>{formatValueLabel(item)}</option>
                {/each}
              </select>
            </div>
          {/if}

          <div class="filter-section">
            <label class="filter-label" for="opacity-slider">Opacity</label>
            <input
              id="opacity-slider"
              type="range"
              class="filter-range"
              min="0.1"
              max="1"
              step="0.05"
              bind:value={opacity}
              on:input={handleOpacityChange}
            />
          </div>

          <div class="filter-section date-section">
            <span class="filter-label">Date range</span>
            <div class="date-inputs">
              <input
                id="start-date"
                type="date"
                class="filter-input date-input"
                value={formatDateInput(startDate)}
                max={formatDateInput(maxDateFromData)}
                on:change={(e) => handleDateChange(e, "start")}
              />
              <span class="date-separator">–</span>
              <input
                id="end-date"
                type="date"
                class="filter-input date-input"
                value={formatDateInput(endDate)}
                max={formatDateInput(maxDateFromData)}
                on:change={(e) => handleDateChange(e, "end")}
              />
            </div>

            <RangeSlider
              min={0}
              max={maxAllowedIndex}
              bind:startValue={startDateIndex}
              bind:endValue={endDateIndex}
              markers={electionMarkers}
              on:startChange={(e) => handleDateChange(e, "start")}
              on:endChange={(e) => handleDateChange(e, "end")}
            />

            <div class="date-navigation">
              <button class="nav-btn" on:click={() => shiftDateRange(-7)}>-1W</button>
              <button class="nav-btn" on:click={() => shiftDateRange(-1)}>-1D</button>
              <button class="nav-btn play-btn" on:click={togglePlayPause}>
                {#if isPlaying}⏸{:else}▶{/if}
              </button>
              <button class="nav-btn" on:click={() => shiftDateRange(1)}>+1D</button>
              <button class="nav-btn" on:click={() => shiftDateRange(7)}>+1W</button>
            </div>
          </div>

          <details class="info-accordion">
            <summary>About this map</summary>
            <div class="info-content">
              <p>
                A semantic map shows how pieces of language relate to each other based on meaning. Each dot here represents a correction or clarification published on Factually.gov.sg. Dots with similar misinformation themes appear closer together. Explore patterns on the map by shortening the time range and scrubbing the timeline, or conducting a search.
              </p>
            </div>
          </details>
        </div>
      {/if}
    </aside>

    <!-- Floating Detail Panel (Right) - only visible when data selected -->
    <aside class="floating-panel detail-panel" class:visible={!!displayedData}>
      {#if displayedData}
        <button class="panel-close" on:click={() => selectedData = null} aria-label="Close">×</button>
        <div class="panel-content">
          <DetailCard
            hoveredData={displayedData}
            {data}
            {domainColumn}
            {colorScale}
            {searchQuery}
            isPinned={!!selectedData}
            on:unpin={() => selectedData = null}
          />
        </div>
      {/if}
    </aside>

    </main>
</div>

<style>
  /* Modern Minimalist Styles */
  :global(html, body, #app) {
    height: 100%;
    overflow: hidden;
    margin: 0;
    padding: 0;
  }

  .app-container {
    display: flex;
    flex-direction: column;
    height: 100vh;
    background: var(--bg-canvas, #fafbfc);
    overflow: hidden;
  }

  /* Compact Header */
  .header {
    padding: var(--spacing-md, 1rem) var(--spacing-lg, 1.5rem);
    background: var(--bg-panel, rgba(255, 255, 255, 0.95));
    border-bottom: 1px solid var(--border-subtle, rgba(0, 0, 0, 0.08));
    flex-shrink: 0;
  }

  .title-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 1rem;
    margin-bottom: 0.5rem;
  }

  .title {
    font-size: 2.5rem;
    font-weight: 700;
    color: var(--text-primary, #1a202c);
    margin: 0;
    letter-spacing: -0.02em;
  }

  .header-right {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.5rem;
    flex-shrink: 0;
  }

  .data-date {
    font-size: 0.7rem;
    color: var(--text-muted, #64748b);
    white-space: nowrap;
  }

  .tagline {
    font-size: 1.1rem;
    color: var(--text-primary, #1a202c);
    margin: 0.5rem 0 0.25rem 0;
    line-height: 1.5;
    font-weight: 500;
  }

  .subtitle {
    font-size: 0.85rem;
    color: var(--text-muted, #64748b);
    margin: 0;
    line-height: 1.6;
  }

  /* Main Content Area */
  .main-content {
    flex: 1;
    position: relative;
    overflow: hidden;
  }

  /* Scatterplot fills entire area */
  .scatterplot-wrapper {
    position: absolute;
    inset: 0;
    background: var(--bg-canvas, #fafbfc);
  }

  /* Loading states */
  .loading-overlay {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg-canvas, #fafbfc);
  }

  .waiting-text {
    color: var(--text-muted, #64748b);
    font-size: 0.9rem;
  }

  .progress-wrap {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    width: 280px;
  }

  .progress-header {
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--text-secondary, #4a5568);
  }

  .progress-bar {
    height: 4px;
    background: rgba(0, 0, 0, 0.08);
    border-radius: 2px;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: var(--accent, #3b82f6);
    transition: width 100ms linear;
  }

  .progress-bar.indeterminate {
    position: relative;
  }

  .progress-bar.indeterminate::before {
    content: "";
    position: absolute;
    left: -40%;
    width: 40%;
    height: 100%;
    background: var(--accent, #3b82f6);
    animation: indeterminate 1.2s ease-in-out infinite;
  }

  @keyframes indeterminate {
    0% { left: -40%; }
    100% { left: 100%; }
  }

  .progress-label {
    font-size: 0.75rem;
    color: var(--text-muted, #64748b);
  }

  /* Floating Panels */
  .floating-panel {
    position: absolute;
    background: var(--bg-panel, rgba(255, 255, 255, 0.95));
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-radius: var(--radius-md, 12px);
    box-shadow: var(--shadow-panel, 0 4px 24px rgba(0, 0, 0, 0.1));
    z-index: 100;
    transition: transform var(--transition-normal, 0.25s ease), opacity var(--transition-normal, 0.25s ease);
  }

  /* Filter Panel (Left) */
  .filter-panel {
    top: var(--spacing-md, 1rem);
    left: var(--spacing-md, 1rem);
    width: 280px;
    max-height: calc(100% - 2rem);
    display: flex;
    flex-direction: column;
  }

  .filter-panel.collapsed {
    width: 48px;
    min-height: 120px;
  }

  .filter-panel.collapsed .panel-toggle {
    right: auto;
    left: 50%;
    transform: translate(-50%, -50%);
  }

  .panel-toggle {
    position: absolute;
    top: 50%;
    right: -12px;
    transform: translateY(-50%);
    width: 24px;
    height: 48px;
    border: none;
    background: var(--bg-panel, rgba(255, 255, 255, 0.95));
    border-radius: 0 var(--radius-sm, 6px) var(--radius-sm, 6px) 0;
    box-shadow: 2px 0 8px rgba(0, 0, 0, 0.1);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1rem;
    color: var(--text-muted, #64748b);
    transition: color var(--transition-fast, 0.15s ease);
  }

  .panel-toggle:hover {
    color: var(--text-primary, #1a202c);
  }

  .toggle-arrow {
    font-weight: 600;
  }

  .filter-panel.collapsed .panel-toggle {
    right: -36px;
    border-radius: var(--radius-sm, 6px);
  }

  .panel-content {
    padding: var(--spacing-md, 1rem);
    overflow-y: auto;
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-md, 1rem);
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: var(--spacing-sm, 0.5rem);
    border-bottom: 1px solid var(--border-subtle, rgba(0, 0, 0, 0.08));
  }

  .panel-title {
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted, #64748b);
  }

  .reset-btn {
    padding: 0.25rem 0.5rem;
    font-size: 0.7rem;
    font-weight: 500;
    background: transparent;
    border: 1px solid var(--border-subtle, rgba(0, 0, 0, 0.08));
    border-radius: var(--radius-sm, 6px);
    color: var(--text-secondary, #4a5568);
    cursor: pointer;
    transition: all var(--transition-fast, 0.15s ease);
  }

  .reset-btn:hover {
    background: var(--accent-light, rgba(59, 130, 246, 0.1));
    border-color: var(--accent, #3b82f6);
    color: var(--accent, #3b82f6);
  }

  /* Filter Sections */
  .filter-section {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs, 0.25rem);
  }

  .filter-label,
  span.filter-label {
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted, #64748b);
    display: block;
  }

  .filter-input,
  .filter-select {
    padding: 0.5rem 0.75rem;
    font-size: 0.875rem;
    border: 1px solid var(--border-subtle, rgba(0, 0, 0, 0.08));
    border-radius: var(--radius-sm, 6px);
    background: white;
    color: var(--text-primary, #1a202c);
    transition: border-color var(--transition-fast, 0.15s ease), box-shadow var(--transition-fast, 0.15s ease);
    width: 100%;
    box-sizing: border-box;
  }

  .filter-input:focus,
  .filter-select:focus {
    outline: none;
    border-color: var(--accent, #3b82f6);
    box-shadow: 0 0 0 3px var(--accent-light, rgba(59, 130, 246, 0.1));
  }

  .filter-input::placeholder {
    color: var(--text-muted, #64748b);
  }

  .multi-select {
    min-height: 120px;
    max-height: 160px;
  }

  .filter-range {
    width: 100%;
    height: 4px;
    appearance: none;
    -webkit-appearance: none;
    background: rgba(0, 0, 0, 0.08);
    border-radius: 2px;
    cursor: pointer;
  }

  .filter-range::-webkit-slider-thumb {
    appearance: none;
    -webkit-appearance: none;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: var(--accent, #3b82f6);
    cursor: pointer;
    transition: transform var(--transition-fast, 0.15s ease);
  }

  .filter-range::-webkit-slider-thumb:hover {
    transform: scale(1.15);
  }

  /* Date Section */
  .date-section {
    gap: var(--spacing-sm, 0.5rem);
  }

  .date-inputs {
    display: flex;
    align-items: center;
    gap: var(--spacing-xs, 0.25rem);
  }

  .date-input {
    flex: 1;
    font-size: 0.75rem;
    padding: 0.375rem 0.5rem;
  }

  .date-separator {
    color: var(--text-muted, #64748b);
    font-size: 0.875rem;
  }

  .date-navigation {
    display: flex;
    gap: 4px;
    margin-top: var(--spacing-xs, 0.25rem);
  }

  .nav-btn {
    flex: 1;
    padding: 0.375rem;
    font-size: 0.7rem;
    font-weight: 500;
    background: white;
    border: 1px solid var(--border-subtle, rgba(0, 0, 0, 0.08));
    border-radius: var(--radius-sm, 6px);
    color: var(--text-secondary, #4a5568);
    cursor: pointer;
    transition: all var(--transition-fast, 0.15s ease);
  }

  .nav-btn:hover {
    background: var(--accent-light, rgba(59, 130, 246, 0.1));
    border-color: var(--accent, #3b82f6);
    color: var(--accent, #3b82f6);
  }

  .play-btn {
    background: var(--accent, #3b82f6);
    border-color: var(--accent, #3b82f6);
    color: white;
  }

  .play-btn:hover {
    background: #2563eb;
    border-color: #2563eb;
    color: white;
  }

  /* Info Accordion */
  .info-accordion {
    margin-top: auto;
    padding-top: var(--spacing-md, 1rem);
    border-top: 1px solid var(--border-subtle, rgba(0, 0, 0, 0.08));
  }

  .info-accordion summary {
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--text-muted, #64748b);
    cursor: pointer;
    list-style: none;
    user-select: none;
  }

  .info-accordion summary::-webkit-details-marker {
    display: none;
  }

  .info-accordion summary::before {
    content: "+ ";
  }

  .info-accordion[open] summary::before {
    content: "− ";
  }

  .info-content {
    margin-top: var(--spacing-sm, 0.5rem);
  }

  .info-content p {
    font-size: 0.8rem;
    line-height: 1.6;
    color: var(--text-secondary, #4a5568);
    margin: 0;
  }

  /* Detail Panel (Right) */
  .detail-panel {
    top: var(--spacing-md, 1rem);
    right: var(--spacing-md, 1rem);
    width: 360px;
    max-height: calc(100% - 2rem);
    transform: translateX(calc(100% + 2rem));
    opacity: 0;
    pointer-events: none;
    display: flex;
    flex-direction: column;
  }

  .detail-panel.visible {
    transform: translateX(0);
    opacity: 1;
    pointer-events: auto;
  }

  .panel-close {
    position: absolute;
    top: 0.5rem;
    right: 0.5rem;
    width: 28px;
    height: 28px;
    border: none;
    background: transparent;
    border-radius: var(--radius-sm, 6px);
    cursor: pointer;
    font-size: 1.25rem;
    color: var(--text-muted, #64748b);
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all var(--transition-fast, 0.15s ease);
    z-index: 10;
  }

  .panel-close:hover {
    background: rgba(0, 0, 0, 0.05);
    color: var(--text-primary, #1a202c);
  }

  .detail-panel .panel-content {
    padding: var(--spacing-md, 1rem);
    padding-top: var(--spacing-lg, 1.5rem);
    flex: 1;
    overflow-y: auto;
    min-height: 0;
  }

  /* Help button */
  .help-btn {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: var(--bg-canvas, #fafbfc);
    border: 1px solid var(--border-subtle, rgba(0, 0, 0, 0.12));
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--text-muted, #64748b);
    text-decoration: none;
    transition: all 0.15s ease;
  }

  .help-btn:hover {
    background: var(--accent, #3b82f6);
    color: white;
    border-color: var(--accent, #3b82f6);
  }

  /* Responsive - Tablet */
  @media (max-width: 1024px) {
    .filter-panel {
      width: 240px;
    }

    .detail-panel {
      width: 320px;
    }

    .title {
      font-size: 2rem;
    }

    .subtitle {
      font-size: 0.85rem;
    }
  }

  /* Responsive - Mobile */
  @media (max-width: 768px) {
    :global(html, body, #app) {
      height: auto;
      overflow: auto;
    }

    .app-container {
      height: auto;
      min-height: 100vh;
      overflow: auto;
    }

    .header {
      padding: 0.75rem 1rem;
      position: relative;
    }

    .title-row {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.5rem;
    }

    .header-right {
      display: none;
    }

    .help-btn {
      position: absolute;
      top: 0.75rem;
      right: 0.75rem;
    }

    .title {
      font-size: 1.35rem;
      line-height: 1.2;
      padding-right: 40px;
    }

    .tagline {
      font-size: 0.8rem;
      margin: 0.5rem 0 0.25rem 0;
      line-height: 1.4;
    }

    .subtitle {
      font-size: 0.7rem;
      max-width: none;
      color: var(--text-muted, #64748b);
    }

    .main-content {
      position: relative;
      display: flex;
      flex-direction: column;
      min-height: 0;
    }

    .scatterplot-wrapper {
      position: relative;
      height: 50vh;
      min-height: 280px;
      flex-shrink: 0;
    }

    /* Hide floating panels on mobile, show simple stacked layout */
    .floating-panel {
      position: relative;
      top: auto;
      left: auto;
      right: auto;
      bottom: auto;
      width: 100%;
      max-height: none;
      border-radius: 0;
      transform: none;
      opacity: 1;
      pointer-events: auto;
      box-shadow: none;
      border-top: 1px solid var(--border-subtle, rgba(0, 0, 0, 0.08));
    }

    .filter-panel {
      order: 2;
    }

    .filter-panel.collapsed {
      width: 100%;
    }

    .panel-toggle {
      display: none !important;
    }

    .toggle-arrow {
      display: none;
    }

    .detail-panel {
      order: 3;
      display: none;
    }

    .detail-panel.visible {
      display: flex;
    }

    .panel-content {
      padding: 1rem;
    }

    .multi-select {
      min-height: 80px;
      max-height: 100px;
    }

    .date-input {
      font-size: 0.75rem;
    }

    .date-navigation {
      flex-wrap: wrap;
    }

    .nav-btn {
      min-width: 40px;
    }

    .info-accordion {
      display: none;
    }
  }

  /* Responsive - Small Mobile */
  @media (max-width: 480px) {
    .header {
      padding: 0.5rem 0.75rem;
    }

    .title {
      font-size: 1.15rem;
    }

    .tagline {
      font-size: 0.75rem;
    }

    .subtitle {
      font-size: 0.7rem;
    }

    .scatterplot-wrapper {
      height: 45vh;
      min-height: 240px;
    }

    .panel-content {
      padding: 0.75rem;
    }

    .filter-label {
      font-size: 0.6rem;
    }

    .filter-input,
    .filter-select {
      font-size: 0.75rem;
      padding: 0.35rem 0.5rem;
    }
  }
</style>
