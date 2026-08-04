"use strict";

const API_BASE_URL = "/api/v1";

document.addEventListener("DOMContentLoaded", () => {
    const targetInput = document.getElementById("targetInput");
    const openConsentButton = document.getElementById(
        "openConsentButton"
    );
    const navNewScanButton = document.getElementById(
        "navNewScanButton"
    );
    const openLatestReportButton = document.getElementById(
        "openLatestReportButton"
    );

    const confirmModal = document.getElementById("confirmModal");
    const modalBackdrop = document.getElementById("modalBackdrop");
    const modalCloseButton = document.getElementById(
        "modalCloseButton"
    );
    const modalScrollableContent = document.getElementById(
        "modalScrollableContent"
    );

    const ownershipConsent = document.getElementById(
        "ownershipConsent"
    );
    const legalConsent = document.getElementById(
        "legalConsent"
    );

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

    function updateAuthorizeButton() {
        const accepted =
            ownershipConsent.checked &&
            legalConsent.checked;

        authorizeScanButton.disabled = !accepted;

        if (accepted) {
            authorizeScanButton.textContent =
                "Start Authorized Scan";
        } else {
            authorizeScanButton.textContent =
                "I Authorize This Scan";
        }
    }

    function showModal() {
        clearError();

        ownershipConsent.checked = false;
        legalConsent.checked = false;

        updateAuthorizeButton();

        if (modalScrollableContent) {
            modalScrollableContent.scrollTop = 0;
        }

        confirmModal.classList.remove("hidden");
        confirmModal.classList.add("flex");

        document.body.style.overflow = "hidden";
    }

    function hideModal() {
        confirmModal.classList.add("hidden");
        confirmModal.classList.remove("flex");

        document.body.style.overflow = "";
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

        if (
            !ownershipConsent.checked ||
            !legalConsent.checked
        ) {
            showError(
                "Confirm both authorization statements."
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

        const originalText =
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
                        authorization_confirmed: true,
                    }),
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

            hideModal();

            window.location.href =
                `/dashboard?scan_id=${encodeURIComponent(
                    payload.scan_id
                )}`;
        } catch (error) {
            showError(
                error.message ||
                "Unable to connect to the SentinelScan backend."
            );

            authorizeScanButton.disabled = false;
            authorizeScanButton.textContent =
                originalText;

            updateAuthorizeButton();
        }
    }

    openConsentButton.addEventListener(
        "click",
        () => {
            clearError();

            try {
                normalizeTarget(targetInput.value);
                showModal();
            } catch (error) {
                showError(error.message);
                targetInput.focus();
            }
        }
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

    ownershipConsent.addEventListener(
        "change",
        updateAuthorizeButton
    );

    legalConsent.addEventListener(
        "change",
        updateAuthorizeButton
    );

    authorizeScanButton.addEventListener(
        "click",
        startScan
    );

    cancelConsentButton.addEventListener(
        "click",
        hideModal
    );

    modalCloseButton?.addEventListener(
        "click",
        hideModal
    );

    modalBackdrop?.addEventListener(
        "click",
        hideModal
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

    document.addEventListener(
        "keydown",
        (event) => {
            if (
                event.key === "Escape" &&
                confirmModal.classList.contains("flex")
            ) {
                hideModal();
            }
        }
    );

    updateAuthorizeButton();
});
