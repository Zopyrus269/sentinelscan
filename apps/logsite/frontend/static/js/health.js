/**
 * SentinelScan Log Site — Screen 5: System Health & Worker Diagnostics
 */
(function () {
  const ALL_WORKERS = [
    "dns_lookup", "ssl_check", "headers_worker", "robots_worker",
    "sitemap_worker", "whois_worker", "portscan_worker", "cookie_worker",
    "ddos_worker", "ssrf_validator", "security_score",
  ];

  async function load() {
    try {
      const data = await window.apiFetch("/api/health");
      renderKPIs(data);
      renderWorkers(data.workers || []);
      renderFingerprints(data.frequent_errors || []);
      const el = document.getElementById("healthLastRefreshed");
      if (el) el.textContent = "Last refreshed " + new Date().toLocaleTimeString() + " UTC";
    } catch (err) {
      console.error("Health load error:", err);
    }
  }

  function renderKPIs(d) {
    const errPct = ((d.error_rate || 0) * 100).toFixed(1);
    setText("kpiErrorRate", errPct + "%");
    const errEl = document.getElementById("kpiErrorRate");
    if (errEl) errEl.style.color = parseFloat(errPct) > 5 ? "var(--amber)" : "var(--green)";
    setText("kpiErrorSub", (d.total_errors_1h || 0) + " errors in 1h");

    setText("kpiLatency", (d.p50_ms || 0) + "ms / " + (d.p95_ms || 0) + "ms");
    setText("kpiRequests", fmt(d.requests_1h || 0) + " requests in 1h");

    setText("kpiRetry", ((d.llm_retry_rate || 0) * 100).toFixed(1) + "%");
    setText("kpiFailure", "Failures: " + ((d.llm_failure_rate || 0) * 100).toFixed(1) + "%");
  }

  function renderWorkers(list) {
    const tbody = document.getElementById("workersTbody");
    const kpiEl = document.getElementById("kpiWorkerSuccess");
    const kpiSub = document.getElementById("kpiWorkerSub");
    if (!tbody) return;

    const map = new Map();
    if (Array.isArray(list)) list.forEach(w => map.set(w.name, w));

    let totalOk = 0, totalFail = 0;
    tbody.innerHTML = "";

    ALL_WORKERS.forEach(name => {
      const w = map.get(name) || { name, ok: 0, failed: 0 };
      const ok = w.ok || 0;
      const fail = w.failed || 0;
      totalOk += ok;
      totalFail += fail;

      const rate = ok + fail > 0 ? ok / (ok + fail) : 1.0;
      const pct = (rate * 100).toFixed(1);

      let statusLabel, statusColor, barColor;
      if (rate >= 0.9) { statusLabel = "Operational"; statusColor = "var(--green)"; barColor = "green"; }
      else if (rate >= 0.7) { statusLabel = "Degraded"; statusColor = "var(--amber)"; barColor = "amber"; }
      else { statusLabel = "Error"; statusColor = "var(--red)"; barColor = "red"; }

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="font-weight:600;">${esc(name)}</td>
        <td style="text-align:right;" class="mono">${fmt(ok)}</td>
        <td style="text-align:right;color:${fail > 0 ? 'var(--red)' : 'var(--ss-text-muted)'};" class="mono">${fmt(fail)}</td>
        <td style="text-align:right;">
          <span style="display:inline-flex;align-items:center;gap:8px;">
            <span class="mono">${pct}%</span>
            <span class="progress-track"><span class="progress-fill ${barColor}" style="width:${pct}%"></span></span>
          </span>
        </td>
        <td style="text-align:right;">
          <span style="display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:600;color:${statusColor};">
            <span class="dot dot-${barColor === 'green' ? 'green' : barColor === 'amber' ? 'amber' : 'red'}"></span>
            ${statusLabel}
          </span>
        </td>
      `;
      tbody.appendChild(tr);
    });

    if (kpiEl) {
      const overall = totalOk + totalFail > 0 ? ((totalOk / (totalOk + totalFail)) * 100).toFixed(1) : "100.0";
      kpiEl.textContent = overall + "%";
      kpiEl.style.color = parseFloat(overall) >= 90 ? "var(--green)" : "var(--amber)";
    }
    if (kpiSub) kpiSub.textContent = ALL_WORKERS.length + " workers registered";
  }

  function renderFingerprints(fps) {
    const tbody = document.getElementById("fingerprintsTbody");
    if (!tbody) return;

    if (!fps.length) {
      tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:32px;color:var(--ss-text-muted);font-size:13px;">No error fingerprints recorded.</td></tr>';
      return;
    }

    tbody.innerHTML = "";
    fps.forEach(f => {
      const tr = document.createElement("tr");
      const link = f.session_id
        ? `<a href="/sessions.html?session_id=${encodeURIComponent(f.session_id)}${f.trace_id ? '&trace_id=' + encodeURIComponent(f.trace_id) : ''}" style="color:var(--ss-primary);font-weight:500;font-size:12px;">View →</a>`
        : "—";
      tr.innerHTML = `
        <td class="mono" style="font-size:11px;color:var(--amber);font-weight:600;">${esc(f.fingerprint || "—")}</td>
        <td style="font-size:13px;">${esc((f.type || "Error") + ": " + (f.message || ""))}</td>
        <td style="text-align:right;font-weight:700;color:var(--red);" class="mono">${fmt(f.count || 1)}</td>
        <td style="text-align:right;">${link}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  function fmt(n) { return (n || 0).toLocaleString(); }
  function setText(id, v) { const e = document.getElementById(id); if (e) e.textContent = v; }
  function esc(s) { return s ? String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;") : ""; }

  if (window.onLogsiteAuthStateChanged) {
    window.onLogsiteAuthStateChanged(load);
  } else {
    load();
  }
})();
