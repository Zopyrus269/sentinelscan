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

let currentUser = null;
let authListeners = [];

/* ----------------------------------------------------------------
   Theme: light / dark
   ---------------------------------------------------------------- */
(function initTheme() {
  const saved = localStorage.getItem("sentinelscan_logsite_theme");
  if (saved === "dark" || (!saved && window.matchMedia("(prefers-color-scheme: dark)").matches)) {
    document.documentElement.classList.add("dark");
  } else {
    document.documentElement.classList.remove("dark");
  }
})();

window.toggleTheme = function () {
  const isDark = document.documentElement.classList.toggle("dark");
  localStorage.setItem("sentinelscan_logsite_theme", isDark ? "dark" : "light");
  updateThemeIcon();
};

function updateThemeIcon() {
  const btn = document.getElementById("btnThemeToggle");
  if (!btn) return;
  const isDark = document.documentElement.classList.contains("dark");
  btn.textContent = isDark ? "☀️" : "🌙";
  btn.title = isDark ? "Switch to light mode" : "Switch to dark mode";
}

/* ----------------------------------------------------------------
   Mobile nav toggle
   ---------------------------------------------------------------- */
window.toggleMobileNav = function () {
  const nav = document.getElementById("mainNav");
  if (nav) nav.classList.toggle("open");
};

/* ----------------------------------------------------------------
   Firebase Auth Helpers
   ---------------------------------------------------------------- */
window.getIdToken = async function () {
  if (!currentUser) return null;
  try { return await currentUser.getIdToken(); }
  catch (e) { console.error("getIdToken failed:", e); return null; }
};

window.loginWithGoogle = async function () {
  try { await signInWithPopup(auth, provider); }
  catch (e) { console.error("Sign-in error:", e); }
};

window.logout = async function () {
  try { await signOut(auth); }
  catch (e) { console.error("Sign-out error:", e); }
};

window.onLogsiteAuthStateChanged = function (callback) {
  authListeners.push(callback);
  // If auth already resolved, fire immediately
  if (currentUser !== undefined) callback(currentUser);
};

/* ----------------------------------------------------------------
   Auth UI: header account widget
   ---------------------------------------------------------------- */
function updateAuthUI(user) {
  const el = document.getElementById("authControls");
  if (!el) return;

  const isDark = document.documentElement.classList.contains("dark");
  const themeBtn = `<button id="btnThemeToggle" onclick="window.toggleTheme()" class="ls-theme-btn" title="${isDark ? 'Switch to light mode' : 'Switch to dark mode'}">${isDark ? '☀️' : '🌙'}</button>`;

  if (user) {
    const email = escapeHtml(user.email || user.uid);
    const photo = user.photoURL;
    const avatar = photo
      ? `<img src="${escapeHtml(photo)}" alt="" style="width:28px;height:28px;border-radius:50%;object-fit:cover;" referrerpolicy="no-referrer" />`
      : `<span style="width:28px;height:28px;border-radius:50%;background:var(--ss-primary-bg);color:var(--ss-primary);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:11px;">DEV</span>`;

    el.innerHTML = `
      <div style="display:flex;align-items:center;gap:8px;">
        ${themeBtn}
        <div style="display:flex;align-items:center;gap:8px;padding:4px 12px 4px 6px;background:var(--ss-surface);border:1px solid var(--ss-border);border-radius:999px;font-size:13px;">
          ${avatar}
          <span style="color:var(--ss-text);font-weight:500;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${email}</span>
          <button onclick="window.logout()" style="margin-left:4px;font-size:12px;font-weight:600;color:var(--ss-text-muted);background:none;border:none;cursor:pointer;padding:2px 4px;transition:color 150ms;">Sign Out</button>
        </div>
      </div>
    `;
  } else {
    el.innerHTML = `
      <div style="display:flex;align-items:center;gap:8px;">
        ${themeBtn}
        <button onclick="window.loginWithGoogle()" class="ls-btn-primary" style="font-size:12px;padding:6px 14px;">Sign in with Google</button>
      </div>
    `;
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

/* ----------------------------------------------------------------
   Auth State Listener
   ---------------------------------------------------------------- */
onAuthStateChanged(auth, (user) => {
  currentUser = user;
  updateAuthUI(user);
  authListeners.forEach((cb) => {
    try { cb(user); } catch (e) { console.error("Auth listener error:", e); }
  });
});
