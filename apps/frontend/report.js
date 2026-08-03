"use strict";

const API_BASE_URL = "http://127.0.0.1:5000/api/v1";

let activeScanId = null;
let activeScan = null;
let activeReport = null;

document.addEventListener("DOMContentLoaded", () => {
    activeScanId = getScanId();

    bindNavigation();
    bindRawJsonToggle();

    if (!activeScanId) {
        hideLoading();
        showError(
            "No scan ID was provided. Start a new scan from the landing page."
        );
        return;
    }

    loadReport();
});


function getScanId() {
    const queryParams = new URLSearchParams(window.location.search);

    return (
        queryParams.get("scan_id") ||
        sessionStorage.getItem("sentinelscan_scan_id")
    );
}


function bindNavigation() {
    const newScanButton = document.getElementById("newScanButton");
    const backToDashboardButton = document.getElementById(
        "backToDashboardButton"
    );

    newScanButton.addEventListener("click", () => {
        window.location.href = "landing_index.html";
    });

    backToDashboardButton.addEventListener("click", () => {
        if (!activeScanId) {
            window.location.href = "dashboard.html";
            return;
        }

        window.location.href =
            `dashboard.html?scan_id=${encodeURIComponent(
                activeScanId
            )}`;
    });
}


function bindRawJsonToggle() {
    const toggleButton = document.getElementById(
        "toggleRawJsonButton"
    );
    const rawJsonPanel = document.getElementById("rawJsonPanel");
    const toggleIcon = document.getElementById(
        "rawJsonToggleIcon"
    );

    toggleButton.addEventListener("click", () => {
        const isHidden = rawJsonPanel.classList.contains("hidden");

        rawJsonPanel.classList.toggle("hidden");

        toggleIcon.textContent = isHidden
            ? "expand_less"
            : "expand_more";
    });
}


async function loadReport() {
    showLoading();
    clearError();

    try {
        activeScan = await fetchScan(activeScanId);

        if (activeScan.status !== "COMPLETED") {
            throw new Error(
                activeScan.status === "FAILED"
                    ? activeScan.error ||
                      "The assessment failed before a report was generated."
                    : "The assessment is not complete yet."
            );
        }

        activeReport = await fetchJsonReport(activeScanId);

        renderScanMetadata(activeScan);
        renderReport(activeReport);
        configureDownloadButtons(activeScanId);

        hideLoading();
    } catch (error) {
        hideLoading();

        showError(
            error.message ||
            "Unable to load the SentinelScan report."
        );
    }
}


async function fetchScan(scanId) {
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
            "Unable to retrieve the scan."
        );
    }

    return payload;
}


async function fetchJsonReport(scanId) {
    const response = await fetch(
        `${API_BASE_URL}/reports/${encodeURIComponent(scanId)}/json`,
        {
            headers: {
                Accept: "application/json",
            },
        }
    );

    if (!response.ok) {
        let message = "Unable to retrieve the JSON report.";

        try {
            const payload = await response.json();

            message =
                payload.message ||
                payload.error ||
                message;
        } catch {
            // The response may not contain JSON.
        }

        throw new Error(message);
    }

    return response.json();
}


function renderScanMetadata(scan) {
    document.getElementById("reportTarget").textContent =
        scan.target || "Unknown target";

    document.getElementById("reportScanId").textContent =
        scan.scan_id || activeScanId;

    document.getElementById("reportCompletedAt").textContent =
        formatDate(scan.completed_at);

    document.getElementById("reportStatus").textContent =
        formatStatus(scan.status);

    document.getElementById("reportIdLabel").textContent =
        `REPORT_ID: ${scan.scan_id || activeScanId}`;
}


function renderReport(report) {
    const findings = Array.isArray(report.findings)
        ? report.findings
        : [];

    const cvssScores = Array.isArray(report.cvss_scores)
        ? report.cvss_scores
        : [];

    const riskSummary = normalizeRiskSummary(
        report.overall_risk_summary
    );

    const maximumCvss = getMaximumCvss(cvssScores);
    const securityScore = calculateSecurityScore(maximumCvss);

    renderSecurityScore(securityScore);
    renderMaximumCvss(maximumCvss);
    renderRiskSummary(riskSummary);
    renderExecutiveSummary(
        report,
        findings,
        cvssScores,
        maximumCvss
    );
    renderFindings(findings, cvssScores);
    renderCvssScores(cvssScores);
    renderWorkerFindings(findings);
    renderRecommendations(findings, cvssScores);
    renderRawJson(report);
}


function normalizeRiskSummary(summary) {
    const safeSummary =
        summary && typeof summary === "object"
            ? summary
            : {};

    return {
        CRITICAL: Number(safeSummary.CRITICAL || 0),
        HIGH: Number(safeSummary.HIGH || 0),
        MEDIUM: Number(safeSummary.MEDIUM || 0),
        LOW: Number(safeSummary.LOW || 0),
        INFORMATIONAL: Number(
            safeSummary.INFORMATIONAL || 0
        ),
    };
}


function getMaximumCvss(cvssScores) {
    if (!cvssScores.length) {
        return 0;
    }

    return cvssScores.reduce((maximum, item) => {
        const score = Number(item.base_score || 0);
        return Math.max(maximum, score);
    }, 0);
}


function calculateSecurityScore(maximumCvss) {
    /*
     * SentinelScan's backend currently provides CVSS values but does not
     * provide an official overall 0–100 security score. This UI score is
     * therefore a display value derived from the highest CVSS score.
     */
    return Math.max(
        0,
        Math.min(100, Math.round(100 - maximumCvss * 10))
    );
}


function renderSecurityScore(score) {
    const gauge = document.getElementById("securityGauge");
    const scoreElement = document.getElementById(
        "securityScore"
    );
    const riskLabel = document.getElementById("riskLabel");

    const radius = 88;
    const circumference = 2 * Math.PI * radius;
    const offset =
        circumference - (score / 100) * circumference;

    gauge.style.strokeDasharray = String(circumference);
    gauge.style.strokeDashoffset = String(offset);

    scoreElement.textContent = String(score);

    const rating = getSecurityRating(score);

    riskLabel.className =
        `mt-md ${rating.textClass} font-label-md ` +
        "flex items-center gap-base";

    riskLabel.innerHTML = `
        <span class="material-symbols-outlined text-sm">
            ${rating.icon}
        </span>
        ${escapeHtml(rating.label)}
    `;

    gauge.setAttribute(
        "class",
        `${rating.gaugeClass} gauge-ring`
    );
}


function getSecurityRating(score) {
    if (score >= 90) {
        return {
            label: "Low Observed Risk",
            icon: "verified_user",
            textClass: "text-success",
            gaugeClass: "text-success gauge-ring",
        };
    }

    if (score >= 70) {
        return {
            label: "Moderate Observed Risk",
            icon: "warning",
            textClass: "text-warning",
            gaugeClass: "text-warning gauge-ring",
        };
    }

    if (score >= 40) {
        return {
            label: "High Observed Risk",
            icon: "error",
            textClass: "text-error",
            gaugeClass: "text-error gauge-ring",
        };
    }

    return {
        label: "Critical Observed Risk",
        icon: "dangerous",
        textClass: "text-critical",
        gaugeClass: "text-critical gauge-ring",
    };
}


function renderMaximumCvss(maximumCvss) {
    document.getElementById(
        "maxCvssScore"
    ).textContent = maximumCvss.toFixed(1);
}


function renderRiskSummary(summary) {
    document.getElementById("criticalCount").textContent =
        String(summary.CRITICAL);

    document.getElementById("highCount").textContent =
        String(summary.HIGH);

    document.getElementById("mediumCount").textContent =
        String(summary.MEDIUM);

    document.getElementById("lowCount").textContent =
        String(summary.LOW);

    document.getElementById(
        "informationalCount"
    ).textContent = String(summary.INFORMATIONAL);
}


function renderExecutiveSummary(
    report,
    findings,
    cvssScores,
    maximumCvss
) {
    const target =
        report.target ||
        activeScan?.target ||
        "the assessed target";

    const workerCount = new Set(
        findings
            .map((finding) => finding.worker)
            .filter(Boolean)
    ).size;

    let summary;

    if (!findings.length) {
        summary =
            `SentinelScan completed its authorized assessment of ` +
            `${target}. No reportable findings were included in the ` +
            `generated report. Review the raw worker output and confirm ` +
            `that all expected assessment steps completed successfully.`;
    } else {
        summary =
            `SentinelScan completed an AI-guided assessment of ${target}. ` +
            `${findings.length} finding${findings.length === 1 ? "" : "s"} ` +
            `were compiled from ${workerCount} worker` +
            `${workerCount === 1 ? "" : "s"}. `;

        if (cvssScores.length) {
            summary +=
                `The highest calculated CVSS v3.1 base score was ` +
                `${maximumCvss.toFixed(1)}. `;
        } else {
            summary +=
                "No CVSS-scored findings were included. ";
        }

        summary +=
            "Review each finding and validate the recommended actions " +
            "before making production changes.";
    }

    document.getElementById(
        "executiveSummary"
    ).textContent = summary;
}


function renderFindings(findings, cvssScores) {
    const list = document.getElementById("findingsList");
    const count = document.getElementById("findingsCount");

    count.textContent =
        `${findings.length} Finding` +
        `${findings.length === 1 ? "" : "s"}`;

    if (!findings.length) {
        list.innerHTML = `
            <div class="bg-surface border border-border rounded-xl p-md">
                <div class="flex items-start gap-sm">
                    <span class="material-symbols-outlined text-success">
                        check_circle
                    </span>

                    <div>
                        <h3 class="text-body-lg font-semibold">
                            No reportable findings
                        </h3>

                        <p class="text-body-sm text-on-surface-variant mt-xs">
                            The generated report did not include any findings.
                        </p>
                    </div>
                </div>
            </div>
        `;
        return;
    }

    list.innerHTML = findings
        .map((finding, index) => {
            const score = findMatchingCvssScore(
                finding,
                cvssScores,
                index
            );

            const severity = score
                ? String(score.severity || "INFORMATIONAL").toUpperCase()
                : "INFORMATIONAL";

            const baseScore = score
                ? Number(score.base_score || 0).toFixed(1)
                : null;

            const severityStyle =
                getSeverityStyle(severity);

            return `
                <article
                    class="finding-card bg-surface border border-border rounded-xl p-md"
                >
                    <div class="flex flex-col md:flex-row gap-md">
                        <div
                            class="w-12 h-12 rounded-lg ${
                                severityStyle.iconBackground
                            } flex items-center justify-center ${
                                severityStyle.text
                            } shrink-0"
                        >
                            <span
                                class="material-symbols-outlined"
                                style="font-variation-settings: 'FILL' 1;"
                            >
                                ${severityStyle.icon}
                            </span>
                        </div>

                        <div class="flex-grow">
                            <div
                                class="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-xs"
                            >
                                <div>
                                    <p
                                        class="text-label-sm text-on-surface-variant uppercase tracking-wider"
                                    >
                                        ${escapeHtml(
                                            formatWorkerName(
                                                finding.worker
                                            )
                                        )}
                                    </p>

                                    <h3
                                        class="text-headline-sm font-headline-sm text-on-surface mt-1"
                                    >
                                        ${escapeHtml(
                                            getFindingTitle(
                                                finding,
                                                index
                                            )
                                        )}
                                    </h3>
                                </div>

                                <span
                                    class="${
                                        severityStyle.badge
                                    } text-label-sm font-label-sm px-sm py-1 rounded-full uppercase self-start"
                                >
                                    ${escapeHtml(severity)}
                                    ${
                                        baseScore !== null
                                            ? ` ${baseScore}`
                                            : ""
                                    }
                                </span>
                            </div>

                            <p
                                class="text-body-sm text-on-surface-variant mt-sm"
                            >
                                ${escapeHtml(
                                    finding.summary ||
                                    "No summary was provided."
                                )}
                            </p>
                        </div>
                    </div>
                </article>
            `;
        })
        .join("");
}


function findMatchingCvssScore(
    finding,
    cvssScores,
    index
) {
    if (!cvssScores.length) {
        return null;
    }

    const summary = String(
        finding.summary || ""
    ).toLowerCase();

    const directMatch = cvssScores.find((score) => {
        const scoredFinding = String(
            score.finding || ""
        ).toLowerCase();

        return (
            scoredFinding &&
            summary &&
            (
                summary.includes(scoredFinding) ||
                scoredFinding.includes(summary)
            )
        );
    });

    return directMatch || cvssScores[index] || null;
}


function getFindingTitle(finding, index) {
    if (finding.title) {
        return finding.title;
    }

    if (finding.finding) {
        return finding.finding;
    }

    return `${formatWorkerName(
        finding.worker
    )} Finding ${index + 1}`;
}


function renderCvssScores(cvssScores) {
    const list = document.getElementById("cvssList");

    if (!cvssScores.length) {
        list.innerHTML = `
            <div class="bg-surface border border-border rounded-xl p-md">
                <p class="text-body-sm text-on-surface-variant">
                    No CVSS-scored findings were included in this report.
                </p>
            </div>
        `;
        return;
    }

    list.innerHTML = cvssScores
        .map((score, index) => {
            const severity = String(
                score.severity || "INFORMATIONAL"
            ).toUpperCase();

            const style = getSeverityStyle(severity);
            const baseScore = Number(
                score.base_score || 0
            ).toFixed(1);

            return `
                <article
                    class="bg-surface border border-border rounded-xl p-md"
                >
                    <div
                        class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-md"
                    >
                        <div class="flex-grow">
                            <div class="flex items-center gap-sm">
                                <span
                                    class="${
                                        style.badge
                                    } text-label-sm font-label-sm px-sm py-1 rounded-full uppercase"
                                >
                                    ${escapeHtml(severity)}
                                </span>

                                <span
                                    class="text-headline-sm font-headline-sm ${
                                        style.text
                                    }"
                                >
                                    ${baseScore}
                                </span>
                            </div>

                            <h3
                                class="text-body-lg font-semibold text-on-surface mt-sm"
                            >
                                ${escapeHtml(
                                    score.finding ||
                                    `Scored Finding ${index + 1}`
                                )}
                            </h3>

                            <p
                                class="font-mono-md text-body-sm text-primary mt-xs break-all"
                            >
                                ${escapeHtml(
                                    score.vector ||
                                    "CVSS vector unavailable"
                                )}
                            </p>
                        </div>

                        <div
                            class="w-full lg:w-40 bg-surface-variant h-3 rounded-full overflow-hidden"
                        >
                            <div
                                class="${
                                    style.bar
                                } h-full rounded-full"
                                style="width: ${
                                    Number(score.base_score || 0) * 10
                                }%"
                            ></div>
                        </div>
                    </div>
                </article>
            `;
        })
        .join("");
}


function renderWorkerFindings(findings) {
    const container = document.getElementById(
        "workerFindings"
    );

    if (!findings.length) {
        container.innerHTML = `
            <div class="bg-surface border border-border rounded-xl p-md">
                <p class="text-body-sm text-on-surface-variant">
                    No worker findings were included.
                </p>
            </div>
        `;
        return;
    }

    container.innerHTML = findings
        .map((finding) => {
            const rawData = finding.raw_data;

            return `
                <article
                    class="bg-surface border border-border rounded-xl p-md"
                >
                    <div class="flex items-center gap-sm mb-sm">
                        <div
                            class="w-10 h-10 rounded-lg bg-primary-fixed text-primary flex items-center justify-center"
                        >
                            <span class="material-symbols-outlined">
                                ${getWorkerIcon(finding.worker)}
                            </span>
                        </div>

                        <div>
                            <p
                                class="text-label-sm text-on-surface-variant uppercase"
                            >
                                Worker
                            </p>

                            <h3
                                class="text-body-lg font-semibold"
                            >
                                ${escapeHtml(
                                    formatWorkerName(
                                        finding.worker
                                    )
                                )}
                            </h3>
                        </div>
                    </div>

                    <p
                        class="text-body-sm text-on-surface-variant mb-sm"
                    >
                        ${escapeHtml(
                            finding.summary ||
                            "No worker summary was provided."
                        )}
                    </p>

                    <details>
                        <summary
                            class="cursor-pointer text-label-md font-label-md text-primary"
                        >
                            View raw output
                        </summary>

                        <pre
                            class="mt-sm bg-inverse-surface text-surface-bright/80 rounded-lg p-sm overflow-auto max-h-72 font-mono-md text-body-sm"
                        >${escapeHtml(
                            stringifyValue(rawData)
                        )}</pre>
                    </details>
                </article>
            `;
        })
        .join("");
}


function renderRecommendations(findings, cvssScores) {
    const container = document.getElementById(
        "recommendationsList"
    );

    const recommendations = buildRecommendations(
        findings,
        cvssScores
    );

    if (!recommendations.length) {
        container.innerHTML = `
            <div
                class="bg-on-surface-variant/10 border border-outline/30 p-md rounded-lg"
            >
                <p class="text-body-sm text-surface-variant">
                    No specific recommendations were generated.
                </p>
            </div>
        `;
        return;
    }

    container.innerHTML = recommendations
        .map((recommendation, index) => {
            return `
                <article
                    class="bg-on-surface-variant/10 border border-outline/30 p-md rounded-lg"
                >
                    <div
                        class="flex items-center gap-sm text-inverse-on-surface font-label-md mb-xs"
                    >
                        <span
                            class="text-sm bg-primary/20 text-primary-fixed-dim px-2 py-0.5 rounded"
                        >
                            STEP ${index + 1}
                        </span>

                        ${escapeHtml(recommendation.title)}
                    </div>

                    <p class="text-body-sm text-surface-variant">
                        ${escapeHtml(recommendation.description)}
                    </p>
                </article>
            `;
        })
        .join("");
}


function buildRecommendations(findings, cvssScores) {
    const recommendations = [];
    const workers = new Set(
        findings
            .map((finding) => finding.worker)
            .filter(Boolean)
    );

    if (workers.has("http_headers")) {
        recommendations.push({
            title: "Review Security Headers",
            description:
                "Review the HTTP header findings and configure missing " +
                "security headers where appropriate for the application.",
        });
    }

    if (workers.has("ssl_check")) {
        recommendations.push({
            title: "Review TLS Configuration",
            description:
                "Validate certificate expiry, trust, protocol selection, " +
                "and cipher configuration against your deployment policy.",
        });
    }

    if (workers.has("cookie_analysis")) {
        recommendations.push({
            title: "Harden Cookie Attributes",
            description:
                "Ensure sensitive cookies use Secure and HttpOnly attributes " +
                "and apply an appropriate SameSite policy.",
        });
    }

    if (workers.has("port_scan")) {
        recommendations.push({
            title: "Reduce Exposed Services",
            description:
                "Confirm every discovered open port is required and restrict " +
                "unnecessary services using network controls.",
        });
    }

    if (
        workers.has("robots_txt_parse") ||
        workers.has("sitemap_parse")
    ) {
        recommendations.push({
            title: "Review Publicly Listed Paths",
            description:
                "Review paths exposed through robots.txt and sitemap files " +
                "and avoid relying on these files as access controls.",
        });
    }

    const highRiskScores = cvssScores.filter((score) => {
        return Number(score.base_score || 0) >= 7;
    });

    if (highRiskScores.length) {
        recommendations.unshift({
            title: "Prioritize High-Risk Findings",
            description:
                `Validate and remediate the ${highRiskScores.length} ` +
                `finding${highRiskScores.length === 1 ? "" : "s"} with ` +
                "CVSS scores of 7.0 or higher before lower-priority items.",
        });
    }

    if (!recommendations.length && findings.length) {
        recommendations.push({
            title: "Review Worker Findings",
            description:
                "Validate each finding against the target's intended " +
                "configuration and document accepted risks or remediation.",
        });
    }

    return recommendations.slice(0, 6);
}


function configureDownloadButtons(scanId) {
    const pdfButton = document.getElementById(
        "downloadPdfButton"
    );
    const jsonButton = document.getElementById(
        "downloadJsonButton"
    );

    pdfButton.disabled = false;
    jsonButton.disabled = false;

    pdfButton.addEventListener("click", () => {
        window.location.href =
            `${API_BASE_URL}/reports/${encodeURIComponent(
                scanId
            )}/pdf`;
    });

    jsonButton.addEventListener("click", () => {
        window.location.href =
            `${API_BASE_URL}/reports/${encodeURIComponent(
                scanId
            )}/json`;
    });
}


function renderRawJson(report) {
    document.getElementById(
        "rawJsonContent"
    ).textContent = JSON.stringify(report, null, 2);
}


function getSeverityStyle(severity) {
    const styles = {
        CRITICAL: {
            badge: "bg-critical text-white",
            text: "text-critical",
            bar: "bg-critical",
            iconBackground: "bg-error-container",
            icon: "dangerous",
        },

        HIGH: {
            badge: "bg-error text-white",
            text: "text-error",
            bar: "bg-error",
            iconBackground: "bg-error-container",
            icon: "error",
        },

        MEDIUM: {
            badge: "bg-warning text-on-surface",
            text: "text-warning",
            bar: "bg-warning",
            iconBackground: "bg-warning/10",
            icon: "warning",
        },

        LOW: {
            badge: "bg-primary text-white",
            text: "text-primary",
            bar: "bg-primary",
            iconBackground: "bg-primary-fixed",
            icon: "info",
        },

        INFORMATIONAL: {
            badge:
                "bg-surface-variant text-on-surface-variant",
            text: "text-on-surface-variant",
            bar: "bg-on-surface-variant",
            iconBackground: "bg-surface-variant",
            icon: "info",
        },

        NONE: {
            badge: "bg-success/10 text-success",
            text: "text-success",
            bar: "bg-success",
            iconBackground: "bg-success/10",
            icon: "check_circle",
        },
    };

    return styles[severity] || styles.INFORMATIONAL;
}


function formatWorkerName(workerName) {
    if (!workerName) {
        return "Unknown Worker";
    }

    const aliases = {
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
        String(workerName)
            .replaceAll("_", " ")
            .replace(/\b\w/g, (character) =>
                character.toUpperCase()
            )
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
        generate_report: "description",
    };

    return icons[workerName] || "security";
}


function formatStatus(status) {
    if (!status) {
        return "Unknown";
    }

    return String(status)
        .replaceAll("_", " ")
        .toLowerCase()
        .replace(/\b\w/g, (character) =>
            character.toUpperCase()
        );
}


function formatDate(value) {
    if (!value) {
        return "Unavailable";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return String(value);
    }

    return date.toLocaleString();
}


function stringifyValue(value) {
    if (value === undefined) {
        return "No raw data was provided.";
    }

    if (typeof value === "string") {
        return value;
    }

    try {
        return JSON.stringify(value, null, 2);
    } catch {
        return String(value);
    }
}


function showLoading() {
    document
        .getElementById("reportLoading")
        .classList.remove("hidden");
}


function hideLoading() {
    document
        .getElementById("reportLoading")
        .classList.add("hidden");
}


function showError(message) {
    const errorBox = document.getElementById("reportError");

    errorBox.textContent = message;
    errorBox.classList.remove("hidden");
}


function clearError() {
    const errorBox = document.getElementById("reportError");

    errorBox.textContent = "";
    errorBox.classList.add("hidden");
}


function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}
