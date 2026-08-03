"use strict";

const API_BASE_URL = "http://127.0.0.1:5000/api/v1";

document.addEventListener("DOMContentLoaded", () => {
    const targetInput = document.getElementById("targetInput");
    const openConsentButton = document.getElementById(
        "openConsentButton"
    );
    const navNewScanButton = document.getElementById(
        "navNewScanButton"
    );
    const confirmModal = document.getElementById("confirmModal");
    const modalBackdrop = document.getElementById("modalBackdrop");
    const ownershipConsent = document.getElementById(
        "ownershipConsent"
    );
    const legalConsent = document.getElementById("legalConsent");
    const authorizeScanButton = document.getElementById(
        "authorizeScanButton"
    );
    const cancelConsentButton = document.getElementById(
        "cancelConsentButton"
    );
    const scanError = document.getElementById("scanError");

    const requiredElements = {
        targetInput,
        openConsentButton,
        confirmModal,
        ownershipConsent,
        legalConsent,
        authorizeScanButton,
        cancelConsentButton,
        scanError,
    };

    const missingElements = Object.entries(requiredElements)
        .filter(([, element]) => !element)
        .map(([name]) => name);

    if (missingElements.length > 0) {
        console.error(
            "SentinelScan landing page is missing required elements:",
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

    function showModal() {
        ownershipConsent.checked = false;
        legalConsent.checked = false;
        updateAuthorizeButton();

        confirmModal.classList.remove("hidden");
        confirmModal.classList.add("flex");
        document.body.style.overflow = "hidden";
    }

    function hideModal() {
        confirmModal.classList.add("hidden");
        confirmModal.classList.remove("flex");
        document.body.style.overflow = "";
    }

    function updateAuthorizeButton() {
        const consentGiven =
            ownershipConsent.checked &&
            legalConsent.checked;

        authorizeScanButton.disabled = !consentGiven;

        if (consentGiven) {
            authorizeScanButton.classList.remove(
                "opacity-50",
                "cursor-not-allowed"
            );
        } else {
            authorizeScanButton.classList.add(
                "opacity-50",
                "cursor-not-allowed"
            );
        }
    }

    function normalizeTarget(rawTarget) {
        const value = String(rawTarget || "").trim();

        if (!value) {
            throw new Error(
                "Enter a domain name before starting the scan."
            );
        }

        let candidate = value;

        if (
            !candidate.startsWith("http://") &&
            !candidate.startsWith("https://")
        ) {
            candidate = `https://${candidate}`;
        }

        let parsedUrl;

        try {
            parsedUrl = new URL(candidate);
        } catch {
            throw new Error(
                "Enter a valid domain, such as example.com."
            );
        }

        const hostname = parsedUrl.hostname.trim();

        if (
            !hostname ||
            hostname === "localhost" ||
            !hostname.includes(".")
        ) {
            throw new Error(
                "Enter a valid public domain, such as example.com."
            );
        }

        return hostname;
    }

    function validateAndOpenModal() {
        clearError();

        try {
            normalizeTarget(targetInput.value);
            showModal();
        } catch (error) {
            showError(error.message);
            targetInput.focus();
        }
    }

    async function startScan() {
        clearError();

        if (
            !ownershipConsent.checked ||
            !legalConsent.checked
        ) {
            showError(
                "You must confirm both authorization statements."
            );
            return;
        }

        let target;

        try {
            target = normalizeTarget(targetInput.value);
        } catch (error) {
            hideModal();
            showError(error.message);
            targetInput.focus();
            return;
        }

        const originalButtonText =
            authorizeScanButton.textContent;

        authorizeScanButton.disabled = true;
        authorizeScanButton.textContent =
            "Starting Assessment...";

        try {
            const response = await fetch(
                `${API_BASE_URL}/scans`,
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        Accept: "application/json",
                    },
                    body: JSON.stringify({
                        target,
                    }),
                }
            );

            const payload = await response.json();

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
                `dashboard.html?scan_id=${encodeURIComponent(
                    payload.scan_id
                )}`;
        } catch (error) {
            hideModal();

            showError(
                error.message ||
                "Unable to connect to the SentinelScan backend."
            );

            authorizeScanButton.disabled = false;
            authorizeScanButton.textContent =
                originalButtonText;

            updateAuthorizeButton();
        }
    }

    ownershipConsent.addEventListener(
        "change",
        updateAuthorizeButton
    );

    legalConsent.addEventListener(
        "change",
        updateAuthorizeButton
    );

    openConsentButton.addEventListener(
        "click",
        validateAndOpenModal
    );

    if (navNewScanButton) {
        navNewScanButton.addEventListener("click", () => {
            targetInput.scrollIntoView({
                behavior: "smooth",
                block: "center",
            });

            targetInput.focus();
        });
    }

    authorizeScanButton.addEventListener(
        "click",
        startScan
    );

    cancelConsentButton.addEventListener(
        "click",
        hideModal
    );

    if (modalBackdrop) {
        modalBackdrop.addEventListener(
            "click",
            hideModal
        );
    }

    targetInput.addEventListener(
        "keydown",
        (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                validateAndOpenModal();
            }
        }
    );

    document.addEventListener("keydown", (event) => {
        if (
            event.key === "Escape" &&
            confirmModal.classList.contains("flex")
        ) {
            hideModal();
        }
    });

    updateAuthorizeButton();
});
