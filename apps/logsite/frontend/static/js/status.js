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
        card.style.borderLeft = "2px solid var(--danger)";
        const wrap = document.createElement("div");
        wrap.style.cssText = "display:flex;align-items:center;gap:12px;";
        const dot = document.createElement("span");
        dot.className = "dot dot-red";
        const content = document.createElement("div");
        const title = document.createElement("div");
        title.style.cssText = "font-size:13.5px;font-weight:700;letter-spacing:0.04em;text-transform:uppercase;color:var(--danger);";
        title.textContent = "TELEMETRY UNAVAILABLE";
        const detail = document.createElement("div");
        detail.style.cssText = "font-size:12.5px;color:var(--text-muted);margin-top:3px;";
        detail.textContent = err.message || "Telemetry feed could not be resolved.";
        content.append(title, detail);
        wrap.append(dot, content);
        card.appendChild(wrap);
      }
    }
  }

  function renderOverall(status, uptime) {
    const card = byId("overallStatusCard"); if (!card) return;
    const state = status?.overall || "degraded";
    const labels = {
      operational: "All Systems Operational",
      degraded: "Degraded System Performance",
      down: "Service Disruption Detected"
    };
    const accentColors = {
      operational: "var(--success)",
      degraded: "var(--warning)",
      down: "var(--danger)"
    };

    const pct = overallPct(uptime);
    card.replaceChildren();
    card.style.borderLeft = `2px solid ${accentColors[state] || accentColors.degraded}`;

    const wrap = document.createElement("div");
    wrap.style.cssText = "display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;";

    const left = document.createElement("div");
    left.style.cssText = "display:flex;align-items:center;gap:10px;";

    const dot = document.createElement("span");
    dot.className = "dot " + (state === "operational" ? "dot-green" : state === "degraded" ? "dot-amber" : "dot-red");

    const textGroup = document.createElement("div");
    const title = document.createElement("div");
    title.style.cssText = "font-size:14px;font-weight:600;color:#ffffff;";
    title.textContent = labels[state] || labels.degraded;

    const desc = document.createElement("div");
    desc.style.cssText = "font-size:12.5px;color:var(--text-secondary);margin-top:2px;";
    desc.textContent = state === "operational"
      ? "Core telemetry, automated workers, and AI pipelines are operating within standard parameters."
      : "Active degradation or elevated failure rates observed in component telemetry.";

    textGroup.append(title, desc);
    left.append(dot, textGroup);

    const right = document.createElement("div");
    right.className = "mono";
    right.style.cssText = "font-size:12px;color:var(--text-muted);";
    right.textContent = pct === null ? "90-Day Uptime: No data" : `90-Day Uptime: ${pct.toFixed(2)}%`;

    wrap.append(left, right);
    card.appendChild(wrap);
  }

  function renderKPIs(active, health) {
    text("kpiActiveUsers", String(active?.count ?? 0));
    text("kpiErrorRate", typeof health?.error_rate === "number" ? (health.error_rate * 100).toFixed(1) + "%" : "N/A");
    text("kpiLatency", typeof health?.p95_ms === "number" ? health.p95_ms + " ms" : "N/A");
    const gemini = byId("kpiGemini");
    if (gemini) {
      if (typeof health?.llm_failure_rate !== "number") {
        gemini.textContent = "N/A";
      } else {
        gemini.textContent = health.llm_failure_rate > 0.05 ? "Degraded" : "Healthy";
      }
    }
  }

  function renderServices(status) {
    const root = byId("servicesList"); if (!root) return;
    root.replaceChildren();
    const rows = Array.isArray(status?.components) ? status.components : [];
    if (!rows.length) {
      const e = document.createElement("div");
      e.className = "ls-card ls-empty";
      e.innerHTML = `<div class="ls-empty-title">No service telemetry recorded yet.</div><div class="ls-empty-desc">Probes will report component state once telemetry events stream.</div>`;
      root.appendChild(e);
      return;
    }

    const panel = document.createElement("div");
    panel.className = "ls-card";
    panel.style.padding = "0";
    panel.style.overflow = "hidden";

    const table = document.createElement("table");
    table.className = "ls-table";
    table.innerHTML = `
      <thead>
        <tr>
          <th>Service</th>
          <th>Status</th>
          <th>Diagnostic Detail</th>
        </tr>
      </thead>
      <tbody></tbody>
    `;
    const tbody = table.querySelector("tbody");

    rows.forEach(c => {
      const tr = document.createElement("tr");
      const state = (c.state || "unknown").toLowerCase();

      const tdName = document.createElement("td");
      tdName.style.fontWeight = "600";
      tdName.style.color = "#ffffff";
      tdName.textContent = c.name || "Component";

      const tdState = document.createElement("td");
      const pillType = state === "operational" ? "pill-success" : state === "degraded" ? "pill-warn" : state === "down" ? "pill-error" : "pill-debug";
      tdState.innerHTML = `<span class="pill ${pillType}">${(c.state || "UNKNOWN").toUpperCase()}</span>`;

      const tdDetail = document.createElement("td");
      tdDetail.style.color = "var(--text-secondary)";
      tdDetail.style.fontSize = "12px";
      tdDetail.textContent = c.detail || "—";

      tr.append(tdName, tdState, tdDetail);
      tbody.appendChild(tr);
    });

    panel.appendChild(table);
    root.appendChild(panel);
  }

  function renderUptime(history) {
    const strip = byId("uptimeStrip"); if (!strip) return;
    const rows = Array.isArray(history) ? history : [];
    const pct = overallPct(rows);
    text("uptimePct", pct === null ? "No uptime data yet" : `Overall availability: ${pct.toFixed(2)}%`);
    strip.replaceChildren();

    const display = rows.length ? rows : Array.from({ length: 90 }, () => null);
    display.forEach(d => {
      const bar = document.createElement("div");
      bar.className = "uptime-bar grey";
      if (d && typeof d.uptime_pct === "number") {
        bar.className = "uptime-bar " + (d.uptime_pct >= 99.9 ? "green" : d.uptime_pct >= 95 ? "amber" : "red");
      }
      bar.title = d
        ? `${d.date || "Date"}: ${typeof d.uptime_pct === "number" ? d.uptime_pct.toFixed(2) + "% availability" : "No telemetry recorded"}`
        : "No telemetry recorded";
      strip.appendChild(bar);
    });
  }

  let timer;
  function schedule() {
    clearTimeout(timer);
    if (document.visibilityState !== "hidden") {
      timer = setTimeout(async () => { await loadStatus(); schedule(); }, 60000);
    }
  }

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") clearTimeout(timer);
    else { loadStatus(); schedule(); }
  });

  const start = async user => { if (!user) return; await loadStatus(); schedule(); };
  window.onLogsiteAuthStateChanged ? window.onLogsiteAuthStateChanged(start) : start(true);
})();
