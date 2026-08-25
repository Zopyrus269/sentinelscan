/** SentinelScan Log Site — System Status (Workstream B contract aligned). */
(function () {
  const byId = id => document.getElementById(id);
  const text = (id, value) => { const e = byId(id); if (e) e.textContent = value; };

  function validUptime(history) {
    return (Array.isArray(history) ? history : []).filter(d => typeof d?.uptime_pct === "number");
  }
  function overallPct(history) {
    const rows = validUptime(history);
    return rows.length ? rows.reduce((n, d) => n + d.uptime_pct, 0) / rows.length : null;
  }

  async function loadStatus() {
    try {
      const [status, uptime, active, health] = await Promise.all([
        window.apiFetch("/api/status"), window.apiFetch("/api/uptime"),
        window.apiFetch("/api/active-users"), window.apiFetch("/api/health")
      ]);
      renderOverall(status, uptime);
      renderKPIs(active, health);
      renderServices(status);
      renderUptime(uptime);
      text("lastRefreshed", "Last refreshed " + new Date().toLocaleTimeString());
    } catch (err) {
      const card = byId("overallStatusCard");
      if (card) {
        card.replaceChildren();
        const title = document.createElement("strong"); title.textContent = "Status unavailable";
        const detail = document.createElement("div"); detail.textContent = err.message || "Telemetry could not be loaded.";
        card.append(title, detail);
      }
    }
  }

  function renderOverall(status, uptime) {
    const card = byId("overallStatusCard"); if (!card) return;
    const state = status?.overall || "degraded";
    const labels = { operational: "All systems operational", degraded: "Some services degraded", down: "Service disruption detected" };
    const pct = overallPct(uptime);
    card.replaceChildren();
    const wrap = document.createElement("div"); wrap.style.cssText = "display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap";
    const left = document.createElement("div");
    const title = document.createElement("div"); title.style.cssText = "font-size:16px;font-weight:700"; title.textContent = labels[state] || labels.degraded;
    const desc = document.createElement("div"); desc.style.cssText = "font-size:13px;color:var(--ss-text-secondary);margin-top:3px"; desc.textContent = state === "operational" ? "No degradation is currently indicated by available telemetry." : "Review component health below.";
    left.append(title, desc);
    const right = document.createElement("div"); right.style.cssText = "font-size:13px;color:var(--ss-text-muted)"; right.textContent = pct === null ? "90-day uptime: No data yet" : `90-day uptime: ${pct.toFixed(2)}%`;
    wrap.append(left, right); card.appendChild(wrap);
  }

  function renderKPIs(active, health) {
    text("kpiActiveUsers", String(active?.count ?? 0));
    text("kpiErrorRate", typeof health?.error_rate === "number" ? (health.error_rate * 100).toFixed(1) + "%" : "N/A");
    text("kpiLatency", typeof health?.p95_ms === "number" ? health.p95_ms + " ms" : "N/A");
    const gemini = byId("kpiGemini");
    if (gemini) {
      if (typeof health?.llm_failure_rate !== "number") gemini.textContent = "N/A";
      else gemini.textContent = health.llm_failure_rate > 0.05 ? "Degraded" : "Healthy";
    }
  }

  function renderServices(status) {
    const root = byId("servicesList"); if (!root) return;
    root.replaceChildren();
    const rows = Array.isArray(status?.components) ? status.components : [];
    if (!rows.length) { const e=document.createElement("div"); e.className="ls-card ls-empty"; e.textContent="No component telemetry recorded yet."; root.appendChild(e); return; }
    const list=document.createElement("div"); list.style.cssText="display:flex;flex-direction:column;gap:8px";
    rows.forEach(c => {
      const row=document.createElement("div"); row.className="ls-card"; row.style.cssText="padding:14px 20px;display:flex;justify-content:space-between;gap:12px";
      const left=document.createElement("div"); const name=document.createElement("div"); name.style.fontWeight="600"; name.textContent=c.name || "Component";
      const detail=document.createElement("div"); detail.style.cssText="font-size:12px;color:var(--ss-text-muted);margin-top:2px"; detail.textContent=c.detail || "No detail available"; left.append(name,detail);
      const state=document.createElement("span"); state.style.cssText="font-size:12px;font-weight:600;text-transform:capitalize"; state.textContent=c.state || "unknown";
      row.append(left,state); list.appendChild(row);
    }); root.appendChild(list);
  }

  function renderUptime(history) {
    const strip=byId("uptimeStrip"); if (!strip) return;
    const rows=Array.isArray(history) ? history : []; const pct=overallPct(rows);
    text("uptimePct", pct === null ? "No uptime data yet" : `Overall uptime ${pct.toFixed(2)}%`);
    strip.replaceChildren();
    const display = rows.length ? rows : Array.from({length:90}, () => null);
    display.forEach(d => {
      const bar=document.createElement("div"); bar.className="uptime-bar grey";
      if (d && typeof d.uptime_pct === "number") bar.className="uptime-bar " + (d.uptime_pct >= 99.9 ? "green" : d.uptime_pct >= 95 ? "amber" : "red");
      bar.title = d ? `${d.date || ""}${typeof d.uptime_pct === "number" ? ` — ${d.uptime_pct.toFixed(2)}%` : " — no data"}` : "No data";
      strip.appendChild(bar);
    });
  }

  let timer;
  function schedule(){ clearTimeout(timer); if(document.visibilityState!=="hidden") timer=setTimeout(async()=>{await loadStatus();schedule();},60000); }
  document.addEventListener("visibilitychange",()=>{ if(document.visibilityState==="hidden") clearTimeout(timer); else {loadStatus();schedule();} });
  const start=async user=>{ if(!user) return; await loadStatus(); schedule(); };
  window.onLogsiteAuthStateChanged ? window.onLogsiteAuthStateChanged(start) : start(true);
})();
