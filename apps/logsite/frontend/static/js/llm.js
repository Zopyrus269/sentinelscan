/**
 * SentinelScan Log Site — Screen 4: Gemini Token Usage Analytics
 */
(function () {
  const COST_PER_1M = 0.15;

  async function load() {
    const groupBy = document.getElementById("groupBySelect")?.value || "day";
    try {
      const data = await window.apiFetch("/api/llm-usage?group_by=" + encodeURIComponent(groupBy));
      renderKPIs(data);
      renderChart(data.buckets || [], groupBy);
      renderScans(data.expensive_scans || []);
      const el = document.getElementById("llmLastRefreshed");
      if (el) el.textContent = "Last refreshed " + new Date().toLocaleTimeString() + " UTC";
    } catch (err) {
      console.error("LLM usage load error:", err);
    }
  }

  function renderKPIs(d) {
    const total = d.total_tokens || 0;
    const prompt = d.prompt_tokens || 0;
    const resp = d.response_tokens || 0;
    const calls = d.calls || 0;
    const hits = d.cache_hits || 0;
    const scans = d.scans_count || 1;

    setText("kpiTotalTokens", fmt(total));
    setText("kpiTokenSplit", "Prompt " + fmt(prompt) + " · Response " + fmt(resp));
    setText("kpiCalls", fmt(calls));
    setText("kpiCacheRate", calls > 0 ? ((hits / calls) * 100).toFixed(1) + "%" : "0.0%");
    setText("kpiCacheSub", fmt(hits) + " hits / " + fmt(calls) + " calls");
    setText("kpiAvgTokens", fmt(Math.round(total / scans)));
    setText("kpiCost", "$" + ((total / 1000000) * COST_PER_1M).toFixed(4));
  }

  function renderChart(buckets, groupBy) {
    const el = document.getElementById("usageChart");
    if (!el) return;

    if (!buckets.length) {
      el.innerHTML = '<div style="width:100%;text-align:center;font-size:13px;color:var(--ss-text-muted);align-self:center;">No usage data for this period.</div>';
      return;
    }

    const max = Math.max(...buckets.map(b => b.tokens || 0), 1);
    el.innerHTML = "";

    buckets.forEach(b => {
      const tokens = b.tokens || 0;
      const pct = Math.max((tokens / max) * 100, 3);

      const col = document.createElement("div");
      col.style.cssText = "flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%;position:relative;";

      const bar = document.createElement("div");
      bar.className = "chart-bar";
      bar.style.width = "100%";
      bar.style.height = pct + "%";
      bar.title = (b.bucket || "") + ": " + fmt(tokens) + " tokens (" + (b.calls || 0) + " calls)";

      const label = document.createElement("span");
      label.style.cssText = "font-size:10px;color:var(--ss-text-muted);margin-top:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100%;text-align:center;";
      label.textContent = (b.bucket || "").substring(5);

      col.appendChild(bar);
      col.appendChild(label);
      el.appendChild(col);
    });
  }

  function renderScans(scans) {
    const tbody = document.getElementById("expensiveScansTbody");
    if (!tbody) return;

    if (!scans.length) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:32px;color:var(--ss-text-muted);font-size:13px;">No scan data recorded yet.</td></tr>';
      return;
    }

    tbody.innerHTML = "";
    scans.forEach(s => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="mono" style="font-size:12px;color:var(--ss-primary);font-weight:600;">${esc(s.scan_id ? s.scan_id.substring(0, 8) : "—")}</td>
        <td>${esc(s.target || "—")}</td>
        <td style="text-align:right;" class="mono">${fmt(s.calls || 0)}</td>
        <td style="text-align:right;color:var(--ss-text-muted);" class="mono">${fmt(s.prompt_tokens || 0)}</td>
        <td style="text-align:right;color:var(--ss-text-muted);" class="mono">${fmt(s.response_tokens || 0)}</td>
        <td style="text-align:right;font-weight:700;" class="mono">${fmt(s.total_tokens || 0)}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  function fmt(n) { return (n || 0).toLocaleString(); }
  function setText(id, v) { const e = document.getElementById(id); if (e) e.textContent = v; }
  function esc(s) { return s ? String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;") : ""; }

  document.getElementById("groupBySelect")?.addEventListener("change", load);

  if (window.onLogsiteAuthStateChanged) {
    window.onLogsiteAuthStateChanged(load);
  } else {
    load();
  }
})();
