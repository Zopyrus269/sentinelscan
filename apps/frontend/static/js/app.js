"use strict";

const API_BASE_URL = "/api/v1";

document.addEventListener("DOMContentLoaded", () => {
    const targetInput = document.getElementById("targetInput");
    // #openConsentButton is a legacy id (see index.html) -- it no longer
    // opens a consent modal, it directly submits the scan. Kept as-is
    // rather than renamed, since HeroScanInput (main.jsx) clicks it by
    // this id to forward the hero input's submit event.
    const openConsentButton = document.getElementById(
        "openConsentButton"
    );
    const navNewScanButton = document.getElementById(
        "navNewScanButton"
    );
    const openLatestReportButton = document.getElementById(
        "openLatestReportButton"
    );

    const scanError = document.getElementById("scanError");

    const requiredElements = {
        targetInput,
        openConsentButton,
        scanError,
    };

    const missingElements = Object.entries(requiredElements)
        .filter(([, element]) => !element)
        .map(([name]) => name);

    if (missingElements.length > 0) {
        console.error(
            "Missing landing-page elements:",
            missingElements
        );
        return;
    }

    function showError(message) {
        scanError.textContent = message;
        scanError.classList.remove("hidden");
    }

    function clearError() {
        scanError.textContent = "";
        scanError.classList.add("hidden");
    }

    function normalizeTarget(rawTarget) {
        const value = String(rawTarget || "").trim();

        if (!value) {
            throw new Error("Enter a domain name.");
        }

        const candidate = /^https?:\/\//i.test(value)
            ? value
            : `https://${value}`;

        let parsedUrl;

        try {
            parsedUrl = new URL(candidate);
        } catch {
            throw new Error(
                "Enter a valid domain such as example.com."
            );
        }

        if (parsedUrl.username || parsedUrl.password) {
            throw new Error(
                "Targets containing usernames or passwords are not allowed."
            );
        }

        const hostname = parsedUrl.hostname
            .trim()
            .toLowerCase()
            .replace(/\.$/, "");

        if (
            !hostname ||
            hostname === "localhost" ||
            hostname.endsWith(".local") ||
            hostname.endsWith(".internal") ||
            !hostname.includes(".")
        ) {
            throw new Error("Enter a valid public domain.");
        }

        return hostname;
    }

    async function readJsonResponse(response) {
        const contentType =
            response.headers.get("Content-Type") || "";

        if (!contentType.includes("application/json")) {
            const text = await response.text();

            throw new Error(
                text ||
                "The backend returned an invalid response."
            );
        }

        return response.json();
    }

    async function startScan() {
        clearError();

        let target;

        try {
            target = normalizeTarget(targetInput.value);
        } catch (error) {
            showError(error.message);
            targetInput.focus();
            return;
        }

        openConsentButton.disabled = true;

        try {
            const idToken = window.getCurrentUserIdToken
                ? await window.getCurrentUserIdToken()
                : null;

            const headers = {
                "Content-Type": "application/json",
                Accept: "application/json",
            };

            if (idToken) {
                headers.Authorization = `Bearer ${idToken}`;
            }

            const response = await fetch(
                `${API_BASE_URL}/scans`,
                {
                    method: "POST",
                    headers,
                    body: JSON.stringify({ target }),
                }
            );

            const payload = await readJsonResponse(response);

            if (!response.ok) {
                throw new Error(
                    payload.message ||
                    payload.error ||
                    "The scan could not be started."
                );
            }

            if (!payload.scan_id) {
                throw new Error(
                    "The backend did not return a scan ID."
                );
            }

            sessionStorage.setItem(
                "sentinelscan_scan_id",
                payload.scan_id
            );

            sessionStorage.setItem(
                "sentinelscan_target",
                target
            );

            window.location.href =
                `/dashboard?scan_id=${encodeURIComponent(
                    payload.scan_id
                )}`;
        } catch (error) {
            showError(
                error.message ||
                "Unable to connect to the SentinelScan backend."
            );

            openConsentButton.disabled = false;
        }
    }

    openConsentButton.addEventListener(
        "click",
        startScan
    );

    targetInput.addEventListener(
        "keydown",
        (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                openConsentButton.click();
            }
        }
    );

    navNewScanButton?.addEventListener(
        "click",
        () => {
            targetInput.scrollIntoView({
                behavior: "smooth",
                block: "center",
            });

            targetInput.focus();
        }
    );

    openLatestReportButton?.addEventListener(
        "click",
        () => {
            const scanId = sessionStorage.getItem(
                "sentinelscan_scan_id"
            );

            window.location.href = scanId
                ? `/report?scan_id=${encodeURIComponent(
                    scanId
                )}`
                : "/";
        }
    );
});
