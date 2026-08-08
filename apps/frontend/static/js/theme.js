"use strict";

(() => {
    const STORAGE_KEY = "sentinelscan_theme";
    const VALID_THEMES = new Set(["light", "dark", "system"]);

    function getStoredTheme() {
        const stored = localStorage.getItem(STORAGE_KEY);
        return VALID_THEMES.has(stored) ? stored : "system";
    }

    function resolveTheme(preference) {
        if (preference === "system") {
            return window.matchMedia("(prefers-color-scheme: dark)").matches
                ? "dark"
                : "light";
        }
        return preference;
    }

    function updateToggleControls(preference, resolved) {
        document.querySelectorAll("[data-theme-toggle], #themeToggleButton").forEach((button) => {
            button.setAttribute("aria-checked", resolved === "dark" ? "true" : "false");
            button.setAttribute("data-theme", preference);
            button.setAttribute(
                "aria-label",
                resolved === "dark" ? "Switch to light theme" : "Switch to dark theme"
            );
            button.title = resolved === "dark" ? "Switch to light theme" : "Switch to dark theme";

            const icon = button.querySelector("[data-theme-icon]");
            if (icon) {
                icon.textContent = resolved === "dark" ? "light_mode" : "dark_mode";
            }
        });

        const accountToggle = document.getElementById("themeToggleButton");
        const knob = document.getElementById("themeToggleKnob");
        if (accountToggle && knob) {
            accountToggle.classList.toggle("bg-primary", resolved === "dark");
            accountToggle.classList.toggle("bg-surface-container-low", resolved !== "dark");
            knob.classList.toggle("translate-x-6", resolved === "dark");
            knob.classList.toggle("translate-x-1", resolved !== "dark");
        }
    }

    function applyTheme(preference, { persist = true } = {}) {
        const safePreference = VALID_THEMES.has(preference) ? preference : "system";
        const resolved = resolveTheme(safePreference);
        const root = document.documentElement;

        root.classList.toggle("dark", resolved === "dark");
        root.classList.toggle("light", resolved !== "dark");
        root.dataset.themePreference = safePreference;
        root.style.colorScheme = resolved;

        if (persist) {
            localStorage.setItem(STORAGE_KEY, safePreference);
        }

        updateToggleControls(safePreference, resolved);
        window.dispatchEvent(
            new CustomEvent("sentinelscan:themechange", {
                detail: { preference: safePreference, resolved },
            })
        );

        return { preference: safePreference, resolved };
    }

    function toggleTheme() {
        const currentResolved = document.documentElement.classList.contains("dark")
            ? "dark"
            : "light";
        return applyTheme(currentResolved === "dark" ? "light" : "dark");
    }

    function createGlobalToggle() {
        if (document.querySelector("[data-global-theme-toggle]")) {
            return;
        }

        const button = document.createElement("button");
        button.type = "button";
        button.dataset.themeToggle = "true";
        button.dataset.globalThemeToggle = "true";
        button.className = "sentinel-theme-toggle";
        button.innerHTML = `
            <span class="material-symbols-outlined" data-theme-icon aria-hidden="true">dark_mode</span>
            <span class="sentinel-theme-toggle-label">Theme</span>
        `;
        button.addEventListener("click", toggleTheme);
        document.body.appendChild(button);
    }

    function bindExistingControls() {
        document.querySelectorAll("[data-theme-toggle], #themeToggleButton").forEach((button) => {
            if (button.dataset.themeBound === "true") {
                return;
            }
            button.dataset.themeBound = "true";
            button.addEventListener("click", toggleTheme);
        });
    }

    const media = window.matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener?.("change", () => {
        if (getStoredTheme() === "system") {
            applyTheme("system", { persist: false });
        }
    });

    window.SentinelTheme = {
        apply: applyTheme,
        toggle: toggleTheme,
        getPreference: getStoredTheme,
        getResolved: () => (document.documentElement.classList.contains("dark") ? "dark" : "light"),
    };

    applyTheme(getStoredTheme(), { persist: false });

    document.addEventListener("DOMContentLoaded", () => {
        createGlobalToggle();
        bindExistingControls();
        updateToggleControls(getStoredTheme(), resolveTheme(getStoredTheme()));
    });
})();
