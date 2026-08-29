/** SentinelScan Log Site — Health screen using only Workstream B fields. */
(function () {
  const el = id => document.getElementById(id);
  const set = (id, v) => { const e = el(id); if (e) e.textContent = v; };
  const fmt = n => Number(n || 0).toLocaleString();

  async function load() {
    try {
      const d = await window.apiFetch("/api/health");
      renderKPIs(d);
      renderWorkers(Array.isArray(d.workers) ? d.workers : []);
      renderUnsupported();
      set("healthLastRefreshed", "Last refreshed " + new Date().toLocaleTimeString());
    } catch (e) {
      console.error("Health load error", e);
    }
  }

  function renderKPIs(d) {
    set("kpiErrorRate", typeof d.error_rate === "number" ? (d.error_rate * 100).toFixed(1) + "%" : "N/A");
    set("kpiErrorSub", "Observed across telemetry in the last hour");
    set("kpiLatency", (typeof d.p50_ms === "number" && typeof d.p95_ms === "number") ? `${d.p50_ms}ms / ${d.p95_ms}ms` : "N/A");
    set("kpiRequests", typeof d.requests_1h === "number" ? fmt(d.requests_1h) + " requests in 1h" : "N/A");
    set("kpiRetry", typeof d.llm_failure_rate === "number" ? (d.llm_failure_rate > 0.05 ? "Degraded" : "Nominal") : "N/A");
    set("kpiFailure", typeof d.llm_failure_rate === "number" ? "Failures: " + (d.llm_failure_rate * 100).toFixed(1) + "%" : "Failures: N/A");
  }

  function renderWorkers(list) {
    const tbody = el("workersTbody");
    if (!tbody) return;
    tbody.replaceChildren();

    if (!list.length) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 5;
      td.className = "ls-empty";
      td.style.border = "none";
      td.innerHTML = `<div class="ls-empty-title">No worker health telemetry recorded yet.</div><div class="ls-empty-desc">Security workers will report completion and failure statistics during scans.</div>`;
      tr.appendChild(td);
      tbody.appendChild(tr);
      set("kpiWorkerSuccess", "N/A");
      set("kpiWorkerSub", "No worker tasks observed in current window");
      return;
    }

    let ok = 0, failed = 0;
    [...list].sort((a, b) => String(a.name || "").localeCompare(String(b.name || ""))).forEach(w => {
      ok += Number(w.ok || 0);
      failed += Number(w.failed || 0);
      const totalWorker = (Number(w.ok || 0)) + (Number(w.failed || 0));
      const rate = typeof w.success_rate === "number" ? w.success_rate : (totalWorker ? (Number(w.ok || 0)) / totalWorker : null);

      const tr = document.createElement("tr");

      // Name
      const tdName = document.createElement("td");
      tdName.style.fontWeight = "600";
      tdName.style.color = "#ffffff";
      tdName.textContent = w.name || "unknown_worker";

      // Completed
      const tdOk = document.createElement("td");
      tdOk.className = "mono";
      tdOk.style.textAlign = "right";
      tdOk.style.color = "var(--text-secondary)";
      tdOk.textContent = fmt(w.ok);

      // Failed
      const tdFailed = document.createElement("td");
      tdFailed.className = "mono";
      tdFailed.style.textAlign = "right";
      tdFailed.style.color = (Number(w.failed || 0) > 0) ? "var(--danger)" : "var(--text-muted)";
      tdFailed.textContent = fmt(w.failed);

      // Success Rate Bar + Percentage
      const tdRate = document.createElement("td");
      tdRate.style.textAlign = "right";
      if (rate === null) {
        tdRate.innerHTML = `<span class="mono" style="color:var(--text-muted);">—</span>`;
      } else {
        const pct = (rate * 100).toFixed(1);
        tdRate.innerHTML = `
          <div style="display:flex;align-items:center;justify-content:flex-end;gap:8px;">
            <div class="progress-track" style="width:70px;height:6px;">
              <span class="progress-fill" style="width:${pct}%;background:${rate >= 0.9 ? 'var(--success)' : rate >= 0.7 ? 'var(--warning)' : 'var(--danger)'};"></span>
            </div>
            <span class="mono" style="font-weight:600;width:45px;text-align:right;">${pct}%</span>
          </div>
        `;
      }

      // Operational State Pill
      const tdState = document.createElement("td");
      tdState.style.textAlign = "right";
      const stateLabel = rate === null ? "NO DATA" : rate >= 0.9 ? "OPERATIONAL" : rate >= 0.7 ? "DEGRADED" : "ERROR";
      const pillClass = rate === null ? "pill-debug" : rate >= 0.9 ? "pill-success" : rate >= 0.7 ? "pill-warn" : "pill-error";
      tdState.innerHTML = `<span class="pill ${pillClass}">${stateLabel}</span>`;

      tr.append(tdName, tdOk, tdFailed, tdRate, tdState);
      tbody.appendChild(tr);
    });

    const total = ok + failed;
    set("kpiWorkerSuccess", total ? ((ok / total) * 100).toFixed(1) + "%" : "N/A");
    set("kpiWorkerSub", list.length + " workers observed");
  }

  function renderUnsupported() {
    const tbody = el("fingerprintsTbody");
    if (!tbody) return;
    tbody.replaceChildren();
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 4;
    td.className = "ls-empty";
    td.style.border = "none";
    td.innerHTML = `<div class="ls-empty-title">Frequent-error fingerprints not exposed</div><div class="ls-empty-desc">Error fingerprint grouping is scheduled for subsequent observability query extensions.</div>`;
    tr.appendChild(td);
    tbody.appendChild(tr);
  }

  window.onLogsiteAuthStateChanged ? window.onLogsiteAuthStateChanged(u => { if (u) load(); }) : load();
})();
