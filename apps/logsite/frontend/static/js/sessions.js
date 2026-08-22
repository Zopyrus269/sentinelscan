/**
 * SentinelScan Log Site — Screen 3: Session Explorer & AI Trace Debugger
 */
(function () {
  let sessionsData = [];
  let filteredSessions = [];
  let currentSession = null;
  let currentTimelineEvents = [];
  let expandedTraces = new Set();
  let expandedDetails = new Set();

  async function init() {
    setupSearch();
    setupCopy();

    const params = new URLSearchParams(window.location.search);
    const sid = params.get("session_id");
    const tid = params.get("trace_id");
    if (tid) expandedTraces.add(tid);

    await loadSessions(sid, tid);
  }

  async function loadSessions(targetSid, targetTid) {
    try {
      const list = await window.apiFetch("/api/sessions?limit=50");
      sessionsData = Array.isArray(list) ? list : [];
      sessionsData.sort((a, b) => {
        const ea = (a.error_count || 0) > 0 ? 1 : 0;
        const eb = (b.error_count || 0) > 0 ? 1 : 0;
        if (ea !== eb) return eb - ea;
        return new Date(b.last_seen || b.started_at || 0) - new Date(a.last_seen || a.started_at || 0);
      });
      filteredSessions = [...sessionsData];
      renderList();

      if (targetSid) selectSession(targetSid, targetTid);
      else if (sessionsData.length > 0) selectSession(sessionsData[0].session_id);
      else renderEmptyTimeline();
    } catch (err) {
      console.error("Sessions load error:", err);
      const el = document.getElementById("sessionsList");
      if (el) el.innerHTML = `<div style="padding:20px;text-align:center;font-size:13px;color:var(--red);">Failed to load sessions: ${esc(err.message)}</div>`;
    }
  }

  function setupSearch() {
    const input = document.getElementById("sessionSearchInput");
    if (!input) return;
    input.addEventListener("input", () => {
      const q = input.value.toLowerCase().trim();
      filteredSessions = !q ? [...sessionsData] : sessionsData.filter(s =>
        (s.email && s.email.toLowerCase().includes(q)) ||
        (s.session_id && s.session_id.toLowerCase().includes(q))
      );
      renderList();
    });
  }

  function renderList() {
    const el = document.getElementById("sessionsList");
    const cnt = document.getElementById("sessionsCount");
    if (!el) return;
    if (cnt) cnt.textContent = filteredSessions.length + " sessions";

    if (filteredSessions.length === 0) {
      el.innerHTML = `<div class="ls-empty"><div class="ls-empty-icon">📭</div><div class="ls-empty-title">No sessions found</div></div>`;
      return;
    }

    el.innerHTML = "";
    filteredSessions.forEach(s => {
      const item = document.createElement("div");
      const isSel = currentSession && currentSession.session_id === s.session_id;
      item.className = "session-item" + (isSel ? " selected" : "");

      let html = `<div style="font-size:13px;font-weight:600;color:var(--ss-text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${esc(s.email || "anonymous")}</div>`;
      html += `<div style="font-size:12px;color:var(--ss-text-muted);margin-top:3px;">Started ${fmtTime(s.started_at)}`;
      html += ` · ${s.event_count || 0} events`;
      if (s.error_count && s.error_count > 0) {
        html += ` · <span style="color:var(--red);font-weight:600;">${s.error_count} errors</span>`;
      }
      html += `</div>`;
      item.innerHTML = html;
      item.addEventListener("click", () => selectSession(s.session_id));
      el.appendChild(item);
    });
  }

  async function selectSession(sid, tid) {
    const obj = sessionsData.find(s => s.session_id === sid) || { session_id: sid };
    currentSession = obj;
    renderList();

    setText("activeSessionTitle", "Session " + sid.substring(0, 12));
    setText("activeSessionSubtitle", (obj.email || "anonymous") + " · Started " + fmtTime(obj.started_at) + " · " + calcDuration(obj.started_at, obj.last_seen));

    const copyBtn = document.getElementById("btnCopyTimeline");
    if (copyBtn) copyBtn.classList.remove("hidden");

    const container = document.getElementById("timelineContainer");
    if (container) container.innerHTML = `<div style="padding:32px;text-align:center;font-size:13px;color:var(--ss-text-muted);"><span class="ls-spinner" style="margin-right:6px;vertical-align:middle;"></span> Loading timeline…</div>`;

    try {
      const res = await window.apiFetch("/api/sessions/" + encodeURIComponent(sid));
      currentTimelineEvents = res.events || [];
      renderTimeline(currentTimelineEvents, tid);
    } catch (err) {
      if (container) container.innerHTML = `<div class="ls-empty"><div class="ls-empty-icon">⚠️</div><div class="ls-empty-title">Failed to load timeline</div><div class="ls-empty-desc">${esc(err.message)}</div></div>`;
    }
  }

  function renderTimeline(events, tid) {
    const container = document.getElementById("timelineContainer");
    if (!container) return;

    if (!events || events.length === 0) {
      container.innerHTML = `<div class="ls-empty"><div class="ls-empty-icon">📭</div><div class="ls-empty-title">No timeline events</div><div class="ls-empty-desc">No events recorded for this session.</div></div>`;
      return;
    }

    const sorted = [...events].sort((a, b) => new Date(a.ts || 0) - new Date(b.ts || 0));

    // Group by trace_id
    const traceMap = new Map();
    const traceOrder = [];
    const ungrouped = [];
    sorted.forEach(evt => {
      if (evt.trace_id) {
        if (!traceMap.has(evt.trace_id)) {
          const g = { trace_id: evt.trace_id, events: [] };
          traceMap.set(evt.trace_id, g);
          traceOrder.push(g);
        }
        traceMap.get(evt.trace_id).events.push(evt);
      } else {
        ungrouped.push(evt);
      }
    });

    container.innerHTML = "";
    if (tid) expandedTraces.add(tid);

    traceOrder.forEach(g => container.appendChild(renderTraceGroup(g)));
    ungrouped.forEach((evt, i) => container.appendChild(renderEventRow(evt, i > 0 ? sorted[i-1] : null)));

    if (tid) {
      setTimeout(() => {
        const el = document.getElementById("trace-" + tid);
        if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 150);
    }
  }

  function renderTraceGroup(group) {
    const events = group.events;
    const first = events.find(e => e.category === "ui" || e.category === "http") || events[0];
    const hasErr = events.some(e => e.level === "error" || e.level === "fatal");
    const isOpen = expandedTraces.has(group.trace_id);

    const wrapper = document.createElement("div");
    wrapper.id = "trace-" + group.trace_id;
    wrapper.className = "trace-group";
    wrapper.style.marginBottom = "10px";

    // Header
    const header = document.createElement("div");
    header.className = "trace-group-header";
    if (hasErr) header.style.borderLeft = "3px solid var(--red)";

    const arrow = document.createElement("span");
    arrow.style.cssText = "font-size:12px;color:var(--ss-text-muted);transition:transform 150ms;flex-shrink:0;";
    arrow.textContent = isOpen ? "▾" : "▸";

    const label = document.createElement("div");
    label.style.cssText = "flex:1;min-width:0;";
    label.innerHTML = `
      <div style="font-size:14px;font-weight:600;color:var(--ss-text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${esc(getTraceLabel(first))}</div>
      <div style="font-size:12px;color:var(--ss-text-muted);margin-top:2px;">${events.length} events · ${calcTraceDuration(events)}</div>
    `;

    const ts = document.createElement("span");
    ts.className = "mono";
    ts.style.cssText = "font-size:12px;color:var(--ss-text-muted);flex-shrink:0;";
    ts.textContent = fmtTime(first.ts);

    header.appendChild(arrow);
    header.appendChild(label);
    header.appendChild(ts);
    wrapper.appendChild(header);

    // Body
    const body = document.createElement("div");
    body.className = "trace-group-body";
    if (!isOpen) body.style.display = "none";

    events.forEach((evt, i) => {
      body.appendChild(renderEventRow(evt, i > 0 ? events[i-1] : null));
    });
    wrapper.appendChild(body);

    header.addEventListener("click", () => {
      const open = body.style.display !== "none";
      body.style.display = open ? "none" : "block";
      arrow.textContent = open ? "▸" : "▾";
      if (open) expandedTraces.delete(group.trace_id);
      else expandedTraces.add(group.trace_id);
    });

    return wrapper;
  }

  function renderEventRow(evt, prevEvt) {
    const row = document.createElement("div");
    const isErr = evt.level === "error" || evt.level === "fatal";
    row.className = "timeline-event" + (isErr ? " is-error" : "");

    // Top line: timestamp + category badge + message
    const top = document.createElement("div");
    top.style.cssText = "display:flex;align-items:center;gap:8px;flex-wrap:wrap;";

    const ts = document.createElement("span");
    ts.className = "mono";
    ts.style.cssText = "font-size:11px;color:var(--ss-text-muted);flex-shrink:0;";
    ts.textContent = fmtTime(evt.ts);

    const pill = document.createElement("span");
    pill.className = "pill pill-" + (evt.level || "info");
    pill.textContent = (evt.level || "info").toUpperCase();

    const cat = document.createElement("span");
    cat.className = "cat-badge";
    cat.textContent = evt.category || "—";

    const msg = document.createElement("span");
    msg.style.cssText = "font-size:13px;color:var(--ss-text);flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;";
    msg.textContent = evt.message || "";

    top.appendChild(ts);
    top.appendChild(pill);
    top.appendChild(cat);
    top.appendChild(msg);

    // Delta time
    if (prevEvt && evt.ts && prevEvt.ts) {
      const diff = new Date(evt.ts) - new Date(prevEvt.ts);
      if (diff > 0) {
        const delta = document.createElement("span");
        delta.className = "mono";
        delta.style.cssText = "font-size:11px;color:var(--ss-text-muted);font-weight:600;flex-shrink:0;";
        delta.textContent = "+" + diff + "ms";
        top.appendChild(delta);
      }
    }
    row.appendChild(top);

    // AI Decision Card
    if (evt.category === "agent" && evt.data && typeof evt.data === "object") {
      const card = document.createElement("div");
      card.className = "ai-card";

      let html = `<div class="ai-card-header">🤖 AI Decision</div>`;
      if (evt.data.tool_name || evt.data.action) {
        html += `<div class="ai-card-field">Selected Worker</div><div class="ai-card-value" style="font-weight:600;">${esc(evt.data.tool_name || evt.data.action)}</div>`;
      }
      if (evt.data.reasoning) {
        html += `<div class="ai-card-field">Reasoning</div><div class="ai-card-reasoning">${esc(evt.data.reasoning)}</div>`;
      }
      card.innerHTML = html;
      row.appendChild(card);
    }

    // Expandable details
    const details = document.createElement("div");
    details.style.cssText = "margin-top:8px;padding:10px 12px;background:var(--ss-surface-low);border-radius:6px;font-size:12px;color:var(--ss-text-secondary);display:none;";
    const isOpen = expandedDetails.has(evt.event_id);
    if (isOpen) details.style.display = "block";

    let dHtml = "";
    const fields = [
      ["Event ID", evt.event_id], ["Trace ID", evt.trace_id], ["Session ID", evt.session_id],
      ["Scan ID", evt.scan_id], ["Duration", evt.duration_ms ? evt.duration_ms + " ms" : null],
    ];
    fields.forEach(([k, v]) => {
      if (v) dHtml += `<div style="display:flex;gap:8px;margin-bottom:3px;"><span style="color:var(--ss-text-muted);width:80px;flex-shrink:0;">${k}:</span><span class="mono" style="color:var(--ss-text);">${esc(String(v))}</span></div>`;
    });
    if (evt.data && Object.keys(evt.data).length > 0) {
      dHtml += `<div style="margin-top:8px;font-weight:600;color:var(--ss-text-muted);margin-bottom:4px;">Data</div>`;
      dHtml += `<pre class="mono" style="font-size:11px;color:var(--ss-text-secondary);background:var(--ss-surface);padding:8px;border-radius:4px;overflow-x:auto;border:1px solid var(--ss-border);margin:0;white-space:pre-wrap;">${esc(JSON.stringify(evt.data, null, 2))}</pre>`;
    }
    details.innerHTML = dHtml;
    row.appendChild(details);

    row.addEventListener("click", e => {
      if (e.target.tagName === "A") return;
      const open = details.style.display !== "none";
      details.style.display = open ? "none" : "block";
      if (open) expandedDetails.delete(evt.event_id);
      else expandedDetails.add(evt.event_id);
    });

    return row;
  }

  function getTraceLabel(evt) {
    if (evt.category === "ui") return "User Action: " + (evt.data?.action || evt.message || "click");
    if (evt.category === "http") return (evt.data?.method || "POST") + " " + (evt.data?.path || evt.data?.route || "/api");
    return evt.message || "Trace";
  }

  function setupCopy() {
    document.getElementById("btnCopyTimeline")?.addEventListener("click", () => {
      if (!currentTimelineEvents.length) return;
      let txt = "SENTINELSCAN SESSION TIMELINE\n";
      txt += "Session: " + (currentSession?.session_id || "—") + "\n";
      txt += "User: " + (currentSession?.email || "anonymous") + "\n\n";
      currentTimelineEvents.forEach(e => {
        txt += "[" + fmtTime(e.ts) + "] [" + (e.level||"info").toUpperCase() + "] [" + (e.category||"") + "] " + (e.message||"") + "\n";
        if (e.data?.reasoning) txt += "  Reasoning: " + e.data.reasoning + "\n";
      });
      navigator.clipboard.writeText(txt).then(() => {
        const btn = document.getElementById("btnCopyTimeline");
        if (btn) { const o = btn.textContent; btn.textContent = "✓ Copied"; setTimeout(() => btn.textContent = o, 2000); }
      });
    });
  }

  function renderEmptyTimeline() {
    const c = document.getElementById("timelineContainer");
    if (c) c.innerHTML = `<div class="ls-empty"><div class="ls-empty-icon">📭</div><div class="ls-empty-title">No sessions recorded</div><div class="ls-empty-desc">Sessions will appear after users visit SentinelScan.</div></div>`;
  }

  function fmtTime(ts) {
    if (!ts) return "";
    try { return new Date(ts).toLocaleTimeString(); } catch (_) { return ts; }
  }
  function calcDuration(a, b) {
    if (!a || !b) return "";
    const d = (new Date(b) - new Date(a)) / 1000;
    return d > 60 ? (d/60).toFixed(1) + "m" : d.toFixed(1) + "s";
  }
  function calcTraceDuration(evts) {
    if (evts.length < 2) return "0ms";
    const d = new Date(evts[evts.length-1].ts) - new Date(evts[0].ts);
    return d > 1000 ? (d/1000).toFixed(1) + "s" : d + "ms";
  }
  function setText(id, v) { const e = document.getElementById(id); if (e) e.textContent = v; }
  function esc(s) { return s ? String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;") : ""; }

  if (window.onLogsiteAuthStateChanged) {
    window.onLogsiteAuthStateChanged(() => init());
  } else {
    init();
  }
})();
