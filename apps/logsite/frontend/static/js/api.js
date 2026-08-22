/**
 * SentinelScan Log Site — API Fetch Client
 *
 * Attaches Firebase ID token. Renders auth banners BELOW the navbar
 * inside #logsiteAuthBanner (normal document flow, never fixed/overlay).
 */
window.apiFetch = async function (path, params = {}) {
  const url = new URL(path, window.location.origin);
  Object.keys(params).forEach((k) => {
    const v = params[k];
    if (v !== undefined && v !== null && v !== "") url.searchParams.append(k, v);
  });

  const headers = {};
  if (window.getIdToken) {
    const tok = await window.getIdToken();
    if (tok) headers["Authorization"] = "Bearer " + tok;
  }

  let res;
  try {
    res = await fetch(url.toString(), { headers });
  } catch (err) {
    showAuthBanner("Network request failed. Please check your connection.", "error");
    throw new Error("Network error");
  }

  if (res.status === 401) {
    showAuthBanner("Sign in with Google to view SentinelScan developer telemetry.", "warning");
    throw new Error("Unauthorized");
  }
  if (res.status === 403) {
    showAuthBanner("This Google account does not have SentinelScan developer access.", "error");
    throw new Error("Forbidden");
  }

  if (!res.ok) {
    let msg = "HTTP " + res.status;
    try { const b = await res.json(); msg = b.message || b.error || msg; } catch (_) {}
    throw new Error(msg);
  }

  hideAuthBanner();
  return await res.json();
};

function showAuthBanner(message, type) {
  const el = document.getElementById("logsiteAuthBanner");
  if (!el) return;

  const isWarn = type === "warning";
  el.className = "ls-auth-banner " + (isWarn ? "warning" : "error");

  const btnHtml = isWarn
    ? '<button onclick="window.loginWithGoogle()" class="ls-btn-primary" style="white-space:nowrap;font-size:12px;padding:6px 14px;">Sign in with Google</button>'
    : '<button onclick="window.logout()" class="ls-btn-secondary" style="white-space:nowrap;font-size:12px;padding:6px 14px;">Switch Account</button>';

  el.innerHTML = `
    <div class="banner-left">
      <span class="banner-icon">${isWarn ? '🔒' : '⚠️'}</span>
      <div>
        <div class="banner-title">${isWarn ? 'Authentication Required' : 'Access Restricted'}</div>
        <div class="banner-desc">${esc(message)}</div>
      </div>
    </div>
    ${btnHtml}
  `;
  el.classList.remove("hidden");
}

function hideAuthBanner() {
  const el = document.getElementById("logsiteAuthBanner");
  if (el) { el.classList.add("hidden"); el.innerHTML = ""; }
}

function esc(s) {
  if (!s) return "";
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}
