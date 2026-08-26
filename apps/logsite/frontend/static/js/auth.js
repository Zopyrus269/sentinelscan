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
let authResolved = false;
let authListeners = [];

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
  if (authResolved) callback(currentUser);
};

/* ----------------------------------------------------------------
   Auth UI: Header account widget (Minimal SentinelScan Style)
   ---------------------------------------------------------------- */
function updateAuthUI(user) {
  const el = document.getElementById("authControls");
  if (!el) return;

  if (user) {
    const email = escapeHtml(user.email || user.uid);
    const photo = user.photoURL;
    const avatar = photo
      ? `<img src="${escapeHtml(photo)}" alt="" style="width:24px;height:24px;border-radius:50%;object-fit:cover;" referrerpolicy="no-referrer" />`
      : `<span style="width:24px;height:24px;border-radius:50%;background:rgba(255,255,255,0.1);color:#ffffff;display:inline-flex;align-items:center;justify-content:center;font-weight:600;font-size:10px;">DEV</span>`;

    el.innerHTML = `
      <div style="display:flex;align-items:center;gap:10px;">
        <div style="display:flex;align-items:center;gap:7px;padding:3px 10px 3px 4px;background:rgba(255,255,255,0.04);border:1px solid var(--border);border-radius:999px;font-size:12px;">
          ${avatar}
          <span style="color:var(--text);font-weight:500;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${email}</span>
        </div>
        <button onclick="window.logout()" style="font-size:12px;font-weight:500;color:var(--text-muted);background:none;border:none;cursor:pointer;padding:4px 6px;transition:color 150ms;">Sign Out</button>
      </div>
    `;
  } else {
    el.innerHTML = `
      <button onclick="window.loginWithGoogle()" class="ls-btn-primary" style="font-size:12px;padding:5px 14px;">Sign In</button>
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
  authResolved = true;
  updateAuthUI(user);
  authListeners.forEach((cb) => {
    try { cb(user); } catch (e) { console.error("Auth listener error:", e); }
  });
});
