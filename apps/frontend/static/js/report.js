"use strict";

const API_BASE_URL = "/api/v1";

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
    
    // Check if we are viewing a historical scan
    const historyId = queryParams.get("history_id");
    if (historyId) {
        return historyId;
    }

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

    if (newScanButton) {
        newScanButton.addEventListener("click", () => {
            window.location.href = "/";
        });
    }

    if (backToDashboardButton) {
        backToDashboardButton.addEventListener("click", () => {
            if (!activeScanId) {
                window.location.href = "/dashboard";
                return;
            }

            window.location.href =
                `/dashboard?scan_id=${encodeURIComponent(activeScanId)}`;
        });
    }
}


function bindRawJsonToggle() {
    const toggleButton = document.getElementById(
        "toggleRawJsonButton"
    );
    const rawJsonPanel = document.getElementById("rawJsonPanel");
    const toggleIcon = document.getElementById(
        "rawJsonToggleIcon"
    );

    if (!toggleButton || !rawJsonPanel || !toggleIcon) {
        return;
    }

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
        const queryParams = new URLSearchParams(window.location.search);
        
        if (queryParams.has("history_id")) {
            // Load historical report from session storage (populated by auth.js)
            const historicalDataStr = sessionStorage.getItem("sentinelscan_historical_report");
            
            if (!historicalDataStr) {
                throw new Error("Historical report data not found. Please open this report from the dashboard history tab.");
            }
            
            activeScan = JSON.parse(historicalDataStr);
            activeReport = activeScan.report_data || {};
            
            if (!activeReport || Object.keys(activeReport).length === 0) {
                 throw new Error("This historical scan does not contain a JSON report payload.");
            }
        } else {
            // Load active runtime scan from API
            activeScan = await fetchScan(activeScanId);

            if (activeScan.status !== "COMPLETED") {
                if (activeScan.status === "FAILED") {
                    throw new Error(
                        activeScan.error ||
                        "The assessment failed before a report was generated."
                    );
                }

                throw new Error(
                    "The assessment is not complete yet. Return to the dashboard and wait for completion."
                );
            }

            activeReport = await fetchJsonReport(activeScanId);
        }

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

    let payload;

    try {
        payload = await response.json();
    } catch {
        throw new Error(
            "The scan status endpoint returned an invalid response."
        );
    }

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

    const contentType =
        response.headers.get("Content-Type") || "";

    if (!contentType.includes("application/json")) {
        throw new Error(
            "The report endpoint did not return a valid JSON document."
        );
    }

    return response.json();
}


function renderScanMetadata(scan) {
    setText(
        "reportTarget",
        scan.target || "Unknown target"
    );

    setText(
        "reportScanId",
        scan.scan_id || activeScanId
    );

    setText(
        "reportCompletedAt",
        formatDate(scan.completed_at)
    );

    setText(
        "reportStatus",
        formatStatus(scan.status)
    );

    setText(
        "reportIdLabel",
        `REPORT_ID: ${scan.scan_id || activeScanId}`
    );
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

    const maximumCvss = Number.isFinite(Number(report.maximum_cvss))
        && Number(report.maximum_cvss) > 0
        ? Number(report.maximum_cvss)
        : getMaximumCvss(cvssScores);

    const securityScore = Number.isFinite(Number(report.security_score))
        ? Number(report.security_score)
        : calculateSecurityScore(maximumCvss, cvssScores);

    renderSecurityScore(securityScore, maximumCvss);
    renderMaximumCvss(maximumCvss, cvssScores);
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
    if (!Array.isArray(cvssScores) || !cvssScores.length) {
        return null;
    }

    const positiveScores = cvssScores
        .map((item) => Number(item.base_score ?? item.score))
        .filter((score) => Number.isFinite(score) && score > 0 && score <= 10);

    return positiveScores.length ? Math.max(...positiveScores) : null;
}


function calculateSecurityScore(maximumCvss, cvssScores) {
    /*
     * SentinelScan display mapping. CVSS itself remains 0.0-10.0;
     * this 0-100 value is a separate project posture gauge.
     *
     * CRITICAL 9.0-10.0 -> 10-0
     * HIGH     7.0-8.9  -> 30-10
     * MEDIUM   4.0-6.9  -> 60-30
     * LOW      0.1-3.9  -> 80-60
     * NONE/N/A 0.0/N/A  -> 100
     */
    if (maximumCvss === null || !Number.isFinite(Number(maximumCvss))) {
        return 100;
    }

    const cvss = Math.max(0, Math.min(10, Number(maximumCvss)));
    if (cvss <= 0) {
        return 100;
    }

    let score;

    if (cvss <= 3.9) {
        score = 80 - ((cvss - 0.1) / 3.8) * 20;
    } else if (cvss <= 6.9) {
        score = 60 - ((cvss - 4.0) / 2.9) * 30;
    } else if (cvss <= 8.9) {
        score = 30 - ((cvss - 7.0) / 1.9) * 20;
    } else {
        score = 10 - ((cvss - 9.0) / 1.0) * 10;
    }

    return Math.round(Math.max(0, Math.min(100, score)));
}


function renderSecurityScore(score, maximumCvss = null) {
    const gauge = document.getElementById("securityGauge");
    const scoreElement = document.getElementById(
        "securityScore"
    );
    const riskLabel = document.getElementById("riskLabel");

    if (!gauge || !scoreElement || !riskLabel) {
        return;
    }

    const radius = 88;
    const circumference = 2 * Math.PI * radius;

    gauge.style.strokeDasharray = String(circumference);

    const safeScore = Number.isFinite(Number(score))
        ? Math.max(0, Math.min(100, Number(score)))
        : 100;

    const offset =
        circumference - (safeScore / 100) * circumference;

    gauge.style.strokeDashoffset = String(offset);
    scoreElement.textContent = String(Math.round(safeScore));

    const rating = getSecurityRating(maximumCvss);

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

    const mappingLabel = document.getElementById("scoreMappingLabel");
    if (mappingLabel) {
        const cvssText = maximumCvss === null || !Number.isFinite(Number(maximumCvss)) || Number(maximumCvss) <= 0
            ? "CVSS 0.0 NONE"
            : `CVSS ${Number(maximumCvss).toFixed(1)} ${getCvssSeverity(Number(maximumCvss))}`;
        mappingLabel.textContent = `${cvssText} → ${Math.round(safeScore)}/100`;
    }
}


function getSecurityRating(maximumCvss) {
    if (maximumCvss === null || !Number.isFinite(Number(maximumCvss)) || Number(maximumCvss) <= 0) {
        return {
            label: "Strong Observed Posture",
            icon: "verified_user",
            textClass: "text-success",
            gaugeClass: "text-success",
        };
    }

    const cvss = Number(maximumCvss);

    if (cvss >= 9.0) {
        return {
            label: "Critical Observed Risk",
            icon: "dangerous",
            textClass: "text-critical",
            gaugeClass: "text-critical",
        };
    }

    if (cvss >= 7.0) {
        return {
            label: "High Observed Risk",
            icon: "error",
            textClass: "text-error",
            gaugeClass: "text-error",
        };
    }

    if (cvss >= 4.0) {
        return {
            label: "Medium Observed Risk",
            icon: "warning",
            textClass: "text-warning",
            gaugeClass: "text-warning",
        };
    }

    return {
        label: "Low Observed Risk",
        icon: "info",
        textClass: "text-primary",
        gaugeClass: "text-primary",
    };
}


function getCvssSeverity(score) {
    if (!Number.isFinite(Number(score)) || Number(score) <= 0) {
        return "NONE";
    }

    const numeric = Number(score);
    if (numeric >= 9.0) return "CRITICAL";
    if (numeric >= 7.0) return "HIGH";
    if (numeric >= 4.0) return "MEDIUM";
    return "LOW";
}


function renderMaximumCvss(maximumCvss, cvssScores) {
    const element = document.getElementById("maxCvssScore");
    const severityElement = document.getElementById("maxCvssSeverity");
    const card = document.getElementById("maxCvssCard");

    if (!element) {
        return;
    }

    const hasScore =
        Array.isArray(cvssScores) &&
        cvssScores.length > 0 &&
        maximumCvss !== null &&
        Number.isFinite(Number(maximumCvss)) &&
        Number(maximumCvss) > 0;

    const severity = hasScore
        ? getCvssSeverity(Number(maximumCvss))
        : "NONE";

    element.textContent = hasScore
        ? Number(maximumCvss).toFixed(1)
        : "0.0";

    if (severityElement) {
        severityElement.textContent = severity;
    }

    if (card) {
        const palette = {
            CRITICAL: { background: "#fee2e2", color: "#991b1b" },
            HIGH: { background: "#fee2e2", color: "#b91c1c" },
            MEDIUM: { background: "#fef3c7", color: "#92400e" },
            LOW: { background: "#dbeafe", color: "#1d4ed8" },
            NONE: { background: "#dcfce7", color: "#166534" },
        };
        const selected = palette[severity] || palette.NONE;
        card.style.backgroundColor = selected.background;
        card.style.color = selected.color;
    }
}


function renderRiskSummary(summary) {
    setText("criticalCount", summary.CRITICAL);
    setText("highCount", summary.HIGH);
    setText("mediumCount", summary.MEDIUM);
    setText("lowCount", summary.LOW);
    setText(
        "informationalCount",
        summary.INFORMATIONAL
    );
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
            `generated report. This does not prove that the target is ` +
            `fully secure. Review the raw worker output and confirm that ` +
            `all expected assessment steps completed successfully.`;
    } else {
        summary =
            `SentinelScan completed an AI-guided assessment of ${target}. ` +
            `${findings.length} finding${findings.length === 1 ? "" : "s"} ` +
            `were compiled from ${workerCount} worker` +
            `${workerCount === 1 ? "" : "s"}. `;

        if (
            cvssScores.length &&
            maximumCvss !== null
        ) {
            summary +=
                `The highest calculated CVSS v3.1 base score was ` +
                `${maximumCvss.toFixed(1)}. `;
        } else {
            summary +=
                "No actionable CVSS-scored finding was retained. The maximum " +
                "CVSS is N/A and the project posture gauge displays 100/100. ";
        }

        summary +=
            "Review each finding, verify it manually, and validate the " +
            "recommended actions before making production changes.";
    }

    setText("executiveSummary", summary);
}


function renderFindings(findings, cvssScores) {
    const list = document.getElementById("findingsList");
    const count = document.getElementById("findingsCount");

    if (!list || !count) {
        return;
    }

    count.textContent =
        `${findings.length} Finding` +
        `${findings.length === 1 ? "" : "s"}`;

    if (!findings.length) {
        list.innerHTML = `
            <div class="bg-surface border border-border rounded-xl p-md">
                <div class="flex items-start gap-sm">
                    <span class="material-symbols-outlined text-on-surface-variant">
                        info
                    </span>

                    <div>
                        <h3 class="text-body-lg font-semibold">
                            No reportable findings
                        </h3>

                        <p class="text-body-sm text-on-surface-variant mt-xs">
                            The generated report did not include any findings.
                            This does not guarantee that the target is secure.
                        </p>
                    </div>
                </div>
            </div>
        `;
        return;
    }

    list.innerHTML = findings
        .map((finding, index) => {
            const findingSeverity = String(
                finding.severity || "INFORMATIONAL"
            ).toUpperCase();

            const score = findingSeverity === "INFORMATIONAL"
                ? null
                : findMatchingCvssScore(finding, cvssScores);

            const severity = score
                ? String(score.severity || findingSeverity).toUpperCase()
                : findingSeverity;

            const baseScore = score &&
                Number.isFinite(Number(score.base_score ?? score.score))
                ? Number(score.base_score ?? score.score).toFixed(1)
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

                        <div class="flex-grow min-w-0">
                            <div
                                class="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-xs"
                            >
                                <div class="min-w-0">
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
                                        class="text-headline-sm font-headline-sm text-on-surface mt-1 break-words"
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
                                    } text-label-sm font-label-sm px-sm py-1 rounded-full uppercase self-start whitespace-nowrap"
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
                                class="text-body-sm text-on-surface-variant mt-sm break-words"
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


function findMatchingCvssScore(finding, cvssScores) {
    if (!Array.isArray(cvssScores) || !cvssScores.length) {
        return null;
    }

    const normalize = (value) => String(value || "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, " ")
        .trim();

    const candidates = [
        finding.finding,
        finding.title,
        finding.summary,
    ].map(normalize).filter(Boolean);

    return cvssScores.find((score) => {
        const scoredFinding = normalize(score.finding);
        if (!scoredFinding) {
            return false;
        }

        return candidates.some((candidate) =>
            candidate === scoredFinding ||
            (scoredFinding.length >= 8 &&
                (candidate.includes(scoredFinding) || scoredFinding.includes(candidate)))
        );
    }) || null;
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

    if (!list) {
        return;
    }

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

            const numericScore =
                Number(score.base_score ?? score.score);

            const baseScore =
                Number.isFinite(numericScore)
                    ? numericScore.toFixed(1)
                    : "N/A";

            const scoreWidth =
                Number.isFinite(numericScore)
                    ? Math.max(
                        0,
                        Math.min(100, numericScore * 10)
                    )
                    : 0;

            return `
                <article
                    class="bg-surface border border-border rounded-xl p-md"
                >
                    <div
                        class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-md"
                    >
                        <div class="flex-grow min-w-0">
                            <div class="flex items-center gap-sm flex-wrap">
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
                                class="text-body-lg font-semibold text-on-surface mt-sm break-words"
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
                                style="width: ${scoreWidth}%"
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

    if (!container) {
        return;
    }

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
            const rawData = finding.evidence || finding.raw_data;

            return `
                <article
                    class="bg-surface border border-border rounded-xl p-md min-w-0"
                >
                    <div class="flex items-center gap-sm mb-sm">
                        <div
                            class="w-10 h-10 rounded-lg bg-primary-fixed text-primary flex items-center justify-center shrink-0"
                        >
                            <span class="material-symbols-outlined">
                                ${getWorkerIcon(finding.worker)}
                            </span>
                        </div>

                        <div class="min-w-0">
                            <p
                                class="text-label-sm text-on-surface-variant uppercase"
                            >
                                Worker
                            </p>

                            <h3
                                class="text-body-lg font-semibold break-words"
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
                        class="text-body-sm text-on-surface-variant mb-sm break-words"
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
                            class="mt-sm bg-inverse-surface text-surface-bright/80 rounded-lg p-sm overflow-auto max-h-72 font-mono-md text-body-sm whitespace-pre-wrap break-words"
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

    if (!container) {
        return;
    }

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
                            class="text-sm bg-primary/20 text-primary-fixed-dim px-2 py-0.5 rounded whitespace-nowrap"
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

    if (workers.has("dns_lookup")) {
        recommendations.push({
            title: "Review DNS Configuration",
            description:
                "Review DNS records for outdated, unnecessary, or incorrectly " +
                "configured entries and confirm mail-security records are suitable.",
        });
    }

    const highRiskScores = cvssScores.filter((score) => {
        return Number(score.base_score ?? score.score ?? 0) >= 7;
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

    if (!pdfButton || !jsonButton) {
        return;
    }

    pdfButton.disabled = false;
    jsonButton.disabled = false;

    pdfButton.addEventListener("click", async () => {
        await downloadReport(
            `${API_BASE_URL}/reports/${encodeURIComponent(scanId)}/pdf`,
            `sentinelscan-${scanId}.pdf`,
            "application/pdf",
            pdfButton
        );
    });

    jsonButton.addEventListener("click", async () => {
        await downloadReport(
            `${API_BASE_URL}/reports/${encodeURIComponent(scanId)}/json`,
            `sentinelscan-${scanId}.json`,
            "application/json",
            jsonButton
        );
    });
}


async function downloadReport(
    url,
    filename,
    expectedContentType,
    button
) {
    clearError();

    const originalText = button.innerHTML;

    button.disabled = true;

    button.innerHTML = `
        <span class="material-symbols-outlined animate-spin">
            progress_activity
        </span>
        Preparing...
    `;

    try {
        const headers = {};
        
        try {
            const { getAuth } = await import("https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js");
            const { initializeApp, getApps } = await import("https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js");
            
            if (getApps().length === 0) {
                initializeApp({
                    apiKey: "AIzaSyBvWgaqLbG9la-77P__L5WACBQ4t3kkCFU",
                    authDomain: "sentinelscan-3f82d.firebaseapp.com",
                    projectId: "sentinelscan-3f82d",
                    storageBucket: "sentinelscan-3f82d.firebasestorage.app",
                    messagingSenderId: "60214574079",
                    appId: "1:60214574079:web:5c6e5cd5004ffe6902c5ca"
                });
            }
            
            const auth = getAuth();
            const user = await new Promise(resolve => {
                const unsubscribe = auth.onAuthStateChanged(u => {
                    unsubscribe();
                    resolve(u);
                });
            });
            
            if (user) {
                const token = await user.getIdToken();
                headers["Authorization"] = `Bearer ${token}`;
            }
        } catch (authError) {
            console.warn("Could not retrieve auth token for download:", authError);
            // Gracefully proceed without token (e.g. unauthenticated context)
        }

        const response = await fetch(url, { headers });

        if (!response.ok) {
            let message = "Report download failed.";

            try {
                const errorPayload = await response.json();

                message =
                    errorPayload.message ||
                    errorPayload.error ||
                    message;
            } catch {
                // Response was not JSON.
            }

            throw new Error(message);
        }

        const contentType =
            response.headers.get("Content-Type") || "";

        if (!contentType.includes(expectedContentType)) {
            throw new Error(
                `The server returned ${contentType || "an unknown format"} ` +
                `instead of ${expectedContentType}.`
            );
        }

        const blob = await response.blob();

        if (blob.size === 0) {
            throw new Error(
                "The downloaded report file was empty."
            );
        }

        const objectUrl = URL.createObjectURL(blob);
        const anchor = document.createElement("a");

        anchor.href = objectUrl;
        anchor.download = filename;
        anchor.style.display = "none";

        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();

        window.setTimeout(() => {
            URL.revokeObjectURL(objectUrl);
        }, 1000);
    } catch (error) {
        showError(
            error.message ||
            "Unable to download the report."
        );
    } finally {
        button.disabled = false;
        button.innerHTML = originalText;
    }
}


function renderRawJson(report) {
    const rawJsonContent = document.getElementById(
        "rawJsonContent"
    );

    if (!rawJsonContent) {
        return;
    }

    rawJsonContent.textContent =
        JSON.stringify(report, null, 2);
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
        ddos_resilience_check: "Passive DDoS Resilience",
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
        ddos_resilience_check: "shield",
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
    if (value === undefined || value === null) {
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
    const loading = document.getElementById(
        "reportLoading"
    );

    if (loading) {
        loading.classList.remove("hidden");
    }
}


function hideLoading() {
    const loading = document.getElementById(
        "reportLoading"
    );

    if (loading) {
        loading.classList.add("hidden");
    }
}


function showError(message) {
    const errorBox = document.getElementById("reportError");

    if (!errorBox) {
        console.error(message);
        return;
    }

    errorBox.textContent = message;
    errorBox.classList.remove("hidden");

    errorBox.scrollIntoView({
        behavior: "smooth",
        block: "center",
    });
}


function clearError() {
    const errorBox = document.getElementById("reportError");

    if (!errorBox) {
        return;
    }

    errorBox.textContent = "";
    errorBox.classList.add("hidden");
}


function setText(elementId, value) {
    const element = document.getElementById(elementId);

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


