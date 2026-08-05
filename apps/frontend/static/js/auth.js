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

async function syncSessionWithBackend(user) {
  try {
    const idToken = await user.getIdToken();
    const res = await fetch("/api/v1/auth/session", {
      method: "POST",
      headers: { "Authorization": `Bearer ${idToken}` }
    });
    if (!res.ok) {
      console.error("Session sync failed:", res.status, await res.text());
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
const themeToggleButton = document.getElementById("themeToggleButton");
const themeToggleKnob = document.getElementById("themeToggleKnob");

function applyThemeToggleUI(theme) {
  const isDark = theme === "dark";
  themeToggleButton.setAttribute("aria-checked", isDark ? "true" : "false");
  themeToggleButton.classList.toggle("bg-primary", isDark);
  themeToggleButton.classList.toggle("bg-surface-container-low", !isDark);
  themeToggleKnob.classList.toggle("translate-x-6", isDark);
  themeToggleKnob.classList.toggle("translate-x-1", !isDark);
}

async function loadCurrentTheme() {
  if (!currentUser) return;
  try {
    const idToken = await currentUser.getIdToken();
    const res = await fetch("/api/v1/auth/me", {
      headers: { "Authorization": `Bearer ${idToken}` }
    });
    if (res.ok) {
      const data = await res.json();
      applyThemeToggleUI(data.theme || "light");
    }
  } catch (err) {
    console.error("Failed to load theme:", err);
  }
}

async function toggleTheme() {
  if (!currentUser) return;
  const isDark = themeToggleButton.getAttribute("aria-checked") === "true";
  const newTheme = isDark ? "light" : "dark";
  applyThemeToggleUI(newTheme);
  try {
    const idToken = await currentUser.getIdToken();
    const res = await fetch("/api/v1/auth/theme", {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${idToken}`
      },
      body: JSON.stringify({ theme: newTheme })
    });
    if (!res.ok) {
      console.error("Theme update failed:", res.status, await res.text());
      applyThemeToggleUI(isDark ? "dark" : "light");
    }
  } catch (err) {
    console.error("Theme update error:", err);
    applyThemeToggleUI(isDark ? "dark" : "light");
  }
}

function openAccountModal() {
  profileDropdown.classList.add("hidden");
  accountModal.classList.remove("hidden");
  accountModal.classList.add("flex");
  document.body.style.overflow = "hidden";
  loadCurrentTheme();
}

function closeAccountModal() {
  accountModal.classList.add("hidden");
  accountModal.classList.remove("flex");
  document.body.style.overflow = "";
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
}

openAccountButton.addEventListener("click", (e) => {
  e.stopPropagation();
  openAccountModal();
});

accountModalCloseButton.addEventListener("click", closeAccountModal);
accountModalBackdrop.addEventListener("click", closeAccountModal);

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && accountModal.classList.contains("flex")) {
    closeAccountModal();
  }
});

accountTabSettings.addEventListener("click", () => switchAccountTab("settings"));
accountTabHistory.addEventListener("click", () => switchAccountTab("history"));

themeToggleButton.addEventListener("click", toggleTheme);
