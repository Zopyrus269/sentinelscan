"use strict";

const API_BASE_URL = "/api/v1";

let activeScanId = null;
let activeScan = null;
let activeReport = null;

document.addEventListener("DOMContentLoaded", () => {
    activeScanId = getScanId();

    bindNavigation();

    if (!activeScanId) {
        hideLoading();
        dispatchNoScanIdNotice(
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


// Handed to the React-owned SpecularButton notice (see ReportBento.jsx's
// ReportNoScanNotice) instead of the plain #reportError box -- these are
// the specific "there's nothing to load, and it's not worth pretending
// otherwise" cases (no scan_id in the URL at all, or historical report data
// missing) that get that treatment; every other error path below (a fetch
// that fails partway through, an incomplete/failed scan) still uses
// showError(). href is where the button's click sends the visitor --
// defaults to the landing page (the "no scan ID" case's own destination).
function dispatchNoScanIdNotice(message, href = "/") {
    window.dispatchEvent(
        new CustomEvent("sentinelscan:no-scan-id", { detail: { message, href } })
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


async function loadReport() {
    showLoading();
    clearError();

    try {
        const queryParams = new URLSearchParams(window.location.search);
        
        if (queryParams.has("history_id")) {
            // View Report (auth.js's viewReport()) stores this in
            // localStorage, not sessionStorage -- it's opened via
            // window.open() into a brand new tab, which gets its own fresh
            // sessionStorage with nothing in it; localStorage is what's
            // actually shared across tabs on the same origin. Keyed per
            // scan_id (matching what auth.js writes) so multiple historical
            // report tabs opened one after another don't clobber each
            // other's data before each one gets a chance to read it.
            const historicalDataKey = `sentinelscan_historical_report_${activeScanId}`;
            const historicalDataStr = localStorage.getItem(historicalDataKey);

            if (!historicalDataStr) {
                hideLoading();
                dispatchNoScanIdNotice(
                    "Historical report data not found. Please open this report from the dashboard history tab.",
                    "/dashboard"
                );
                return;
            }

            activeScan = JSON.parse(historicalDataStr);
            activeReport = activeScan.report_data || {};
            // One-shot handoff from the History tab -- read once, then
            // cleared, rather than left to accumulate in localStorage
            // (potentially one entry per historical scan ever viewed).
            localStorage.removeItem(historicalDataKey);

            if (!activeReport || Object.keys(activeReport).length === 0) {
                hideLoading();
                dispatchNoScanIdNotice(
                    "This historical scan does not contain a JSON report payload.",
                    "/dashboard"
                );
                return;
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

        // fetchScan()'s 404 ("The requested scan_id does not exist.") --
        // typically a stale sessionStorage scan_id left over from before a
        // backend restart, since scan state is in-memory only -- gets the
        // same SpecularButton notice as "no scan ID at all" rather than the
        // plain #reportError box; every other failure here (fetch errors,
        // an incomplete/failed scan) still uses that box.
        if (error.status === 404) {
            dispatchNoScanIdNotice(
                error.message || "The requested scan_id does not exist.",
                "/"
            );
            return;
        }

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
        const error = new Error(
            payload.message ||
            payload.error ||
            "Unable to retrieve the scan."
        );
        // Read by loadReport()'s catch to tell "this scan_id doesn't exist"
        // (backend 404, e.g. a stale sessionStorage scan_id from before a
        // backend restart -- scan state is in-memory only) apart from every
        // other fetch failure, so only that specific case gets routed to
        // the SpecularButton notice instead of the plain #reportError box.
        error.status = response.status;
        throw error;
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

    // Dispatched first and defensively -- this used to run last, so any
    // exception thrown by an earlier render*() call (a shape the report
    // data didn't anticipate, etc.) meant it never ran at all, leaving the
    // scroll-reveal paragraphs stuck on their "this section is loading"
    // placeholder forever with no visible error anywhere else on the page.
    dispatchReportCrawl(report, findings, cvssScores, maximumCvss, riskSummary);

    renderSecurityScore(securityScore, maximumCvss);
    renderMaximumCvss(maximumCvss, cvssScores);
    renderRiskSummary(riskSummary);
    renderExecutiveSummary(
        report,
        findings,
        cvssScores,
        maximumCvss,
        securityScore,
        riskSummary
    );
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
    const riskLabel = document.getElementById("riskLabel");

    if (!gauge || !riskLabel) {
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

    // The score itself is rendered by a React-owned CountUp component
    // (see ReportBento.jsx) which animates 0 -> safeScore rather than a
    // plain textContent snap -- this dispatches the value for it to pick
    // up instead of writing into a "securityScore" element directly.
    window.dispatchEvent(
        new CustomEvent("sentinelscan:security-score-update", {
            detail: { score: Math.round(safeScore) },
        })
    );

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
    const severityElement = document.getElementById("maxCvssSeverity");

    const hasScore =
        Array.isArray(cvssScores) &&
        cvssScores.length > 0 &&
        maximumCvss !== null &&
        Number.isFinite(Number(maximumCvss)) &&
        Number(maximumCvss) > 0;

    const severity = hasScore
        ? getCvssSeverity(Number(maximumCvss))
        : "NONE";

    // The value itself is rendered by a React-owned CountUp component
    // (see ReportBento.jsx) instead of a "maxCvssScore" element this
    // script writes textContent into directly -- it also owns the card's
    // fixed dark styling now (no more per-severity background swap), so
    // this only dispatches the value/severity for it to pick up.
    window.dispatchEvent(
        new CustomEvent("sentinelscan:max-cvss-update", {
            detail: {
                value: hasScore ? Number(maximumCvss) : 0,
                hasScore,
            },
        })
    );

    if (severityElement) {
        severityElement.textContent = severity;
    }
}


function renderRiskSummary(summary) {
    // Each count is rendered by a React-owned CountUp component (see
    // ReportBento.jsx) that animates 0 -> count -- e.g. 5 critical findings
    // counts up from 0 to 5 -- rather than a plain textContent snap, so
    // this dispatches the numbers instead of writing into
    // "criticalCount"/"highCount"/etc. elements directly.
    window.dispatchEvent(
        new CustomEvent("sentinelscan:risk-summary-update", {
            detail: {
                critical: Number(summary.CRITICAL) || 0,
                high: Number(summary.HIGH) || 0,
                medium: Number(summary.MEDIUM) || 0,
                low: Number(summary.LOW) || 0,
                informational: Number(summary.INFORMATIONAL) || 0,
            },
        })
    );
}


function renderExecutiveSummary(
    report,
    findings,
    cvssScores,
    maximumCvss,
    securityScore,
    riskSummary
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

    const safeScore = Number.isFinite(Number(securityScore))
        ? Math.round(Number(securityScore))
        : 100;

    const hasCvss = cvssScores.length && maximumCvss !== null;

    // The score itself (see renderSecurityScore/calculateSecurityScore) is
    // never hardcoded to 100 just because there's no CVSS-scored finding --
    // the backend's report_worker.py falls back to an 80-100 "informational
    // posture score" derived from other observed hardening signals (SSL
    // config, headers, cookies, etc.) in that case, which can legitimately
    // land below 100 (e.g. 88). The summary text used to always claim
    // "100/100" whenever no CVSS score existed, which went stale the moment
    // that posture score was anything else -- it now always states the
    // real, currently-displayed score instead of assuming one.
    const postureSentence = hasCvss
        ? `The highest calculated CVSS v3.1 base score was ` +
          `${maximumCvss.toFixed(1)} (${getCvssSeverity(maximumCvss)}), mapping to an observed ` +
          `security posture of ${safeScore}/100. `
        : `No CVSS-scored finding was retained from this assessment, so the ` +
          `${safeScore}/100 posture score reflects SentinelScan's informational ` +
          `hardening review (SSL/TLS configuration, HTTP security headers, cookie ` +
          `flags, DNS/WHOIS exposure) rather than a CVSS mapping. `;

    let summary;

    if (!findings.length) {
        summary =
            `SentinelScan completed its authorized assessment of ` +
            `${target}. No reportable findings were included in the ` +
            `generated report. This does not prove that the target is ` +
            `fully secure. Review the raw worker output and confirm that ` +
            `all expected assessment steps completed successfully.`;
    } else {
        const critical = riskSummary?.CRITICAL || 0;
        const high = riskSummary?.HIGH || 0;
        const medium = riskSummary?.MEDIUM || 0;
        const low = riskSummary?.LOW || 0;
        const informational = riskSummary?.INFORMATIONAL || 0;
        const elevated = critical + high;

        const severityParts = [
            critical && `${critical} critical`,
            high && `${high} high`,
            medium && `${medium} medium`,
            low && `${low} low`,
            informational && `${informational} informational`,
        ].filter(Boolean);

        summary =
            `SentinelScan completed an AI-guided assessment of ${target}, ` +
            `compiling ${findings.length} finding${findings.length === 1 ? "" : "s"} ` +
            `from ${workerCount} worker${workerCount === 1 ? "" : "s"}` +
            `${severityParts.length ? ` -- a severity breakdown of ${severityParts.join(", ")}` : ""}. `;

        summary += postureSentence;

        summary += elevated
            ? `Prioritize remediation of the ${elevated} critical/high-severity ` +
              `finding${elevated === 1 ? "" : "s"} first, then work through the ` +
              `remaining medium and low-severity items. `
            : `No critical or high-severity findings were identified in this ` +
              `pass, but ${medium || low || informational ? "the remaining lower-severity items are still worth a look" : "continued periodic reassessment is still recommended"}. `;

        summary +=
            "Review each finding, verify it manually, and validate the " +
            "recommended actions before making production changes.";
    }

    window.dispatchEvent(
        new CustomEvent("sentinelscan:executive-summary-update", {
            detail: { summary },
        })
    );
}


// Builds one short, plain-language paragraph per section -- Assessment
// Findings, CVSS Scoring, Worker Findings, Sentinel AI Recommendations,
// Raw Report Data -- instead of the per-item card lists the old crawl (and
// the static HTML sections before it) rendered, and hands them to a single
// React-owned scroll-reveal story component (see ReportCrawl.jsx) via one
// CustomEvent. The reader scrolls past Risk Summary into prose, one
// section at a time, rather than a long list of individual finding/CVSS/
// worker-output cards.
function joinWithAnd(items) {
    if (items.length <= 1) return items.join("");
    if (items.length === 2) return `${items[0]} and ${items[1]}`;
    return `${items.slice(0, -1).join(", ")}, and ${items[items.length - 1]}`;
}


function buildFindingsParagraph(findings, riskSummary) {
    if (!findings.length) {
        return (
            "We didn't find any issues to report. That doesn't mean the site is " +
            "completely safe -- just make sure every check actually ran before " +
            "treating this as a clean result."
        );
    }

    const workerCount = new Set(findings.map(f => f.worker).filter(Boolean)).size;

    const severityParts = [
        riskSummary.CRITICAL && `${riskSummary.CRITICAL} critical`,
        riskSummary.HIGH && `${riskSummary.HIGH} high`,
        riskSummary.MEDIUM && `${riskSummary.MEDIUM} medium`,
        riskSummary.LOW && `${riskSummary.LOW} low`,
        riskSummary.INFORMATIONAL && `${riskSummary.INFORMATIONAL} informational`,
    ].filter(Boolean);

    const titles = findings.slice(0, 3).map((f, i) => getFindingTitle(f, i));
    const remaining = findings.length - titles.length;

    let paragraph =
        `We found ${findings.length} issue${findings.length === 1 ? "" : "s"} ` +
        `using ${workerCount} check${workerCount === 1 ? "" : "s"}` +
        `${severityParts.length ? ` -- that's ${joinWithAnd(severityParts)}` : ""}. `;

    paragraph += `A few examples: ${joinWithAnd(titles.map(t => `"${t}"`))}`;
    paragraph += remaining > 0 ? `, plus ${remaining} more listed below.` : ".";

    return paragraph;
}


function buildCvssParagraph(cvssScores, maximumCvss) {
    if (!cvssScores.length || maximumCvss === null) {
        return (
            "None of the issues here got a formal risk score (CVSS). The score " +
            "shown above instead comes from a general check of your site's " +
            "security settings, not from a scored issue."
        );
    }

    const topScore = cvssScores.reduce((best, score) => {
        const value = Number(score.base_score ?? score.score);
        const bestValue = Number(best?.base_score ?? best?.score ?? -1);
        return Number.isFinite(value) && value > bestValue ? score : best;
    }, null);

    return (
        `${cvssScores.length} issue${cvssScores.length === 1 ? "" : "s"} got a risk score. ` +
        `The highest was ${maximumCvss.toFixed(1)} out of 10 ` +
        `(${getCvssSeverity(maximumCvss)})${topScore?.finding ? `, for "${topScore.finding}"` : ""}. ` +
        "Take a look at each score before deciding what to fix first."
    );
}


function buildWorkerParagraph(findings) {
    const workers = Array.from(new Set(findings.map(f => f.worker).filter(Boolean)));

    if (!workers.length) {
        return "No tool results were attached to this report.";
    }

    return (
        `We used ${workers.length} tool${workers.length === 1 ? "" : "s"} to scan the site: ` +
        `${joinWithAnd(workers.map(formatWorkerName))}. Their raw results are what every ` +
        "finding and severity rating above is based on."
    );
}


function buildRecommendationsParagraph(recommendations) {
    if (!recommendations.length) {
        return "Our AI didn't have any specific suggestions for this scan.";
    }

    const titles = recommendations.slice(0, 3).map(r => r.title);
    const remaining = recommendations.length - titles.length;

    let paragraph = `Our AI suggests ${recommendations.length} thing${recommendations.length === 1 ? "" : "s"} to fix, starting with ${joinWithAnd(titles)}`;
    paragraph += remaining > 0 ? `, and ${remaining} more.` : ".";
    paragraph += " Go through them in order -- the most important ones come first.";

    return paragraph;
}


function dispatchReportCrawl(report, findings, cvssScores, maximumCvss, riskSummary) {
    let detail;

    try {
        detail = {
            findingsText: buildFindingsParagraph(findings, riskSummary),
            cvssText: buildCvssParagraph(cvssScores, maximumCvss),
            workerText: buildWorkerParagraph(findings),
            recommendationsText: buildRecommendationsParagraph(buildRecommendations(findings, cvssScores)),
            rawJsonText:
                "Want every detail? Click the Download JSON button above to " +
                "get the full, raw report.",
        };
    } catch (error) {
        console.error("Failed to build report crawl paragraphs:", error);
        const fallback = "This section could not be generated for this report.";
        detail = {
            findingsText: fallback,
            cvssText: fallback,
            workerText: fallback,
            recommendationsText: fallback,
            rawJsonText: fallback,
        };
    }

    // Latched on window in addition to being dispatched live: report.js's
    // fetches can resolve fast enough (confirmed live -- localhost round
    // trips) to call this before React has finished flushing effects for
    // ReportCrawl specifically (six nested ScrollReveal/GSAP instances make
    // its own mount noticeably heavier than the simpler score/risk-summary
    // listeners elsewhere, which is why only this one was ever observed
    // missing the event). ReportCrawl reads this synchronously on mount as
    // a fallback for exactly that race, instead of only ever listening for
    // a live event it may have already missed.
    window.__sentinelscanReportCrawl = detail;
    window.dispatchEvent(
        new CustomEvent("sentinelscan:report-crawl-update", { detail })
    );
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


// renderCvssScores/renderWorkerFindings/renderRecommendations (the old
// per-section innerHTML writers) were removed -- dispatchReportCrawl()
// above now builds this same data and hands it to the React-owned
// ReportCrawl component in one event instead.


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


