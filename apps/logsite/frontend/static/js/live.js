/**
 * SentinelScan Log Site — Screen 2: Live Activity Feed
 * 30-second cursor polling. Pauses when tab is hidden.
 */
(function () {
  let nextCursor = null;
  let events = [];
  let pollTimer = null;
  const POLL_INTERVAL = 30000;
  const MAX_EVENTS = 200;

  async function init() {
    setupFilters();
    setupVisibility();
    await poll();
  }

  async function loadActiveUsers() {
    try {
      const data = await window.apiFetch("/api/active-users");
      const el = document.getElementById("liveActiveUsers");
      if (el) el.textContent = String(data.count || 0);
    } catch (_) {}
  }

  async function poll() {
    clearTimeout(pollTimer);
    updatePollingStatus("Fetching…");

    try {
      await loadActiveUsers();

      const params = {};
      if (nextCursor) params.cursor = nextCursor;

      const level = document.getElementById("filterLevel")?.value;
      const source = document.getElementById("filterSource")?.value;
      const category = document.getElementById("filterCategory")?.value;
      if (level) params.level = level;
      if (source) params.source = source;
      if (category) params.category = category;

      const data = await window.apiFetch("/api/events", params);
      const newEvents = data.events || [];
      nextCursor = data.next_cursor || null;

      if (newEvents.length > 0) {
        events = newEvents.concat(events).slice(0, MAX_EVENTS);
        renderEvents();
      } else if (events.length === 0) {
        renderEmptyEvents();
      }

      updatePollingStatus("Live · polling every 30s");
    } catch (err) {
      console.error("Poll error:", err);
      updatePollingStatus("Error: " + err.message);
    }

    pollTimer = setTimeout(poll, POLL_INTERVAL);
  }

  function renderEvents() {
    const tbody = document.getElementById("eventsBody");
    if (!tbody) return;

    if (events.length === 0) {
      renderEmptyEvents();
      return;
    }

    tbody.innerHTML = "";
    events.forEach(evt => {
      const tr = document.createElement("tr");
      const isError = evt.level === "error" || evt.level === "fatal";
      if (isError) tr.className = "row-error";

      // Time (mono)
      const tdTime = document.createElement("td");
      tdTime.className = "mono";
      tdTime.style.fontSize = "12px";
      tdTime.style.color = "var(--ss-text-muted)";
      tdTime.textContent = fmtTime(evt.ts);

      // Level (pill)
      const tdLevel = document.createElement("td");
      const pillClass = "pill pill-" + (evt.level || "info");
      tdLevel.innerHTML = `<span class="${pillClass}">${esc(evt.level || "info")}</span>`;

      // Source
      const tdSource = document.createElement("td");
      tdSource.style.fontSize = "13px";
      tdSource.style.color = "var(--ss-text-secondary)";
      tdSource.textContent = evt.source || "—";

      // Category (badge)
      const tdCat = document.createElement("td");
      tdCat.innerHTML = `<span class="cat-badge">${esc(evt.category || "—")}</span>`;

      // Message
      const tdMsg = document.createElement("td");
      tdMsg.style.fontSize = "13px";
      tdMsg.textContent = evt.message || "";

      tr.appendChild(tdTime);
      tr.appendChild(tdLevel);
      tr.appendChild(tdSource);
      tr.appendChild(tdCat);
      tr.appendChild(tdMsg);
      tbody.appendChild(tr);
    });
  }

  function renderEmptyEvents() {
    const tbody = document.getElementById("eventsBody");
    if (!tbody) return;
    tbody.innerHTML = `
      <tr>
        <td colspan="5" class="ls-empty" style="border:none;">
          <div class="ls-empty-icon">📭</div>
          <div class="ls-empty-title">No events recorded yet</div>
          <div class="ls-empty-desc">Telemetry events will appear here as users interact with SentinelScan.</div>
        </td>
      </tr>
    `;
  }

  function setupFilters() {
    ["filterLevel", "filterSource", "filterCategory"].forEach(id => {
      document.getElementById(id)?.addEventListener("change", resetAndPoll);
    });
    document.getElementById("btnResetFilters")?.addEventListener("click", () => {
      ["filterLevel", "filterSource", "filterCategory"].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = "";
      });
      resetAndPoll();
    });
  }

  function resetAndPoll() {
    nextCursor = null;
    events = [];
    poll();
  }

  function setupVisibility() {
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "hidden") {
        clearTimeout(pollTimer);
      } else {
        poll();
      }
    });
  }

  function updatePollingStatus(msg) {
    const el = document.getElementById("livePollingStatus");
    if (el) el.textContent = msg;
  }

  function fmtTime(ts) {
    if (!ts) return "";
    try { return new Date(ts).toISOString().substring(11, 19); }
    catch (_) { return ts; }
  }

  function esc(s) {
    if (!s) return "";
    return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  }

  if (window.onLogsiteAuthStateChanged) {
    window.onLogsiteAuthStateChanged(() => init());
  } else {
    init();
  }
})();
