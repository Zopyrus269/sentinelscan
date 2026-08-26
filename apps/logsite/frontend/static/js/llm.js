/** SentinelScan Log Site — Gemini usage using Workstream B's exact response shape. */
(function () {
  const COST_PER_MILLION_TOKENS_ESTIMATE = 0.15; // Standard Gemini Flash estimation basis ($0.15 / 1M)
  const el = id => document.getElementById(id);
  const set = (id, v) => { const e = el(id); if (e) e.textContent = v; };
  const fmt = n => Number(n || 0).toLocaleString();

  async function load() {
    try {
      const group = el("groupBySelect")?.value || "day";
      const d = await window.apiFetch("/api/llm-usage", { group_by: group });
      set("kpiTotalTokens", fmt(d.total_tokens));
      set("kpiTokenSplit", `${fmt(d.prompt_tokens)} prompt · ${fmt(d.response_tokens)} response`);
      set("kpiCalls", fmt(d.calls));
      const rate = d.calls ? ((Number(d.cache_hits || 0) / d.calls) * 100) : null;
      set("kpiCacheRate", rate === null ? "N/A" : rate.toFixed(1) + "%");
      set("kpiCacheSub", `${fmt(d.cache_hits)} cached calls`);
      set("kpiAvgTokens", d.calls ? Math.round(d.total_tokens / d.calls).toLocaleString() : "N/A");
      set("kpiCost", COST_PER_MILLION_TOKENS_ESTIMATE > 0 ? "$" + ((d.total_tokens / 1e6) * COST_PER_MILLION_TOKENS_ESTIMATE).toFixed(4) : "N/A");
      renderChart(Array.isArray(d.buckets) ? d.buckets : []);
      renderUnsupported();
      set("llmLastRefreshed", "Last refreshed " + new Date().toLocaleTimeString());
    } catch (e) {
      console.error("LLM usage load error", e);
    }
  }

  function renderChart(buckets) {
    const root = el("usageChart");
    if (!root) return;
    root.replaceChildren();

    if (!buckets.length) {
      const d = document.createElement("div");
      d.className = "ls-empty";
      d.innerHTML = `<div class="ls-empty-title">No Gemini model telemetry recorded yet.</div>`;
      root.appendChild(d);
      return;
    }

    const max = Math.max(...buckets.map(b => Number(b.tokens || 0)), 1);
    const container = document.createElement("div");
    container.style.cssText = "display: flex; flex-direction: column; gap: 10px; padding: 4px 0;";

    buckets.forEach(b => {
      const row = document.createElement("div");
      row.style.cssText = "display: grid; grid-template-columns: 120px 1fr 100px; gap: 12px; align-items: center;";

      const label = document.createElement("span");
      label.className = "mono";
      label.style.cssText = "font-size: 11.5px; color: var(--text-secondary); white-space: nowrap;";
      label.textContent = b.bucket || "—";

      const track = document.createElement("div");
      track.className = "progress-track";

      const fill = document.createElement("span");
      fill.className = "progress-fill";
      fill.style.width = ((Number(b.tokens || 0) / max) * 100) + "%";
      track.appendChild(fill);

      const val = document.createElement("span");
      val.className = "mono";
      val.style.cssText = "font-size: 12px; font-weight: 600; text-align: right; color: #ffffff;";
      val.textContent = fmt(b.tokens);

      row.append(label, track, val);
      container.appendChild(row);
    });

    root.appendChild(container);
  }

  function renderUnsupported() {
    const tbody = el("expensiveScansTbody");
    if (!tbody) return;
    tbody.replaceChildren();
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 6;
    td.className = "ls-empty";
    td.style.border = "none";
    td.innerHTML = `<div class="ls-empty-title">Per-scan breakdown not exposed by current query contract</div><div class="ls-empty-desc">Telemetry aggregation is currently available at the aggregate and bucket resolution levels.</div>`;
    tr.appendChild(td);
    tbody.appendChild(tr);
  }

  el("groupBySelect")?.addEventListener("change", load);
  window.onLogsiteAuthStateChanged ? window.onLogsiteAuthStateChanged(u => { if (u) load(); }) : load();
})();
