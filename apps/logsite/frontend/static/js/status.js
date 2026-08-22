/**
 * SentinelScan Log Site — Screen 1: System Status
 */
(function () {
  const SERVICES = [
    { key: "web",      label: "Web Application", type: "http" },
    { key: "scan_api", label: "Scan API",         type: "api" },
    { key: "gemini",   label: "Gemini Agent",     type: "llm" },
    { key: "firestore",label: "Firestore",        type: "db" },
    { key: "workers",  label: "Workers",          type: "worker" },
  ];

  async function loadStatus() {
    try {
      const [statusData, uptimeData, activeData] = await Promise.all([
        window.apiFetch("/api/status"),
        window.apiFetch("/api/uptime"),
        window.apiFetch("/api/active-users"),
      ]);

      renderOverallStatus(statusData, uptimeData);
      renderKPIs(statusData, activeData);
      renderServices(statusData, uptimeData);
      renderUptimeStrip(uptimeData);
      updateRefreshed();
    } catch (err) {
      console.error("Status load error:", err);
      renderOverallLoading("Unable to load system status. " + err.message);
    }
  }

  function renderOverallStatus(status, uptime) {
    const el = document.getElementById("overallStatusCard");
    if (!el) return;

    const isOk = !status.has_incidents;
    const pct = uptime.overall_pct !== undefined ? uptime.overall_pct.toFixed(2) : "100.00";

    el.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px;">
        <div style="display:flex;align-items:center;gap:12px;">
          <span class="dot ${isOk ? 'dot-green' : 'dot-amber'}" style="width:12px;height:12px;"></span>
          <div>
            <div style="font-size:16px;font-weight:700;color:${isOk ? 'var(--green)' : 'var(--amber)'};">
              ${isOk ? 'All systems operational' : 'Some services degraded'}
            </div>
            <div style="font-size:13px;color:var(--ss-text-secondary);margin-top:2px;">
              ${isOk ? 'SentinelScan services are operating normally.' : 'One or more services are experiencing issues.'}
            </div>
          </div>
        </div>
        <div style="font-size:13px;font-weight:600;color:var(--ss-text-muted);">
          90-day uptime <span class="mono" style="color:var(--ss-text);font-weight:700;">${esc(pct)}%</span>
        </div>
      </div>
    `;
  }

  function renderOverallLoading(msg) {
    const el = document.getElementById("overallStatusCard");
    if (!el) return;
    el.innerHTML = `
      <div style="display:flex;align-items:center;gap:12px;">
        <span style="font-size:20px;">⚠️</span>
        <div>
          <div style="font-size:15px;font-weight:600;color:var(--ss-text);">Status unavailable</div>
          <div style="font-size:13px;color:var(--ss-text-muted);margin-top:2px;">${esc(msg)}</div>
        </div>
      </div>
    `;
  }

  function renderKPIs(status, active) {
    setText("kpiActiveUsers", String(active.count || 0));
    setText("kpiErrorRate", ((status.error_rate || 0) * 100).toFixed(1) + "%");
    setText("kpiLatency", (status.p95_ms || 0) + " ms");

    const geminiEl = document.getElementById("kpiGemini");
    if (geminiEl) {
      const gs = status.gemini_status || "healthy";
      geminiEl.textContent = gs.charAt(0).toUpperCase() + gs.slice(1);
      geminiEl.style.color = gs === "healthy" ? "var(--green)" : "var(--amber)";
    }
  }

  function renderServices(status, uptime) {
    const container = document.getElementById("servicesList");
    if (!container) return;

    const components = status.components || uptime.components || [];
    if (components.length === 0 && !status.web_status) {
      container.innerHTML = `
        <div class="ls-card ls-empty">
          <div class="ls-empty-icon">📡</div>
          <div class="ls-empty-title">No component telemetry recorded yet.</div>
          <div class="ls-empty-desc">Service health data will appear after SentinelScan processes requests.</div>
        </div>
      `;
      return;
    }

    // Build from status object fields if components array is empty
    const rows = components.length > 0 ? components : SERVICES.map(s => ({
      name: s.label,
      status: "operational",
      detail: "",
    }));

    let html = '<div style="display:flex;flex-direction:column;gap:8px;">';
    rows.forEach(c => {
      const isOk = (c.status || "operational") === "operational";
      const dotClass = isOk ? "dot-green" : (c.status === "degraded" ? "dot-amber" : "dot-red");
      const statusLabel = isOk ? "Operational" : (c.status === "degraded" ? "Degraded" : "Down");

      html += `
        <div class="ls-card" style="padding:14px 20px;display:flex;align-items:center;justify-content:space-between;gap:12px;">
          <div style="display:flex;align-items:center;gap:10px;">
            <span class="dot ${dotClass}"></span>
            <div>
              <div style="font-size:14px;font-weight:600;color:var(--ss-text);">${esc(c.name || c.label)}</div>
              ${c.detail ? `<div style="font-size:12px;color:var(--ss-text-muted);margin-top:1px;" class="mono">${esc(c.detail)}</div>` : ''}
            </div>
          </div>
          <span style="font-size:12px;font-weight:500;color:${isOk ? 'var(--green)' : 'var(--amber)'};">${statusLabel}</span>
        </div>
      `;
    });
    html += '</div>';
    container.innerHTML = html;
  }

  function renderUptimeStrip(uptime) {
    const strip = document.getElementById("uptimeStrip");
    const pctEl = document.getElementById("uptimePct");
    if (!strip) return;

    const days = uptime.days || [];
    if (pctEl) pctEl.textContent = "Overall uptime " + (uptime.overall_pct !== undefined ? uptime.overall_pct.toFixed(2) : "100.00") + "%";

    if (days.length === 0) {
      // Generate 90 grey placeholders
      strip.innerHTML = Array(90).fill('<div class="uptime-bar grey"></div>').join('');
      return;
    }

    strip.innerHTML = days.map(d => {
      let cls = "grey";
      if (d.status === "up" || d.status === "operational") cls = "green";
      else if (d.status === "degraded") cls = "amber";
      else if (d.status === "down") cls = "red";
      return `<div class="uptime-bar ${cls}" title="${esc(d.date || '')}"></div>`;
    }).join('');
  }

  function updateRefreshed() {
    const el = document.getElementById("lastRefreshed");
    if (el) el.textContent = "Last refreshed " + new Date().toLocaleTimeString() + " UTC";
  }

  function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  function esc(s) {
    if (!s) return "";
    return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  }

  if (window.onLogsiteAuthStateChanged) {
    window.onLogsiteAuthStateChanged(() => loadStatus());
  } else {
    loadStatus();
  }
})();
