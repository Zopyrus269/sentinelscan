import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { getAuth, GoogleAuthProvider, signInWithPopup, signOut, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";

const firebaseConfig = {
  apiKey: "AIzaSyBvWgaqLbG9la-77P__L5WACBQ4t3kkCFU",
  authDomain: "sentinelscan-3f82d.firebaseapp.com",
  projectId: "sentinelscan-3f82d",
  storageBucket: "sentinelscan-3f82d.firebasestorage.app",
  messagingSenderId: "60214574079",
  appId: "1:60214574079:web:5c6e5cd5004ffe6902c5ca"
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const provider = new GoogleAuthProvider();

const profileButton = document.getElementById("profileButton");
const profileDropdown = document.getElementById("profileDropdown");
const profileEmail = document.getElementById("profileEmail");
const profileAvatar = document.getElementById("profileAvatar");
const profileIconDefault = document.getElementById("profileIconDefault");
// Sign Out is a GooeyActionNav (React Bits) mounted by main.jsx directly
// into #signOutActions, not a plain <button> this script wires up itself
// -- see window.performSignOutAction below, which is what that mounted
// component's click callback actually calls.
// The dropdown's own header (avatar + name + email) mirrors the button's
// own avatar/fallback -- same photoURL, same onerror/onload fallback logic
// (see applyAvatar below), just rendered larger alongside the account name.
const profileDropdownAvatar = document.getElementById("profileDropdownAvatar");
const profileDropdownIconDefault = document.getElementById("profileDropdownIconDefault");
const profileDropdownName = document.getElementById("profileDropdownName");

let currentUser = null;

window.getCurrentUserIdToken = async function () {
  if (!currentUser) return null;
  try {
    return await currentUser.getIdToken();
  } catch (err) {
    console.error("Failed to get ID token:", err);
    return null;
  }
};

async function syncSessionWithBackend(user) {
  try {
    const idToken = await user.getIdToken();
    const res = await fetch("/api/v1/auth/session", {
      method: "POST",
      headers: { "Authorization": `Bearer ${idToken}` }
    });
    if (!res.ok) {
      console.error("Session sync failed:", res.status, await res.text());
      if (res.status === 503) {
        // Backend doesn't have Firebase, hide account features
        profileButton.style.display = "none";
      }
    }
  } catch (err) {
    console.error("Session sync error:", err);
  }
}

// Shared by the small button avatar and the dropdown header's larger copy
// of it -- both need the identical "try the photo, fall back to the Google
// icon on error" behavior for the same photoURL.
function applyAvatar(imgEl, fallbackEl, photoURL) {
  if (photoURL) {
    imgEl.onerror = () => {
      imgEl.classList.add("hidden");
      fallbackEl.classList.remove("hidden");
    };
    imgEl.onload = () => {
      fallbackEl.classList.add("hidden");
      imgEl.classList.remove("hidden");
    };
    imgEl.src = photoURL;
  } else {
    fallbackEl.classList.remove("hidden");
    imgEl.classList.add("hidden");
  }
}

function showLoggedInUI(user) {
  applyAvatar(profileAvatar, profileIconDefault, user.photoURL);
  applyAvatar(profileDropdownAvatar, profileDropdownIconDefault, user.photoURL);
  profileDropdownName.textContent =
    user.displayName || (user.email ? user.email.split("@")[0] : "SentinelScan User");
  profileEmail.textContent = user.email || "";
}

function showLoggedOutUI() {
  profileIconDefault.classList.remove("hidden");
  profileAvatar.classList.add("hidden");
  profileAvatar.src = "";
  profileDropdownIconDefault.classList.remove("hidden");
  profileDropdownAvatar.classList.add("hidden");
  profileDropdownAvatar.src = "";
  profileDropdownName.textContent = "";
  profileEmail.textContent = "";
  profileDropdown.classList.remove("is-open");
}

onAuthStateChanged(auth, (user) => {
  currentUser = user;
  if (user) {
    showLoggedInUI(user);
    syncSessionWithBackend(user);
  } else {
    showLoggedOutUI();
  }
});

profileButton.addEventListener("click", async (e) => {
  e.stopPropagation();
  if (currentUser) {
    profileDropdown.classList.toggle("is-open");
  } else {
    try {
      await signInWithPopup(auth, provider);
    } catch (err) {
      console.error("Sign-in error:", err);
    }
  }
});

document.addEventListener("click", (e) => {
  if (profileDropdown.classList.contains("is-open") && !profileDropdown.contains(e.target) && e.target !== profileButton) {
    profileDropdown.classList.remove("is-open");
  }
});

// Called by the GooeyActionNav main.jsx mounts into #signOutActions, once
// its click animation finishes (see GooeyActionNav.jsx's own delay).
window.performSignOutAction = async function () {
  try {
    await signOut(auth);
  } catch (err) {
    console.error("Sign-out error:", err);
  }
};

const openAccountButton = document.getElementById("openAccountButton");
const accountModal = document.getElementById("accountModal");
const accountModalBackdrop = document.getElementById("accountModalBackdrop");
const accountModalCloseButton = document.getElementById("accountModalCloseButton");
const accountTabSettings = document.getElementById("accountTabSettings");
const accountTabHistory = document.getElementById("accountTabHistory");
const accountPanelSettings = document.getElementById("accountPanelSettings");
const accountPanelHistory = document.getElementById("accountPanelHistory");

function openAccountModal() {
  profileDropdown.classList.remove("is-open");
  accountModal.classList.remove("hidden");
  accountModal.classList.add("flex");
  document.body.style.overflow = "hidden";
  loadHistory();
}

function closeAccountModal() {
  accountModal.classList.add("hidden");
  accountModal.classList.remove("flex");
  document.body.style.overflow = "";
}

async function loadHistory() {
  if (!currentUser) return;
  const historyLoading = document.getElementById("historyLoading");
  const historyEmpty = document.getElementById("historyEmpty");
  const historyError = document.getElementById("historyError");
  const historyList = document.getElementById("historyList");
  
  historyLoading.classList.remove("hidden");
  historyEmpty.classList.add("hidden");
  historyError.classList.add("hidden");
  historyList.innerHTML = "";

  try {
    const idToken = await currentUser.getIdToken();
    const res = await fetch("/api/v1/history", {
      headers: { "Authorization": `Bearer ${idToken}` }
    });
    
    if (!res.ok) {
      throw new Error(`Failed to load history (${res.status})`);
    }
    
    const data = await res.json();
    historyLoading.classList.add("hidden");
    
    if (!data || data.length === 0) {
      historyEmpty.classList.remove("hidden");
      return;
    }
    
    data.forEach(scan => {
      const card = document.createElement("div");
      card.className = "border border-white/10 rounded-lg p-4 bg-white/[0.03]";

      const startedAt = scan.started_at ? new Date(scan.started_at).toLocaleString() : "Unknown";
      const completedAt = scan.completed_at ? new Date(scan.completed_at).toLocaleString() : "Pending";
      const statusColor =
        scan.status === "COMPLETED" ? "text-emerald-400" :
        scan.status === "FAILED" ? "text-red-400" : "text-yellow-400";

      let summaryHtml = "";
      if (scan.summary) {
        summaryHtml = `<p class="text-xs text-gray-400 mt-2 line-clamp-2">${scan.summary}</p>`;
      }

      // React Bits' GooeyNav (see GooeyActionNav.jsx) is mounted into
      // actionsId below by main.jsx's window.mountGooeyActionNav bridge --
      // this plain script builds the card's HTML but doesn't own the
      // actions row itself. statusLineId is a plain text line these
      // actions report into (loading/error), separate from GooeyNav's own
      // click animation.
      const actionsId = `scan-actions-${scan.scan_id}`;
      const statusLineId = `scan-status-${scan.scan_id}`;

      card.innerHTML = `
        <div class="flex justify-between items-start mb-2">
            <h3 class="text-sm text-white">$ target: <span class="text-cyan-400">${scan.target}</span></h3>
            <span class="text-xs font-bold ${statusColor}">[${scan.status}]</span>
        </div>
        <div class="text-xs text-gray-500 mb-2">
            <div>started: ${startedAt}</div>
            <div>completed: ${completedAt}</div>
        </div>
        ${summaryHtml}
        <div id="${actionsId}" class="mt-4"></div>
        <div id="${statusLineId}" class="mt-2 text-xs text-gray-500"></div>
      `;
      historyList.appendChild(card);

      if (window.mountGooeyActionNav) {
        window.mountGooeyActionNav(actionsId, [
          { label: "View Report", onClick: () => viewReport(scan.scan_id, statusLineId) },
          { label: "Download PDF", onClick: () => downloadHistoryFile(scan.scan_id, "pdf", statusLineId) },
          { label: "Download JSON", onClick: () => downloadHistoryFile(scan.scan_id, "json", statusLineId) },
        ]);
      }
    });
  } catch (err) {
    historyLoading.classList.add("hidden");
    historyError.textContent = "An error occurred while loading your history. Please try again.";
    historyError.classList.remove("hidden");
    console.error("History load error:", err);
  }
}

async function viewReport(scanId, statusLineId) {
  const statusEl = document.getElementById(statusLineId);
  if (statusEl) statusEl.textContent = "$ fetching report...";

  try {
    const idToken = await currentUser.getIdToken();
    const res = await fetch(`/api/v1/history/${encodeURIComponent(scanId)}`, {
      headers: { "Authorization": `Bearer ${idToken}` }
    });
    if (!res.ok) throw new Error("Failed to fetch historical report");

    const data = await res.json();
    localStorage.setItem("sentinelscan_historical_report_" + scanId, JSON.stringify(data));
    window.open(`/report?history_id=${encodeURIComponent(scanId)}`, "_blank");
    if (statusEl) statusEl.textContent = "";
  } catch (err) {
    if (statusEl) statusEl.textContent = `$ error: ${err.message}`;
  }
}

async function downloadHistoryFile(scanId, type, statusLineId) {
  const statusEl = document.getElementById(statusLineId);
  if (statusEl) statusEl.textContent = `$ downloading ${type}...`;

  try {
    const idToken = await currentUser.getIdToken();
    const res = await fetch(`/api/v1/reports/${encodeURIComponent(scanId)}/${type}`, {
      headers: { "Authorization": `Bearer ${idToken}` }
    });

    if (!res.ok) {
      let msg = "Download failed.";
      try {
        const err = await res.json();
        msg = err.message || err.error || msg;
      } catch (jsonErr) {}
      throw new Error(msg);
    }

    const blob = await res.blob();
    if (blob.size === 0) throw new Error("The downloaded file was empty.");

    const objectUrl = URL.createObjectURL(blob);
    if (type === "pdf") {
      window.open(objectUrl, "_blank");
      // Revoke after a longer time to ensure it loads in the new tab
      setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
    } else {
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = `sentinelscan_report_${scanId}.${type}`;
      anchor.style.display = "none";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();

      setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    }
    if (statusEl) statusEl.textContent = "";
  } catch (err) {
    if (statusEl) statusEl.textContent = `$ error: ${err.message}`;
  }
}

function switchAccountTab(tab) {
  const isSettings = tab === "settings";
  accountPanelSettings.classList.toggle("hidden", !isSettings);
  accountPanelHistory.classList.toggle("hidden", isSettings);
  accountTabSettings.classList.toggle("border-primary", isSettings);
  accountTabSettings.classList.toggle("text-primary", isSettings);
  accountTabSettings.classList.toggle("border-transparent", !isSettings);
  accountTabSettings.classList.toggle("text-on-surface-variant", !isSettings);
  accountTabHistory.classList.toggle("border-primary", !isSettings);
  accountTabHistory.classList.toggle("text-primary", !isSettings);
  accountTabHistory.classList.toggle("border-transparent", isSettings);
  accountTabHistory.classList.toggle("text-on-surface-variant", isSettings);
  
  if (!isSettings) {
      loadHistory();
  }
}

openAccountButton.addEventListener("click", (e) => {
  e.stopPropagation();
  openAccountModal();
});

accountModalCloseButton.addEventListener("click", closeAccountModal);
accountModalBackdrop.addEventListener("click", closeAccountModal);

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && accountModal && accountModal.classList.contains("flex")) {
    closeAccountModal();
  }
});

if (accountTabSettings) accountTabSettings.addEventListener("click", () => switchAccountTab("settings"));
if (accountTabHistory) accountTabHistory.addEventListener("click", () => switchAccountTab("history"));
