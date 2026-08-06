"use strict";

const API_BASE_URL = "/api/v1";
const POLL_INTERVAL_MS = 500;

let pollTimer = null;
let scanStartedAt = null;
let activeScanId = null;

document.addEventListener("DOMContentLoaded", () => {
    activeScanId = getScanId();

    bindNavigation();

    if (!activeScanId) {
        showError(
            "No scan ID was provided. Return to the landing page and start a new scan."
        );
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

    const viewReportButton = document.getElementById(
        "viewReportButton"
    );

    const openLatestReportButton =
        document.getElementById(
            "openLatestReportButton"
        );

    newScanButton?.addEventListener("click", () => {
        window.location.href = "/";
    });

    viewReportButton?.addEventListener("click", () => {
        openReport();
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
            enableReportButton();
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
    const progress = clampProgress(
        Number(scan.progress_percent || 0)
    );

    setText(
        "scanTarget",
        scan.target || "Unknown target"
    );

    setText(
        "scanIdDisplay",
        scan.scan_id || activeScanId
    );

    setText(
        "currentWorker",
        friendlyName(
            scan.current_action || "initializing"
        )
    );

    setText(
        "scanStatusBadge",
        friendlyName(scan.status || "IN_PROGRESS")
    );

    renderProgress(progress, scan);
    renderDuration(scan);
    renderEvents(scan.events || []);
    renderWorkers(
        scan.events || [],
        scan.current_action
    );
    renderInsight(scan);
}

function renderProgress(progress, scan) {
    const progressPercent = document.getElementById(
        "progressPercent"
    );

    const progressBar = document.getElementById(
        "progressBar"
    );

    const statusText = document.getElementById(
        "scanStatusText"
    );

    if (progressPercent) {
        progressPercent.innerHTML =
            `${progress}` +
            `<span class="text-headline-md">%</span>`;
    }

    if (progressBar) {
        progressBar.style.width = `${progress}%`;
    }

    if (!statusText) {
        return;
    }

    if (scan.status === "COMPLETED") {
        statusText.textContent =
            "Assessment complete.";
    } else if (scan.status === "FAILED") {
        statusText.textContent =
            "Assessment failed.";
    } else {
        statusText.textContent =
            `Running ${friendlyName(
                scan.current_action || "initialization"
            )}...`;
    }
}

function renderDuration(scan) {
    if (!scan.started_at) {
        setText("scanDuration", "00:00");
        return;
    }

    if (!scanStartedAt) {
        scanStartedAt = new Date(scan.started_at);
    }

    const endTime = scan.completed_at
        ? new Date(scan.completed_at)
        : new Date();

    const totalSeconds = Math.max(
        0,
        Math.floor(
            (endTime.getTime() -
                scanStartedAt.getTime()) /
                1000
        )
    );

    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;

    setText(
        "scanDuration",
        `${String(minutes).padStart(2, "0")}:${String(
            seconds
        ).padStart(2, "0")}`
    );
}

function renderEvents(events) {
    const terminal = document.getElementById(
        "terminalLogs"
    );

    if (!terminal) {
        return;
    }

    if (!events.length) {
        terminal.innerHTML =
            "<p>Waiting for scan events...</p>";

        setText("eventCount", "0 Events");
        setText("completedWorkers", "0 Workers");
        return;
    }

    terminal.innerHTML = "";

    for (const event of events) {
        const line = document.createElement("p");

        line.className = getLogClass(event.level);

        const timestamp = event.timestamp
            ? new Date(event.timestamp).toLocaleTimeString(
                  [],
                  {
                      hour12: false,
                  }
              )
            : "--:--:--";

        line.textContent =
            `[${timestamp}] ` +
            `${String(
                event.level || "info"
            ).toUpperCase()}: ` +
            `${event.message || ""}`;

        terminal.appendChild(line);
    }

    terminal.scrollTop = terminal.scrollHeight;

    setText(
        "eventCount",
        `${events.length} Event${
            events.length === 1 ? "" : "s"
        }`
    );

    const workerCount =
        collectWorkers(events).length;

    setText(
        "completedWorkers",
        `${workerCount} Worker${
            workerCount === 1 ? "" : "s"
        }`
    );
}

function renderWorkers(events, currentWorker) {
    const workerGrid = document.getElementById(
        "workerGrid"
    );

    if (!workerGrid) {
        return;
    }

    const workers = collectWorkers(events);

    if (!workers.length) {
        workerGrid.innerHTML = `
            <div
                class="bg-surface border border-border p-md rounded-xl"
            >
                Waiting for the AI agent to select workers...
            </div>
        `;

        return;
    }

    workerGrid.innerHTML = workers
        .map(({ tool_name: worker, reasoning }) => {
            const isCurrent =
                worker === currentWorker;

            return `
                <article
                    class="bg-surface border ${
                        isCurrent
                            ? "border-primary"
                            : "border-border"
                    } p-md rounded-xl"
                >
                    <div
                        class="flex justify-between items-start gap-sm"
                    >
                        <span
                            class="material-symbols-outlined text-primary"
                        >
                            ${getWorkerIcon(worker)}
                        </span>

                        <span
                            class="${
                                isCurrent
                                    ? "text-primary"
                                    : "text-success"
                            } text-label-sm font-semibold"
                        >
                            ${
                                isCurrent
                                    ? "Running"
                                    : "Selected"
                            }
                        </span>
                    </div>

                    <h3 class="font-semibold mt-sm">
                        ${escapeHtml(
                            friendlyName(worker)
                        )}
                    </h3>

                    <p
                        class="text-body-sm text-on-surface-variant mt-xs"
                    >
                        ${escapeHtml(
                            reasoning || getWorkerDescription(worker)
                        )}
                    </p>
                </article>
            `;
        })
        .join("");
}

function renderInsight(scan) {
    const insight = document.getElementById(
        "aiInsight"
    );

    if (!insight) {
        return;
    }

    if (scan.status === "COMPLETED") {
        insight.textContent =
            "The assessment is complete. Open the report to review findings, CVSS scores and recommendations.";
    } else if (scan.status === "FAILED") {
        insight.textContent =
            scan.error ||
            "The assessment failed before completion.";
    } else {
        insight.textContent =
            `The AI agent is coordinating ` +
            `${friendlyName(
                scan.current_action ||
                    "initialization"
            )} for ${scan.target || "the target"}.`;
    }
}

function collectWorkers(events) {
    const seen = new Map();

    events
        .filter((event) => event.tool_name && event.tool_name !== "generate_report")
        .forEach((event) => {
            seen.set(event.tool_name, event.reasoning || "");
        });

    return [...seen.entries()].map(([tool_name, reasoning]) => ({
        tool_name,
        reasoning,
    }));
}

function enableReportButton() {
    const button = document.getElementById(
        "viewReportButton"
    );

    if (button) {
        button.disabled = false;
    }
}

function stopPolling() {
    if (pollTimer) {
        window.clearInterval(pollTimer);
        pollTimer = null;
    }
}

function clampProgress(progress) {
    if (!Number.isFinite(progress)) {
        return 0;
    }

    return Math.max(
        0,
        Math.min(100, Math.round(progress))
    );
}

function getLogClass(level) {
    switch (String(level || "").toLowerCase()) {
        case "error":
            return "text-error-container";

        case "warning":
            return "text-warning";

        case "success":
            return "text-success";

        default:
            return "text-surface-bright/80";
    }
}

function friendlyName(value) {
    const aliases = {
        initializing: "Initialization",
        initialization: "Initialization",
        complete: "Complete",
        dns_lookup: "DNS Lookup",
        reverse_dns_lookup: "Reverse DNS Lookup",
        port_scan: "Port Scan",
        ssl_check: "SSL Check",
        http_headers: "HTTP Headers",
        cookie_analysis: "Cookie Analysis",
        robots_txt_parse: "robots.txt Parser",
        sitemap_parse: "Sitemap Parser",
        whois_lookup: "WHOIS Lookup",
        calculate_cvss: "CVSS Calculator",
        generate_report: "Report Generator",
        IN_PROGRESS: "In Progress",
        COMPLETED: "Completed",
        FAILED: "Failed",
    };

    return (
        aliases[value] ||
        String(value || "Waiting")
            .replaceAll("_", " ")
            .replace(/\b\w/g, (character) =>
                character.toUpperCase()
            )
    );
}

function getWorkerIcon(worker) {
    const icons = {
        dns_lookup: "dns",
        reverse_dns_lookup: "travel_explore",
        port_scan: "router",
        ssl_check: "lock",
        http_headers: "http",
        cookie_analysis: "cookie",
        robots_txt_parse: "smart_toy",
        sitemap_parse: "account_tree",
        whois_lookup: "public",
        calculate_cvss: "speed",
    };

    return icons[worker] || "security";
}

function getWorkerDescription(worker) {
    const descriptions = {
        dns_lookup:
            "Retrieves public DNS records.",
        reverse_dns_lookup:
            "Resolves IP addresses to public hostnames.",
        port_scan:
            "Checks the configured authorized port set.",
        ssl_check:
            "Inspects certificate and negotiated TLS details.",
        http_headers:
            "Checks important HTTP security headers.",
        cookie_analysis:
            "Inspects cookie security attributes.",
        robots_txt_parse:
            "Parses publicly available robots.txt directives.",
        sitemap_parse:
            "Discovers publicly listed sitemap URLs.",
        whois_lookup:
            "Retrieves public domain registration information.",
        calculate_cvss:
            "Calculates supported CVSS v3.1 base scores.",
    };

    return (
        descriptions[worker] ||
        "SentinelScan worker activity."
    );
}

function showError(message) {
    const errorBox = document.getElementById(
        "dashboardError"
    );

    if (!errorBox) {
        console.error(message);
        return;
    }

    errorBox.textContent = message;
    errorBox.classList.remove("hidden");
}

function clearError() {
    const errorBox = document.getElementById(
        "dashboardError"
    );

    if (!errorBox) {
        return;
    }

    errorBox.textContent = "";
    errorBox.classList.add("hidden");
}

function setText(elementId, value) {
    const element =
        document.getElementById(elementId);

    if (element) {
        element.textContent = String(value);
    }
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}
