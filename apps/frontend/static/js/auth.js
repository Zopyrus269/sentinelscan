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
const signOutButton = document.getElementById("signOutButton");

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

function showLoggedInUI(user) {
  if (user.photoURL) {
    profileAvatar.onerror = () => {
      profileAvatar.classList.add("hidden");
      profileIconDefault.classList.remove("hidden");
    };
    profileAvatar.onload = () => {
      profileIconDefault.classList.add("hidden");
      profileAvatar.classList.remove("hidden");
    };
    profileAvatar.src = user.photoURL;
  } else {
    profileIconDefault.classList.remove("hidden");
    profileAvatar.classList.add("hidden");
  }
  profileEmail.textContent = user.email || "";
}

function showLoggedOutUI() {
  profileIconDefault.classList.remove("hidden");
  profileAvatar.classList.add("hidden");
  profileAvatar.src = "";
  profileEmail.textContent = "";
  profileDropdown.classList.add("hidden");
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
    profileDropdown.classList.toggle("hidden");
  } else {
    try {
      await signInWithPopup(auth, provider);
    } catch (err) {
      console.error("Sign-in error:", err);
    }
  }
});

document.addEventListener("click", (e) => {
  if (!profileDropdown.classList.contains("hidden") && !profileDropdown.contains(e.target) && e.target !== profileButton) {
    profileDropdown.classList.add("hidden");
  }
});

signOutButton.addEventListener("click", async (e) => {
  e.stopPropagation();
  try {
    await signOut(auth);
  } catch (err) {
    console.error("Sign-out error:", err);
  }
});

const openAccountButton = document.getElementById("openAccountButton");
const accountModal = document.getElementById("accountModal");
const accountModalBackdrop = document.getElementById("accountModalBackdrop");
const accountModalCloseButton = document.getElementById("accountModalCloseButton");
const accountTabSettings = document.getElementById("accountTabSettings");
const accountTabHistory = document.getElementById("accountTabHistory");
const accountPanelSettings = document.getElementById("accountPanelSettings");
const accountPanelHistory = document.getElementById("accountPanelHistory");

function openAccountModal() {
  profileDropdown.classList.add("hidden");
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
      card.className = "border border-border rounded-lg p-4 bg-surface-container-lowest";
      
      const startedAt = scan.started_at ? new Date(scan.started_at).toLocaleString() : "Unknown";
      const completedAt = scan.completed_at ? new Date(scan.completed_at).toLocaleString() : "Pending";
      const statusColor = scan.status === "COMPLETED" ? "text-primary" : "text-error";
      
      let summaryHtml = "";
      if (scan.summary) {
        summaryHtml = `<p class="text-sm text-on-surface-variant mt-2 line-clamp-2">${scan.summary}</p>`;
      }
      
      card.innerHTML = `
        <div class="flex justify-between items-start mb-2">
            <h3 class="font-medium text-on-background">${scan.target}</h3>
            <span class="text-xs font-bold ${statusColor}">${scan.status}</span>
        </div>
        <div class="text-xs text-on-surface-variant mb-2">
            <div>Started: ${startedAt}</div>
            <div>Completed: ${completedAt}</div>
        </div>
        ${summaryHtml}
        <div class="flex flex-wrap gap-2 mt-4">
            <button data-id="${scan.scan_id}" class="view-report-btn text-xs font-medium bg-primary text-on-primary px-3 py-1.5 rounded hover:opacity-90 transition-opacity">View Report</button>
            <button data-id="${scan.scan_id}" data-type="pdf" class="download-history-btn text-xs font-medium border border-border text-on-surface px-3 py-1.5 rounded hover:bg-surface-container-low transition-colors">Download PDF</button>
            <button data-id="${scan.scan_id}" data-type="json" class="download-history-btn text-xs font-medium border border-border text-on-surface px-3 py-1.5 rounded hover:bg-surface-container-low transition-colors">Download JSON</button>
        </div>
      `;
      historyList.appendChild(card);
    });
    
    document.querySelectorAll(".view-report-btn").forEach(btn => {
      btn.addEventListener("click", async (e) => {
         const scanId = e.target.getAttribute("data-id");
         const btnEl = e.target;
         const originalText = btnEl.textContent;
         
         btnEl.textContent = "Loading...";
         btnEl.disabled = true;

         try {
            const idToken = await currentUser.getIdToken();
            const res = await fetch(`/api/v1/history/${encodeURIComponent(scanId)}`, {
                headers: { "Authorization": `Bearer ${idToken}` }
            });
            if (!res.ok) throw new Error("Failed to fetch historical report");
            
            const data = await res.json();
            localStorage.setItem("sentinelscan_historical_report_" + scanId, JSON.stringify(data));
            window.open(`/report?history_id=${encodeURIComponent(scanId)}`, "_blank");
         } catch (err) {
            alert("Error loading report: " + err.message);
         } finally {
            btnEl.textContent = originalText;
            btnEl.disabled = false;
         }
      });
    });
    
    document.querySelectorAll(".download-history-btn").forEach(btn => {
      btn.addEventListener("click", async (e) => {
         const scanId = e.target.getAttribute("data-id");
         const type = e.target.getAttribute("data-type");
         const btnEl = e.target;
         const originalText = btnEl.textContent;
         
         btnEl.innerHTML = `<span class="material-symbols-outlined text-[14px] align-middle mr-1 animate-spin">progress_activity</span>Downloading...`;
         btnEl.disabled = true;

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
            
         } catch (err) {
            alert("Error downloading file: " + err.message);
         } finally {
            btnEl.textContent = originalText;
            btnEl.disabled = false;
         }
      });
    });
    
  } catch (err) {
    historyLoading.classList.add("hidden");
    historyError.textContent = "An error occurred while loading your history. Please try again.";
    historyError.classList.remove("hidden");
    console.error("History load error:", err);
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
