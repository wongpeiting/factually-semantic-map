<script>
  import { onMount, createEventDispatcher } from 'svelte';
  import { scaleOrdinal } from 'd3-scale';
  import { schemeTableau10 } from 'd3-scale-chromatic';

  const dispatch = createEventDispatcher();

  export let hoveredData;
  export let domainColumn;
  export let data;
  export let colorScale;
  export let searchQuery = "";
  export let isPinned = false;
  export let labelOverride = null; // optional function(domain, value) -> label
  export let descriptionOverride = null; // optional function(domain, value) -> description

  let filteredData = [];
  let dates = [];
  let selectedDate = null;
  let isPlaying = false;
  let interval;

  onMount(() => {
      colorScale.domain(data.map(d => d[domainColumn]));
  });

  // Get first value from semicolon-separated string (for color lookup)
  function getFirstValue(val) {
    if (!val) return "";
    const str = String(val);
    return str.includes(";") ? str.split(";")[0].trim() : str;
  }

  // Parse topic to split main label and "Read:" subtitle
  // e.g., "Justice (Read: Death Penalty)" -> { main: "Justice", sub: "Death Penalty" }
  function parseTopicLabel(val) {
    if (!val) return { main: "", sub: "" };
    const str = String(val);
    const match = str.match(/^(.+?)\s*\(Read:\s*(.+?)\)\s*$/);
    if (match) {
      return { main: match[1].trim(), sub: match[2].trim() };
    }
    return { main: str, sub: "" };
  }

  // Function to highlight search terms in text
  function highlightText(text, query) {
    if (!query || !text) return text;

    try {
      // Try to use the query as a regex pattern
      const regex = new RegExp(`(${query})`, 'gi');
      return text.replace(regex, '<mark>$1</mark>');
    } catch (e) {
      // If regex is invalid, fall back to simple string search
      const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const regex = new RegExp(`(${escapedQuery})`, 'gi');
      return text.replace(regex, '<mark>$1</mark>');
    }
  }

</script>

<div class="detail-card">
  {#if hoveredData}
    {#if isPinned}
      <div class="pin-header">
        <span class="pin-indicator">📌 Pinned</span>
        <button class="unpin-btn" on:click={() => dispatch('unpin')}>✕</button>
      </div>
    {/if}
    <h1>{@html highlightText(hoveredData.title, searchQuery)}</h1>
    <div class="meta-row">
      <div class="meta-links">
        {#if hoveredData.url || hoveredData.link || hoveredData.href || hoveredData.permalink || hoveredData.item_url}
          <a class="article-link" href={hoveredData.url || hoveredData.link || hoveredData.href || hoveredData.permalink || hoveredData.item_url} target="_blank" rel="noopener noreferrer">
            View on Factually
          </a>
        {/if}
        {#if hoveredData.pofma_link}
          <a class="article-link" href={hoveredData.pofma_link} target="_blank" rel="noopener noreferrer">
            View POFMA release
          </a>
        {/if}
      </div>
      <span class="article-date">{hoveredData.date.toISOString().split('T')[0]}</span>
    </div>
    {#if domainColumn === 'topic' && parseTopicLabel(hoveredData[domainColumn]).sub}
      {@const parsed = parseTopicLabel(hoveredData[domainColumn])}
      <span class="topic-badge" style="background: {colorScale(getFirstValue(hoveredData[domainColumn]))};">
        <span class="topic-main">{parsed.main}</span>
        <span class="topic-sub">{parsed.sub}</span>
      </span>
    {:else}
      <span style="background: {colorScale(getFirstValue(hoveredData[domainColumn]))};">
        {labelOverride ? labelOverride(domainColumn, hoveredData[domainColumn]) : hoveredData[domainColumn]}
      </span>
    {/if}
    {#if descriptionOverride}
      {#if descriptionOverride(domainColumn, hoveredData[domainColumn])}
        <p><em>{descriptionOverride(domainColumn, hoveredData[domainColumn])}</em></p>
      {/if}
    {/if}
    {#if hoveredData.summary}
      <p class="summary">{@html highlightText(hoveredData.summary, searchQuery)}</p>
    {/if}
    <p>{@html highlightText(hoveredData.text || hoveredData.article_text, searchQuery)}</p>
  {:else}
    <p class="placeholder-text">{isPinned ? 'Click on a circle to pin it here.' : 'Hover over a circle to see details here.'}</p>
  {/if}
</div>

<style>
  .detail-card {
    padding: 0;
    border-radius: 0;
    background: transparent;
    height: 100%;
    overflow-y: auto;
    line-height: 1.5;
    display: flex;
    flex-direction: column;
    gap: 0.875rem;
  }

  h1 {
    margin: 0;
    padding: 0;
    font-size: 1.2rem;
    font-weight: 600;
    line-height: 1.4;
    color: var(--text-primary, #1a202c);
    letter-spacing: -0.01em;
  }

  span {
    padding: 4px 10px;
    display: inline-block;
    vertical-align: bottom;
    border-radius: 4px;
    color: white;
    font-size: 0.75rem;
    font-weight: 500;
    width: fit-content;
  }

  p {
    font-size: 0.875rem;
    font-weight: 400;
    margin: 0;
    line-height: 1.7;
    color: var(--text-secondary, #4a5568);
  }

  .placeholder-text {
    color: var(--text-muted, #64748b);
    font-style: normal;
    font-size: 0.85rem;
    text-align: center;
    padding: 2rem 1rem;
  }

  /* Highlighting for search terms */
  :global(.detail-card mark) {
    background-color: rgba(59, 130, 246, 0.2);
    color: inherit;
    padding: 1px 3px;
    border-radius: 2px;
  }

  .pin-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem 0.75rem;
    background: var(--accent-light, rgba(59, 130, 246, 0.1));
    border-radius: 6px;
    margin-bottom: 0.25rem;
  }

  .pin-indicator {
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--accent, #3b82f6);
  }

  .unpin-btn {
    background: transparent;
    border: none;
    font-size: 1rem;
    cursor: pointer;
    color: var(--text-muted, #64748b);
    padding: 0;
    width: 22px;
    height: 22px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    transition: all 0.15s ease;
  }

  .unpin-btn:hover {
    background: rgba(0, 0, 0, 0.08);
    color: var(--text-primary, #1a202c);
  }

  /* Topic badge with main label and subtitle */
  .topic-badge {
    display: flex;
    flex-direction: column;
    gap: 1px;
    padding: 5px 10px;
  }

  .topic-main {
    font-size: 0.75rem;
    font-weight: 600;
    padding: 0;
    display: block;
  }

  .topic-sub {
    font-size: 0.6rem;
    font-weight: 400;
    opacity: 0.85;
    padding: 0;
    display: block;
  }

  .meta-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .meta-links {
    display: flex;
    gap: 1rem;
  }

  .article-link {
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--accent, #3b82f6);
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0;
    transition: color 0.15s ease;
  }

  .article-link:hover {
    color: #2563eb;
    text-decoration: underline;
  }

  .article-link::after {
    content: "↗";
    font-size: 0.7rem;
  }

  .article-date {
    font-size: 0.7rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--text-muted, #64748b);
  }

  .summary {
    padding: 0.75rem;
    background: rgba(0, 0, 0, 0.02);
    border-radius: 6px;
    border-left: 3px solid var(--accent, #3b82f6);
  }

  @media (max-width: 768px) {
    h1 {
      font-size: 1.1rem;
    }

    p {
      font-size: 0.8rem;
      line-height: 1.6;
    }

    .placeholder-text {
      padding: 1rem;
    }
  }
</style>