"use strict";

const API_BASE_URL = "http://127.0.0.1:5000/api/v1";
const POLL_INTERVAL_MS = 2000;

let pollTimer = null;
let scanStartedAt = null;
let renderedEventCount = 0;

document.addEventListener("DOMContentLoaded", () => {
    const scanId = getScanId();

    document
        .getElementById("newScanButton")
        .addEventListener("click", () => {
            window.location.href = "../landing/index.html";
        });

    if (!scanId) {
        showError(
            "No scan ID was provided. Start a new scan from the landing page."
        );
        updateStatus("FAILED");
        return;
    }

    loadScan(scanId);

    pollTimer = window.setInterval(() => {
        loadScan(scanId);
    }, POLL_INTERVAL_MS);
});

function getScanId() {
    const params = new URLSearchParams(window.location.search);

    return (
        params.get("scan_id") ||
        sessionStorage.getItem("sentinelscan_scan_id")
    );
}

async function loadScan(scanId) {
    try {
        const response = await fetch(
            `${API_BASE_URL}/scans/${encodeURIComponent(scanId)}`,
            {
                headers: {
                    Accept: "application/json",
                },
            }
        );

        const payload = await response.json();

        if (!response.ok) {
            throw new Error(
                payload.message ||
                payload.error ||
                "Unable to retrieve scan status."
            );
        }

        clearError();
        renderScan(payload);

        if (payload.status === "COMPLETED") {
            stopPolling();

            window.setTimeout(() => {
                window.location.href =
                    `../report/report.html?scan_id=${encodeURIComponent(
                        payload.scan_id
                    )}`;
            }, 1500);
        }

        if (payload.status === "FAILED") {
            stopPolling();

            showError(
                payload.error ||
                "The assessment failed before completion."
            );
        }
    } catch (error) {
        showError(
            error.message ||
            "Unable to communicate with the SentinelScan backend."
        );
    }
}

function renderScan(scan) {
    const progress = Number(scan.progress_percent || 0);
    const status = scan.status || "PENDING";
    const currentAction = scan.current_action || "queued";

    document.getElementById("scanTarget").textContent =
        scan.target || "Unknown target";

    document.getElementById("currentWorker").textContent =
        formatWorkerName(currentAction);

    document.getElementById("progressPercent").innerHTML =
        `${progress}<span class="text-headline-md">%</span>`;

    document.getElementById("progressBar").style.width =
        `${Math.min(100, Math.max(0, progress))}%`;

    document.getElementById("scanStatusText").textContent =
        getStatusMessage(status, currentAction);

    updateStatus(status);
    renderDuration(scan);
    renderEvents(scan.events || []);
    renderWorkerGrid(scan.events || [], currentAction);
    renderInsight(scan);
}

function updateStatus(status) {
    const statusText = document.getElementById("scanStatusText");

    if (status === "COMPLETED") {
        statusText.textContent =
            "Assessment completed. Opening report...";
        statusText.className =
            "text-label-md font-label-md text-success pb-2";
    } else if (status === "FAILED") {
        statusText.textContent = "Assessment failed.";
        statusText.className =
            "text-label-md font-label-md text-error pb-2";
    } else {
        statusText.className =
            "text-label-md font-label-md text-on-surface-variant pb-2";
    }
}

function getStatusMessage(status, currentAction) {
    const messages = {
        PENDING: "Assessment is queued...",
        IN_PROGRESS: `Running ${formatWorkerName(currentAction)}...`,
        COMPLETED: "Assessment completed.",
        FAILED: "Assessment failed.",
    };

    return messages[status] || "Assessment status unavailable.";
}

function renderDuration(scan) {
    if (!scan.started_at) {
        document.getElementById("scanDuration").textContent = "00:00";
        return;
    }

    if (!scanStartedAt) {
        scanStartedAt = new Date(scan.started_at);
    }

    const endTime = scan.completed_at
        ? new Date(scan.completed_at)
        : new Date();

    const elapsedSeconds = Math.max(
        0,
        Math.floor((endTime - scanStartedAt) / 1000)
    );

    const minutes = String(
        Math.floor(elapsedSeconds / 60)
    ).padStart(2, "0");

    const seconds = String(
        elapsedSeconds % 60
    ).padStart(2, "0");

    document.getElementById(
        "scanDuration"
    ).textContent = `${minutes}:${seconds}`;
}

function renderEvents(events) {
    const terminal = document.getElementById("terminalLogs");

    if (!events.length) {
        terminal.innerHTML = `
            <p class="text-primary-fixed-dim animate-pulse">
                Waiting for scan events...
            </p>
        `;
        return;
    }

    if (events.length === renderedEventCount) {
        return;
    }

    terminal.innerHTML = "";

    events.forEach((event) => {
        const line = document.createElement("p");
        const timestamp = formatTimestamp(event.timestamp);
        const level = String(event.level || "info").toUpperCase();

        line.className = getLogClass(event.level);
        line.textContent =
            `[${timestamp}] ${level}: ${event.message || ""}`;

        terminal.appendChild(line);
    });

    renderedEventCount = events.length;
    terminal.scrollTop = terminal.scrollHeight;

    document.getElementById(
        "eventCount"
    ).textContent = `${events.length} Events`;

    const workers = getUniqueWorkers(events);

    document.getElementById(
        "completedWorkers"
    ).textContent =
        `${workers.length} Worker${workers.length === 1 ? "" : "s"}`;
}

function renderWorkerGrid(events, currentAction) {
    const workerGrid = document.getElementById("workerGrid");
    const workers = getUniqueWorkers(events);

    if (!workers.length) {
        workerGrid.innerHTML = `
            <div class="bg-surface border border-border p-md rounded-xl">
                <p class="text-body-sm text-on-surface-variant">
                    Waiting for the AI agent to choose its first worker.
                </p>
            </div>
        `;
        return;
    }

    workerGrid.innerHTML = workers
        .map((worker) => {
            const isCurrent = worker === currentAction;
            const label = formatWorkerName(worker);

            return `
                <article
                    class="bg-surface border ${
                        isCurrent
                            ? "border-primary"
                            : "border-border"
                    } p-md rounded-xl hover:shadow-md transition-shadow"
                >
                    <div class="flex justify-between items-start mb-sm">
                        <div
                            class="w-10 h-10 rounded-lg bg-primary-fixed flex items-center justify-center text-primary"
                        >
                            <span class="material-symbols-outlined">
                                ${getWorkerIcon(worker)}
                            </span>
                        </div>

                        <span
                            class="${
                                isCurrent
                                    ? "bg-primary/10 text-primary"
                                    : "bg-success/10 text-success"
                            } px-xs py-0.5 rounded-full text-label-sm font-label-sm"
                        >
                            ${isCurrent ? "Running" : "Selected"}
                        </span>
                    </div>

                    <h3 class="text-body-lg font-semibold mb-1">
                        ${escapeHtml(label)}
                    </h3>

                    <p class="text-body-sm text-on-surface-variant">
                        ${escapeHtml(getWorkerDescription(worker))}
                    </p>

                    <div
                        class="mt-md pt-sm border-t border-border flex justify-between items-center"
                    >
                        <span
                            class="text-label-sm font-label-sm text-on-surface-variant"
                        >
                            ${isCurrent ? "In progress" : "Activity recorded"}
                        </span>

                        <span
                            class="material-symbols-outlined text-on-surface-variant"
                        >
                            ${isCurrent ? "sync" : "check_circle"}
                        </span>
                    </div>
                </article>
            `;
        })
        .join("");
}

function renderInsight(scan) {
    const insight = document.getElementById("aiInsight");

    if (scan.status === "COMPLETED") {
        insight.textContent =
            "The AI-guided assessment has completed. Your structured report is ready.";
    } else if (scan.status === "FAILED") {
        insight.textContent =
            scan.error ||
            "The assessment stopped because an error occurred.";
    } else {
        insight.textContent =
            `The AI agent is currently coordinating ${
                formatWorkerName(scan.current_action || "initialization")
            } for ${scan.target}.`;
    }
}

function getUniqueWorkers(events) {
    const workers = events
        .map((event) => event.tool_name)
        .filter(Boolean)
        .filter((worker) => worker !== "generate_report");

    return [...new Set(workers)];
}

function formatWorkerName(workerName) {
    if (!workerName) {
        return "Waiting";
    }

    const aliases = {
        queued: "Queued",
        initializing: "Initialization",
        complete: "Report Complete",
        failed: "Assessment Failed",
        dns_lookup: "DNS Lookup",
        reverse_dns_lookup: "Reverse DNS Lookup",
        port_scan: "Port Scan",
        ssl_check: "SSL Certificate Check",
        http_headers: "HTTP Headers",
        cookie_analysis: "Cookie Analysis",
        robots_txt_parse: "robots.txt Parser",
        sitemap_parse: "Sitemap Parser",
        whois_lookup: "WHOIS Lookup",
        calculate_cvss: "CVSS Calculator",
        generate_report: "Report Generator",
    };

    return (
        aliases[workerName] ||
        workerName
            .replaceAll("_", " ")
            .replace(/\b\w/g, (character) =>
                character.toUpperCase()
            )
    );
}

function getWorkerDescription(workerName) {
    const descriptions = {
        dns_lookup:
            "Retrieves public DNS records and target infrastructure information.",
        reverse_dns_lookup:
            "Attempts to resolve discovered IP addresses back to hostnames.",
        port_scan:
            "Checks authorized common ports and identifies visible services.",
        ssl_check:
            "Inspects certificate validity, expiry, protocol, and cipher information.",
        http_headers:
            "Checks public HTTP responses for important security headers.",
        cookie_analysis:
            "Examines response cookies for Secure and HttpOnly attributes.",
        robots_txt_parse:
            "Parses publicly available robots.txt directives.",
        sitemap_parse:
            "Discovers publicly listed sitemap URLs and endpoints.",
        whois_lookup:
            "Retrieves publicly available domain-registration information.",
        calculate_cvss:
            "Calculates an official CVSS v3.1 base score from supplied metrics.",
    };

    return (
        descriptions[workerName] ||
        "SentinelScan worker activity."
    );
}

function getWorkerIcon(workerName) {
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

    return icons[workerName] || "security";
}

function getLogClass(level) {
    const classes = {
        success: "text-success",
        error: "text-error-container",
        warning: "text-warning",
        info: "text-surface-bright/80",
    };

    return classes[level] || classes.info;
}

function formatTimestamp(timestamp) {
    if (!timestamp) {
        return "--:--:--";
    }

    return new Date(timestamp).toLocaleTimeString([], {
        hour12: false,
    });
}

function showError(message) {
    const errorBox = document.getElementById("dashboardError");

    errorBox.textContent = message;
    errorBox.classList.remove("hidden");
}

function clearError() {
    const errorBox = document.getElementById("dashboardError");

    errorBox.textContent = "";
    errorBox.classList.add("hidden");
}

function stopPolling() {
    if (pollTimer !== null) {
        window.clearInterval(pollTimer);
        pollTimer = null;
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
