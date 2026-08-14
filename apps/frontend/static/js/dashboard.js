"use strict";

const API_BASE_URL = "/api/v1";
const POLL_INTERVAL_MS = 500;

let pollTimer = null;
let activeScanId = null;

document.addEventListener("DOMContentLoaded", () => {
    activeScanId = getScanId();

    bindNavigation();

    if (!activeScanId) {
        showNoScanNotice();
        return;
    }

    sessionStorage.setItem(
        "sentinelscan_scan_id",
        activeScanId
    );

    loadScan();

    pollTimer = window.setInterval(
        loadScan,
        POLL_INTERVAL_MS
    );
});

function getScanId() {
    const query = new URLSearchParams(
        window.location.search
    );

    return (
        query.get("scan_id") ||
        sessionStorage.getItem("sentinelscan_scan_id")
    );
}

function bindNavigation() {
    const newScanButton = document.getElementById(
        "newScanButton"
    );

    const openLatestReportButton =
        document.getElementById(
            "openLatestReportButton"
        );

    newScanButton?.addEventListener("click", () => {
        window.location.href = "/";
    });

    openLatestReportButton?.addEventListener(
        "click",
        () => {
            openReport();
        }
    );
}

function openReport() {
    if (!activeScanId) {
        window.location.href = "/";
        return;
    }

    window.location.href =
        `/report?scan_id=${encodeURIComponent(activeScanId)}`;
}

async function loadScan() {
    try {
        const scan = await fetchScan(activeScanId);

        clearError();
        renderScan(scan);

        if (scan.status === "COMPLETED") {
            stopPolling();
        }

        if (scan.status === "FAILED") {
            stopPolling();

            showError(
                scan.error ||
                "The SentinelScan assessment failed."
            );
        }
    } catch (error) {
        /*
         * A temporary backend restart should not destroy the current
         * dashboard. Display the problem and continue polling.
         */
        showError(
            error.message ||
            "Unable to retrieve the scan status."
        );
    }
}

async function fetchScan(scanId) {
    const endpoint =
        `${API_BASE_URL}/scans/${encodeURIComponent(
            scanId
        )}`;

    let response;

    try {
        response = await fetch(endpoint, {
            method: "GET",
            headers: {
                Accept: "application/json",
            },
            cache: "no-store",
        });
    } catch {
        throw new Error(
            "Unable to connect to the SentinelScan backend on port 5000. Make sure python -m backend.app is running."
        );
    }

    const contentType =
        response.headers.get("Content-Type") || "";

    if (!contentType.includes("application/json")) {
        const responseText = await response.text();

        const preview = responseText
            .replace(/\s+/g, " ")
            .trim()
            .slice(0, 100);

        throw new Error(
            `The backend returned HTML instead of JSON ` +
            `(HTTP ${response.status}). ` +
            `Requested: ${endpoint}. ` +
            `${preview ? `Response begins: ${preview}` : ""}`
        );
    }

    let payload;

    try {
        payload = await response.json();
    } catch {
        throw new Error(
            "The backend returned malformed JSON."
        );
    }

    if (!response.ok) {
        throw new Error(
            payload.message ||
            payload.error ||
            `Unable to retrieve scan status (HTTP ${response.status}).`
        );
    }

    return payload;
}

function renderScan(scan) {
    // ScanTerminal (mounted at #sentinelscan-scan-terminal, see main.jsx)
    // owns rendering of scan progress, live events, worker status, and
    // duration -- this dispatch is the only way it receives data, since it
    // runs in the React bundle and dashboard.js is a plain script, not an
    // ES module either side could import from.
    window.dispatchEvent(
        new CustomEvent("sentinelscan:scan-update", { detail: scan })
    );
}

function stopPolling() {
    if (pollTimer) {
        window.clearInterval(pollTimer);
        pollTimer = null;
    }
}

function dispatchDashboardNotice(message) {
    // #sentinelscan-dashboard-notice (mounted by main.jsx) renders the
    // SpecularButton React Bits component for every edge case above the
    // terminal -- no scan ID, an invalid/missing scan, or a fetch/backend
    // error -- so this is the single bridge into it, mirroring the
    // sentinelscan:scan-update pattern used to feed ScanTerminal.
    window.dispatchEvent(
        new CustomEvent("sentinelscan:dashboard-notice", {
            detail: { message },
        })
    );
}

function showNoScanNotice() {
    dispatchDashboardNotice(
        "No scan ID was provided. Return to the landing page and start a new scan."
    );
}

function showError(message) {
    dispatchDashboardNotice(message);
}

function clearError() {
    dispatchDashboardNotice(null);
}

function setText(elementId, value) {
    const element =
        document.getElementById(elementId);

    if (element) {
        element.textContent = String(value);
    }
}
