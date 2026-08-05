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
    profileIconDefault.classList.add("hidden");
    profileAvatar.src = user.photoURL;
    profileAvatar.classList.remove("hidden");
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
