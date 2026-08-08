"""SentinelScan report generator.

The report worker formats retained evidence and applies SentinelScan's
configured security-score display policy.

Important:
- CVSS remains an independent 0.0-10.0 vulnerability severity metric.
- Informational observations never receive fake CVSS scores.
- If there is no positive CVSS-scored finding, SentinelScan can still show
  an 80-100 observed posture score based on directly observed hardening
  conditions.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


REPORT_VERSION = "4.2"

SCORABLE_SEVERITIES = {
    "LOW",
    "MEDIUM",
    "HIGH",
    "CRITICAL",
}


# ---------------------------------------------------------
# Workers whose normal observations are informational.
#
# These must never create CVSS exposure simply because
# something was observed.
# ---------------------------------------------------------

INFORMATIONAL_ONLY_WORKERS = {
    "dns_lookup",
    "dns_worker",

    "reverse_dns_lookup",
    "reverse_dns_worker",

    "whois_lookup",
    "whois_worker",

    "robots_txt_parse",
    "robots_worker",

    "sitemap_parse",
    "sitemap_worker",

    "ddos_resilience_check",
    "ddos_worker",
}


_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "with",
    "finding",
    "issue",
    "worker",
    "detected",
    "observed",
}


# =========================================================
# Utility helpers
# =========================================================

def _worker_key(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "_",
        str(value or "").strip().lower(),
    ).strip("_")


def _severity_for_cvss(
    score: Optional[float],
) -> str:

    if score is None or score <= 0.0:
        return "NONE"

    if score <= 3.9:
        return "LOW"

    if score <= 6.9:
        return "MEDIUM"

    if score <= 8.9:
        return "HIGH"

    return "CRITICAL"


def _normalize_text(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        str(value or "").lower(),
    ).strip()


def _tokens(value: Any) -> set[str]:
    return {
        token
        for token in _normalize_text(value).split()
        if token
        and token not in _STOPWORDS
    }


def _safe(value: Any) -> str:
    return escape(str(value or ""))


# =========================================================
# Informational posture score
# =========================================================

def informational_posture_score(
    findings: Sequence[Dict[str, Any]],
) -> int:
    """
    Calculates the SentinelScan informational posture score.

    Used only when there is NO positive CVSS-scored vulnerability.

    Range:
        80-100 / 100

    This is NOT CVSS.

    The score considers directly observed hardening conditions
    without pretending they are vulnerabilities.

    These do NOT reduce the score simply by existing:

        DNS
        Reverse DNS
        WHOIS
        robots.txt
        sitemap.xml
        passive DDoS/CDN/WAF observations

    Hardening conditions that can reduce this score include:

        missing HTTP security headers
        insecure cookie attributes
        certificate close to expiry
        unexpected publicly reachable services
    """

    deduction = 0

    for finding in findings or []:

        if not isinstance(finding, dict):
            continue

        worker = _worker_key(
            finding.get("worker")
        )

        evidence = (
            finding.get("evidence")
            if isinstance(
                finding.get("evidence"),
                dict,
            )
            else {}
        )

        # =====================================================
        # HTTP security headers
        # =====================================================

        if worker in {
            "http_headers",
            "headers_worker",
        }:

            missing = {
                str(header)
                for header
                in (
                    evidence.get(
                        "missing_headers"
                    )
                    or []
                )
            }

            header_weights = {
                "Strict-Transport-Security": 3,
                "Content-Security-Policy": 3,
                "X-Frame-Options": 2,
                "X-Content-Type-Options": 1,
                "Referrer-Policy": 1,
                "Permissions-Policy": 1,
            }

            for header in missing:

                deduction += (
                    header_weights.get(
                        header,
                        1,
                    )
                )

        # =====================================================
        # TLS maintenance
        # =====================================================

        elif worker in {
            "ssl_check",
            "ssl_worker",
        }:

            # Invalid TLS certificates should normally already
            # become actionable CVSS findings.
            #
            # This block only applies when TLS is otherwise valid
            # but certificate expiry is approaching.

            if evidence.get(
                "is_valid"
            ) is True:

                try:

                    days = int(
                        evidence.get(
                            "days_until_expiry",
                            9999,
                        )
                    )

                except (
                    TypeError,
                    ValueError,
                ):

                    days = 9999

                if days <= 7:

                    deduction += 4

                elif days <= 30:

                    deduction += 2

        # =====================================================
        # Cookie hardening
        # =====================================================

        elif worker in {
            "cookie_analysis",
            "cookie_worker",
        }:

            cookies = evidence.get(
                "cookies"
            )

            if isinstance(
                cookies,
                list,
            ):

                flagged = 0

                for cookie in cookies:

                    if not isinstance(
                        cookie,
                        dict,
                    ):
                        continue

                    if (
                        cookie.get(
                            "is_vulnerable"
                        )
                        is True
                    ):

                        flagged += 1

                # Small posture impact only.
                #
                # This does not automatically turn ordinary
                # cookie observations into CVSS vulnerabilities.

                deduction += min(
                    flagged,
                    3,
                )

        # =====================================================
        # Unexpected public TCP services
        # =====================================================

        elif worker in {
            "port_scan",
            "portscan_worker",
        }:

            open_ports = evidence.get(
                "open_ports"
            )

            if isinstance(
                open_ports,
                list,
            ):

                unexpected = 0

                for item in open_ports:

                    if not isinstance(
                        item,
                        dict,
                    ):
                        continue

                    try:

                        port = int(
                            item.get(
                                "port"
                            )
                        )

                    except (
                        TypeError,
                        ValueError,
                    ):

                        continue

                    # Public web ports are expected.
                    #
                    # Their presence must not lower the score.

                    if port not in {
                        80,
                        443,
                    }:

                        unexpected += 1

                # Reachability alone is NOT a vulnerability.
                #
                # This is intentionally a small hardening
                # deduction.

                deduction += min(
                    unexpected * 2,
                    4,
                )

    # ---------------------------------------------------------
    # Informational / no-CVSS score is restricted to 80-100.
    # ---------------------------------------------------------

    deduction = min(
        deduction,
        20,
    )

    score = (
        100
        - deduction
    )

    return max(
        80,
        min(
            100,
            score,
        ),
    )


# =========================================================
# CVSS -> overall project score mapping
# =========================================================

def security_score_from_cvss(
    maximum_cvss: Optional[float],
    findings: Sequence[
        Dict[str, Any]
    ] | None = None,
) -> int:
    """
    SentinelScan security-score mapping.

    Positive validated CVSS finding:

        Critical
        CVSS 9.0-10.0
        Security score 0-10

        High
        CVSS 7.0-8.9
        Security score 10-30

        Medium
        CVSS 4.0-6.9
        Security score 30-60

        Low
        CVSS 0.1-3.9
        Security score 60-80

    No positive CVSS:

        Informational / None / N/A
        Security score 80-100

    Linear interpolation is used inside each CVSS band.
    """

    # ---------------------------------------------------------
    # No CVSS-scored vulnerability.
    # ---------------------------------------------------------

    if maximum_cvss is None:

        return informational_posture_score(
            findings or []
        )

    try:

        cvss = float(
            maximum_cvss
        )

    except (
        TypeError,
        ValueError,
    ):

        return informational_posture_score(
            findings or []
        )

    cvss = max(
        0.0,
        min(
            10.0,
            cvss,
        ),
    )

    # CVSS 0.0 means NONE.
    #
    # Use informational posture instead.

    if cvss <= 0.0:

        return informational_posture_score(
            findings or []
        )

    # =====================================================
    # LOW
    #
    # 0.1 -> 80
    # 3.9 -> 60
    # =====================================================

    if cvss <= 3.9:

        result = (
            80.0
            - (
                (
                    cvss
                    - 0.1
                )
                / 3.8
            )
            * 20.0
        )

    # =====================================================
    # MEDIUM
    #
    # 4.0 -> 60
    # 6.9 -> 30
    # =====================================================

    elif cvss <= 6.9:

        result = (
            60.0
            - (
                (
                    cvss
                    - 4.0
                )
                / 2.9
            )
            * 30.0
        )

    # =====================================================
    # HIGH
    #
    # 7.0 -> 30
    # 8.9 -> 10
    # =====================================================

    elif cvss <= 8.9:

        result = (
            30.0
            - (
                (
                    cvss
                    - 7.0
                )
                / 1.9
            )
            * 20.0
        )

    # =====================================================
    # CRITICAL
    #
    # 9.0 -> 10
    # 10 -> 0
    # =====================================================

    else:

        result = (
            10.0
            - (
                (
                    cvss
                    - 9.0
                )
                / 1.0
            )
            * 10.0
        )

    return int(
        round(
            max(
                0.0,
                min(
                    100.0,
                    result,
                ),
            )
        )
    )


# =========================================================
# Overall risk label
# =========================================================

def _risk_label(
    maximum_cvss: Optional[float],
    security_score: int = 100,
) -> str:

    severity = _severity_for_cvss(
        maximum_cvss
    )

    if severity == "CRITICAL":

        return (
            "CRITICAL OBSERVED RISK"
        )

    if severity == "HIGH":

        return (
            "HIGH OBSERVED RISK"
        )

    if severity == "MEDIUM":

        return (
            "MEDIUM OBSERVED RISK"
        )

    if severity == "LOW":

        return (
            "LOW OBSERVED RISK"
        )

    # ---------------------------------------------------------
    # CVSS = N/A / NONE
    # ---------------------------------------------------------

    if security_score >= 95:

        return (
            "STRONG OBSERVED POSTURE"
        )

    if security_score >= 90:

        return (
            "GOOD OBSERVED POSTURE"
        )

    return (
        "HARDENING OPPORTUNITIES"
    )


# =========================================================
# Finding <-> CVSS matching
# =========================================================

def _score_matches_finding(
    score_item: Dict[str, Any],
    finding: Dict[str, Any],
) -> bool:

    scored_name = _normalize_text(
        score_item.get(
            "finding"
        )
    )

    if not scored_name:

        return False

    candidate_values = [
        finding.get(
            "finding"
        ),
        finding.get(
            "title"
        ),
        finding.get(
            "summary"
        ),
    ]

    for value in candidate_values:

        candidate = _normalize_text(
            value
        )

        if not candidate:

            continue

        if scored_name == candidate:

            return True

        if (
            len(scored_name) >= 8
            and (
                scored_name in candidate
                or candidate in scored_name
            )
        ):

            return True

        scored_tokens = _tokens(
            scored_name
        )

        candidate_tokens = _tokens(
            candidate
        )

        if (
            scored_tokens
            and candidate_tokens
        ):

            overlap = len(
                scored_tokens
                & candidate_tokens
            )

            smaller = min(
                len(
                    scored_tokens
                ),
                len(
                    candidate_tokens
                ),
            )

            if (
                smaller >= 2
                and (
                    overlap
                    / smaller
                )
                >= 0.60
            ):

                return True

    return False


# =========================================================
# Finding sanitization
# =========================================================

def _sanitize_findings(
    findings: Sequence[
        Dict[str, Any]
    ],
) -> List[Dict[str, Any]]:

    sanitized: List[
        Dict[str, Any]
    ] = []

    for raw in (
        findings
        or []
    ):

        if not isinstance(
            raw,
            dict,
        ):

            continue

        finding = dict(
            raw
        )

        worker = _worker_key(
            finding.get(
                "worker"
            )
        )

        severity = str(
            finding.get(
                "severity"
            )
            or "INFORMATIONAL"
        ).upper()

        # -----------------------------------------------------
        # Metadata/context-only workers cannot become CVSS
        # vulnerabilities merely because Gemini labels them.
        # -----------------------------------------------------

        if (
            worker
            in INFORMATIONAL_ONLY_WORKERS
        ):

            severity = (
                "INFORMATIONAL"
            )

        elif (
            severity
            not in (
                SCORABLE_SEVERITIES
                | {
                    "INFORMATIONAL",
                }
            )
        ):

            severity = (
                "INFORMATIONAL"
            )

        finding[
            "severity"
        ] = severity

        sanitized.append(
            finding
        )

    return sanitized


# =========================================================
# CVSS sanitization
# =========================================================

def _sanitize_cvss_scores(
    cvss_scores: Sequence[
        Dict[str, Any]
    ],
    findings: Sequence[
        Dict[str, Any]
    ],
) -> List[Dict[str, Any]]:
    """
    Keeps only valid positive CVSS scores that correspond to
    an actual retained actionable finding.
    """

    sanitized: List[
        Dict[str, Any]
    ] = []

    for raw_score in (
        cvss_scores
        or []
    ):

        if not isinstance(
            raw_score,
            dict,
        ):

            continue

        try:

            numeric = float(
                raw_score.get(
                    "base_score",
                    raw_score.get(
                        "score"
                    ),
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            continue

        # -----------------------------------------------------
        # CVSS 0 is NONE.
        #
        # It must not be presented as vulnerability exposure.
        # -----------------------------------------------------

        if not (
            0.0
            < numeric
            <= 10.0
        ):

            continue

        matched = None

        for finding in findings:

            worker = _worker_key(
                finding.get(
                    "worker"
                )
            )

            severity = str(
                finding.get(
                    "severity"
                )
                or "INFORMATIONAL"
            ).upper()

            if (
                worker
                in INFORMATIONAL_ONLY_WORKERS
            ):

                continue

            if (
                severity
                not in SCORABLE_SEVERITIES
            ):

                continue

            if _score_matches_finding(
                raw_score,
                finding,
            ):

                matched = finding

                break

        # -----------------------------------------------------
        # A detached / unmatched score cannot affect the report.
        # -----------------------------------------------------

        if matched is None:

            continue

        item = dict(
            raw_score
        )

        item[
            "base_score"
        ] = round(
            numeric,
            1,
        )

        item[
            "severity"
        ] = _severity_for_cvss(
            numeric
        )

        sanitized.append(
            item
        )

    return sanitized


# =========================================================
# Reconcile findings with CVSS
# =========================================================

def _reconcile_findings_with_cvss(
    findings: Sequence[
        Dict[str, Any]
    ],
    cvss_scores: Sequence[
        Dict[str, Any]
    ],
) -> tuple[
    List[Dict[str, Any]],
    List[Dict[str, Any]],
]:
    """
    Produces one internally consistent findings/CVSS view.

    Rules:

    - Informational-only workers always stay informational.
    - A LOW/MEDIUM/HIGH/CRITICAL badge requires a matching
      positive CVSS result.
    - If a finding was labelled scorable but CVSS did not
      produce a valid score, the report displays it as
      informational instead of inventing a CVSS number.
    """

    clean_findings = (
        _sanitize_findings(
            findings
        )
    )

    clean_scores = (
        _sanitize_cvss_scores(
            cvss_scores,
            clean_findings,
        )
    )

    reconciled: List[
        Dict[str, Any]
    ] = []

    for raw_finding in (
        clean_findings
    ):

        finding = dict(
            raw_finding
        )

        worker = _worker_key(
            finding.get(
                "worker"
            )
        )

        # -----------------------------------------------------
        # Informational-only worker
        # -----------------------------------------------------

        if (
            worker
            in INFORMATIONAL_ONLY_WORKERS
        ):

            finding[
                "severity"
            ] = (
                "INFORMATIONAL"
            )

            finding[
                "actionable"
            ] = False

            finding.pop(
                "cvss_base_score",
                None,
            )

            finding.pop(
                "cvss_vector",
                None,
            )

            finding[
                "cvss_status"
            ] = (
                "NOT_APPLICABLE"
            )

            reconciled.append(
                finding
            )

            continue

        matching_score = next(
            (
                score
                for score
                in clean_scores
                if _score_matches_finding(
                    score,
                    finding,
                )
            ),
            None,
        )

        # -----------------------------------------------------
        # No matching CVSS
        # -----------------------------------------------------

        if matching_score is None:

            if (
                str(
                    finding.get(
                        "severity"
                    )
                    or "INFORMATIONAL"
                ).upper()
                in SCORABLE_SEVERITIES
            ):

                finding[
                    "severity"
                ] = (
                    "INFORMATIONAL"
                )

                finding[
                    "actionable"
                ] = False

                finding[
                    "cvss_status"
                ] = (
                    "UNSCORED"
                )

            else:

                finding[
                    "severity"
                ] = (
                    "INFORMATIONAL"
                )

                finding[
                    "cvss_status"
                ] = (
                    "NOT_APPLICABLE"
                )

            finding.pop(
                "cvss_base_score",
                None,
            )

            finding.pop(
                "cvss_vector",
                None,
            )

        # -----------------------------------------------------
        # Matching validated CVSS
        # -----------------------------------------------------

        else:

            numeric = float(
                matching_score[
                    "base_score"
                ]
            )

            finding[
                "severity"
            ] = (
                _severity_for_cvss(
                    numeric
                )
            )

            finding[
                "actionable"
            ] = True

            finding[
                "cvss_status"
            ] = (
                "SCORED"
            )

            finding[
                "cvss_base_score"
            ] = round(
                numeric,
                1,
            )

            finding[
                "cvss_vector"
            ] = (
                matching_score.get(
                    "vector"
                )
            )

        reconciled.append(
            finding
        )

    # ---------------------------------------------------------
    # Remove any CVSS score that no longer maps to a retained
    # scorable finding.
    # ---------------------------------------------------------

    final_scores: List[
        Dict[str, Any]
    ] = []

    for score in clean_scores:

        if any(
            (
                str(
                    finding.get(
                        "cvss_status"
                    )
                )
                == "SCORED"
            )
            and _score_matches_finding(
                score,
                finding,
            )
            for finding
            in reconciled
        ):

            final_scores.append(
                score
            )

    return (
        reconciled,
        final_scores,
    )


# =========================================================
# Report generation
# =========================================================

def generate_report(
    target: str,
    findings: List[
        Dict[str, Any]
    ],
    cvss_scores: List[
        Dict[str, Any]
    ],
    worker_coverage: List[
        Dict[str, Any]
    ] | None = None,
    scan_duration: float = 0.0,
) -> Dict[str, Any]:
    """
    Generates SentinelScan JSON and PDF reports.
    """

    try:

        worker_coverage = list(
            worker_coverage
            or []
        )

        findings, cvss_scores = (
            _reconcile_findings_with_cvss(
                findings,
                cvss_scores,
            )
        )

        scan_id = str(
            uuid.uuid4()
        )

        timestamp = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        project_root = os.path.abspath(
            os.path.join(
                os.path.dirname(
                    __file__
                ),
                "..",
                "..",
                "..",
            )
        )

        reports_dir = os.path.join(
            project_root,
            "reports",
        )

        os.makedirs(
            reports_dir,
            exist_ok=True,
        )

        json_path = os.path.join(
            reports_dir,
            f"{scan_id}.json",
        )

        pdf_path = os.path.join(
            reports_dir,
            f"{scan_id}.pdf",
        )

        # =====================================================
        # Risk summary
        # =====================================================

        risk_summary = {
            "CRITICAL": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0,
            "INFORMATIONAL": 0,
        }

        for finding in findings:

            severity = str(
                finding.get(
                    "severity"
                )
                or "INFORMATIONAL"
            ).upper()

            if (
                severity
                not in risk_summary
            ):

                severity = (
                    "INFORMATIONAL"
                )

            risk_summary[
                severity
            ] += 1

        # =====================================================
        # Maximum CVSS
        # =====================================================

        maximum_cvss = max(
            (
                float(
                    item[
                        "base_score"
                    ]
                )
                for item
                in cvss_scores
            ),
            default=None,
        )

        maximum_cvss_severity = (
            _severity_for_cvss(
                maximum_cvss
            )
        )

        # =====================================================
        # Overall security score
        # =====================================================

        security_score = (
            security_score_from_cvss(
                maximum_cvss,
                findings,
            )
        )

        risk_label = (
            _risk_label(
                maximum_cvss,
                security_score,
            )
        )

        # =====================================================
        # JSON report
        # =====================================================

        json_report = {

            "target":
                target,

            "scan_timestamp":
                timestamp,

            "scan_duration":
                scan_duration,

            "report_version":
                REPORT_VERSION,

            "security_score":
                security_score,

            "security_score_method": (
                "Validated CVSS band mapping when a "
                "CVSS-scored finding exists; otherwise "
                "an 80-100 informational posture score "
                "based on observed hardening conditions."
            ),

            "maximum_cvss":
                maximum_cvss,

            "maximum_cvss_severity":
                maximum_cvss_severity,

            "risk_label":
                risk_label,

            "score_confidence":
                "LIMITED",

            "overall_risk_summary":
                risk_summary,

            "findings":
                findings,

            "cvss_scores":
                cvss_scores,

            "worker_coverage":
                worker_coverage,

            "limitations": [

                (
                    "This is an external point-in-time "
                    "assessment, not proof that the target "
                    "is secure or insecure."
                ),

                (
                    "Informational observations do not "
                    "receive CVSS scores."
                ),

                (
                    "The 0-100 security score is a "
                    "SentinelScan display metric. "
                    "With positive CVSS it follows the "
                    "configured CVSS bands; with CVSS N/A "
                    "it uses an 80-100 hardening posture "
                    "band. It is not an official CVSS metric."
                ),

            ],
        }

        with open(
            json_path,
            "w",
            encoding="utf-8",
        ) as handle:

            json.dump(
                json_report,
                handle,
                indent=2,
            )

        # =====================================================
        # PDF
        # =====================================================

        _generate_pdf(

            pdf_path=
                pdf_path,

            target=
                target,

            timestamp=
                timestamp,

            scan_id=
                scan_id,

            risk_summary=
                risk_summary,

            findings=
                findings,

            cvss_scores=
                cvss_scores,

            worker_coverage=
                worker_coverage,

            scan_duration=
                scan_duration,

            security_score=
                security_score,

            maximum_cvss=
                maximum_cvss,

            maximum_cvss_severity=
                maximum_cvss_severity,

            risk_label=
                risk_label,
        )

        return {

            "pdf_path":
                pdf_path,

            "json_path":
                json_path,

            "security_score":
                security_score,

            "maximum_cvss":
                maximum_cvss,

            "maximum_cvss_severity":
                maximum_cvss_severity,

            "risk_label":
                risk_label,
        }

    except Exception as exc:

        return {

            "error":
                "Report generation failed",

            "details":
                str(exc),
        }


# =========================================================
# PDF generation
# =========================================================

def _generate_pdf(
    pdf_path: str,
    target: str,
    timestamp: str,
    scan_id: str,
    risk_summary: Dict[
        str,
        int,
    ],
    findings: List[
        Dict[str, Any]
    ],
    cvss_scores: List[
        Dict[str, Any]
    ],
    worker_coverage: List[
        Dict[str, Any]
    ],
    scan_duration: float,
    security_score: int,
    maximum_cvss: Optional[
        float
    ],
    maximum_cvss_severity: str,
    risk_label: str,
) -> None:

    doc = BaseDocTemplate(

        pdf_path,

        pagesize=
            letter,

        leftMargin=
            0.5 * inch,

        rightMargin=
            0.5 * inch,

        topMargin=
            0.5 * inch,

        bottomMargin=
            0.5 * inch,
    )

    styles = (
        getSampleStyleSheet()
    )

    title_style = ParagraphStyle(

        "ReportTitle",

        parent=
            styles[
                "Heading1"
            ],

        fontSize=
            24,

        spaceAfter=
            4,
    )

    subtitle_style = ParagraphStyle(

        "ReportSubtitle",

        parent=
            styles[
                "Normal"
            ],

        fontSize=
            10,

        textColor=
            colors.grey,

        spaceAfter=
            20,
    )

    section_title = ParagraphStyle(

        "SectionTitle",

        parent=
            styles[
                "Heading2"
            ],

        fontSize=
            16,

        spaceBefore=
            20,

        spaceAfter=
            10,
    )

    body_style = ParagraphStyle(

        "Body",

        parent=
            styles[
                "Normal"
            ],

        alignment=
            TA_LEFT,

        leading=
            14,
    )

    header_bg = colors.HexColor(
        "#0f172a"
    )

    severity_colors = {

        "CRITICAL":
            colors.HexColor(
                "#fee2e2"
            ),

        "HIGH":
            colors.HexColor(
                "#fee2e2"
            ),

        "MEDIUM":
            colors.HexColor(
                "#fef3c7"
            ),

        "LOW":
            colors.HexColor(
                "#dbeafe"
            ),

        "INFORMATIONAL":
            colors.HexColor(
                "#eef2ff"
            ),

        "NONE":
            colors.HexColor(
                "#ecfdf5"
            ),
    }

    # =====================================================
    # Header/footer
    # =====================================================

    def header_footer(
        canvas,
        current_doc,
    ):

        canvas.saveState()

        canvas.setFont(
            "Helvetica-Bold",
            12,
        )

        canvas.setFillColor(
            colors.HexColor(
                "#0ea5e9"
            )
        )

        canvas.drawString(
            0.5 * inch,
            letter[1]
            - 0.5 * inch,
            "SentinelScan",
        )

        canvas.setStrokeColor(
            colors.lightgrey
        )

        canvas.line(
            0.5 * inch,
            letter[1]
            - 0.6 * inch,
            letter[0]
            - 0.5 * inch,
            letter[1]
            - 0.6 * inch,
        )

        canvas.setFont(
            "Helvetica",
            9,
        )

        canvas.setFillColor(
            colors.grey
        )

        canvas.drawString(
            0.5 * inch,
            0.4 * inch,
            (
                "Authorized external "
                "security assessment"
            ),
        )

        canvas.drawRightString(
            letter[0]
            - 0.5 * inch,
            0.4 * inch,
            f"Page {current_doc.page}",
        )

        canvas.restoreState()

    frame = Frame(

        doc.leftMargin,

        doc.bottomMargin
        + 0.3 * inch,

        doc.width,

        doc.height
        - 0.8 * inch,

        id=
            "normal",
    )

    doc.addPageTemplates(
        [
            PageTemplate(

                id=
                    "main",

                frames=
                    frame,

                onPage=
                    header_footer,
            )
        ]
    )

    max_cvss_display = (
        "N/A"
        if maximum_cvss
        is None
        else f"{maximum_cvss:.1f}"
    )

    story: List[Any] = [

        Paragraph(
            (
                "SentinelScan Security "
                "Assessment Report"
            ),
            title_style,
        ),

        Paragraph(
            (
                f"Report ID: "
                f"{_safe(scan_id)}"
            ),
            subtitle_style,
        ),
    ]

    # =====================================================
    # Metadata
    # =====================================================

    metadata = [

        [
            (
                f"Target: "
                f"{_safe(target)}"
            ),
            (
                f"Generated: "
                f"{_safe(timestamp)}"
            ),
        ],

        [
            (
                f"Security score: "
                f"{security_score}/100"
            ),
            (
                f"Risk label: "
                f"{_safe(risk_label)}"
            ),
        ],

        [
            (
                f"Maximum CVSS: "
                f"{max_cvss_display}"
            ),
            (
                f"CVSS severity: "
                f"{_safe(maximum_cvss_severity)}"
            ),
        ],

        [
            (
                "Score confidence: LIMITED"
            ),
            (
                f"Report version: "
                f"{REPORT_VERSION}"
            ),
        ],
    ]

    metadata_table = Table(

        metadata,

        colWidths=[
            3.75 * inch,
            3.75 * inch,
        ],
    )

    metadata_table.setStyle(

        TableStyle(
            [

                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, -1),
                    colors.darkgrey,
                ),

                (
                    "FONTNAME",
                    (0, 0),
                    (-1, -1),
                    "Helvetica",
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
            ]
        )
    )

    story.append(
        metadata_table
    )

    # =====================================================
    # Executive summary
    # =====================================================

    story.append(

        Paragraph(
            "Executive Summary",
            section_title,
        )
    )

    if maximum_cvss is None:

        cvss_sentence = (

            "No retained actionable finding had "
            "a valid positive CVSS score, so "
            "maximum CVSS is N/A. "

            f"The observed informational posture "
            f"score is {security_score}/100. "

            "This posture value reflects only "
            "observed hardening conditions and "
            "is not a CVSS score."
        )

    else:

        cvss_sentence = (

            f"The highest retained CVSS v3.1 "
            f"base score is "
            f"{maximum_cvss:.1f} "
            f"({maximum_cvss_severity}), "

            f"mapping to "
            f"{security_score}/100 "
            "on the SentinelScan posture gauge."
        )

    story.append(

        Paragraph(

            _safe(

                (
                    f"This automated assessment "
                    f"targeted {target}. "

                    f"Findings: "
                    f"{risk_summary['CRITICAL']} "
                    f"critical, "

                    f"{risk_summary['HIGH']} "
                    f"high, "

                    f"{risk_summary['MEDIUM']} "
                    f"medium, "

                    f"{risk_summary['LOW']} "
                    f"low, and "

                    f"{risk_summary['INFORMATIONAL']} "
                    f"informational. "

                    f"{cvss_sentence} "

                    "The gauge is a project "
                    "display metric and does not "
                    "prove that the target is "
                    "secure."
                )
            ),

            body_style,
        )
    )

    # =====================================================
    # Risk summary
    # =====================================================

    story.append(

        Paragraph(
            "Risk Summary",
            section_title,
        )
    )

    risk_data = [

        [
            "Severity",
            "Count",
        ]
    ]

    for severity in [

        "CRITICAL",
        "HIGH",
        "MEDIUM",
        "LOW",
        "INFORMATIONAL",

    ]:

        risk_data.append(

            [
                severity,
                str(
                    risk_summary.get(
                        severity,
                        0,
                    )
                ),
            ]
        )

    risk_style = TableStyle(
        [

            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                header_bg,
            ),

            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white,
            ),

            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Helvetica-Bold",
            ),

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey,
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, 0),
                10,
            ),
        ]
    )

    for index, severity in enumerate(

        [
            "CRITICAL",
            "HIGH",
            "MEDIUM",
            "LOW",
            "INFORMATIONAL",
        ],

        1,

    ):

        risk_style.add(

            "BACKGROUND",

            (
                0,
                index,
            ),

            (
                -1,
                index,
            ),

            severity_colors[
                severity
            ],
        )

    risk_table = Table(

        risk_data,

        colWidths=[
            2.5 * inch,
            1.5 * inch,
        ],
    )

    risk_table.setStyle(
        risk_style
    )

    story.extend(

        [
            risk_table,
            PageBreak(),
        ]
    )

    # =====================================================
    # Findings
    # =====================================================

    story.append(

        Paragraph(
            "Assessment Findings",
            section_title,
        )
    )

    finding_data = [

        [
            "Severity",
            "Finding",
            "What it means",
            "Recommendation",
        ]
    ]

    finding_style = TableStyle(
        [

            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                header_bg,
            ),

            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white,
            ),

            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Helvetica-Bold",
            ),

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey,
            ),

            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP",
            ),
        ]
    )

    for index, finding in enumerate(
        findings,
        1,
    ):

        severity = str(
            finding.get(
                "severity"
            )
            or "INFORMATIONAL"
        ).upper()

        finding_data.append(

            [

                Paragraph(
                    _safe(
                        severity
                    ),
                    body_style,
                ),

                Paragraph(
                    _safe(
                        finding.get(
                            "summary"
                        )
                        or finding.get(
                            "title"
                        )
                        or "Finding"
                    ),
                    body_style,
                ),

                Paragraph(
                    _safe(
                        finding.get(
                            "what_it_means"
                        )
                        or ""
                    ),
                    body_style,
                ),

                Paragraph(
                    _safe(
                        finding.get(
                            "recommendation"
                        )
                        or ""
                    ),
                    body_style,
                ),
            ]
        )

        finding_style.add(

            "BACKGROUND",

            (
                0,
                index,
            ),

            (
                -1,
                index,
            ),

            severity_colors.get(
                severity,
                colors.white,
            ),
        )

    if len(
        finding_data
    ) == 1:

        finding_data.append(

            [
                "INFORMATIONAL",
                "No reportable findings",
                "",
                "",
            ]
        )

    finding_table = Table(

        finding_data,

        colWidths=[
            1.4 * inch,
            2.0 * inch,
            2.05 * inch,
            2.05 * inch,
        ],
    )

    finding_table.setStyle(
        finding_style
    )

    story.extend(

        [
            finding_table,
            Spacer(
                1,
                18,
            ),
        ]
    )

    # =====================================================
    # Worker coverage
    # =====================================================

    story.append(

        Paragraph(
            "Worker Coverage",
            section_title,
        )
    )

    worker_data = [

        [
            "Worker",
            "Status",
            "Duration",
            "Result",
        ]
    ]

    for worker in worker_coverage:

        try:

            duration = (
                f"{float(worker.get('duration', 0)):.2f}s"
            )

        except (
            TypeError,
            ValueError,
        ):

            duration = "N/A"

        worker_data.append(

            [

                Paragraph(
                    _safe(
                        worker.get(
                            "worker"
                        )
                        or ""
                    ),
                    body_style,
                ),

                _safe(
                    worker.get(
                        "status"
                    )
                    or ""
                ),

                duration,

                Paragraph(
                    _safe(
                        worker.get(
                            "result"
                        )
                        or ""
                    ),
                    body_style,
                ),
            ]
        )

    if len(
        worker_data
    ) == 1:

        worker_data.append(

            [
                (
                    "No worker coverage "
                    "retained"
                ),
                "N/A",
                "N/A",
                "",
            ]
        )

    worker_table = Table(

        worker_data,

        colWidths=[
            1.6 * inch,
            1.0 * inch,
            0.9 * inch,
            4.0 * inch,
        ],
    )

    worker_table.setStyle(

        TableStyle(
            [

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    header_bg,
                ),

                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white,
                ),

                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold",
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.grey,
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
            ]
        )
    )

    story.extend(

        [
            worker_table,
            PageBreak(),
        ]
    )

    # =====================================================
    # CVSS section
    # =====================================================

    story.append(

        Paragraph(
            "CVSS Scoring",
            section_title,
        )
    )

    if cvss_scores:

        cvss_data = [

            [
                "Finding",
                "Vector",
                "Score",
                "Severity",
            ]
        ]

        cvss_style = TableStyle(
            [

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    header_bg,
                ),

                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white,
                ),

                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold",
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.grey,
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
            ]
        )

        for index, score in enumerate(
            cvss_scores,
            1,
        ):

            severity = str(
                score.get(
                    "severity"
                )
                or "NONE"
            ).upper()

            cvss_data.append(

                [

                    Paragraph(
                        _safe(
                            score.get(
                                "finding"
                            )
                            or (
                                "Scored "
                                "finding"
                            )
                        ),
                        body_style,
                    ),

                    Paragraph(
                        _safe(
                            score.get(
                                "vector"
                            )
                            or ""
                        ),
                        body_style,
                    ),

                    (
                        f"{float(score.get('base_score')):.1f}"
                    ),

                    severity,
                ]
            )

            cvss_style.add(

                "BACKGROUND",

                (
                    0,
                    index,
                ),

                (
                    -1,
                    index,
                ),

                severity_colors.get(
                    severity,
                    colors.white,
                ),
            )

        cvss_table = Table(

            cvss_data,

            colWidths=[
                2.3 * inch,
                3.4 * inch,
                0.8 * inch,
                1.0 * inch,
            ],
        )

        cvss_table.setStyle(
            cvss_style
        )

        story.append(
            cvss_table
        )

    else:

        story.append(

            Paragraph(

                (
                    "No CVSS-scored actionable "
                    "finding was retained. "
                    "Informational observations "
                    "remain CVSS N/A."
                ),

                body_style,
            )
        )

    # =====================================================
    # Security-score mapping
    # =====================================================

    story.append(

        Spacer(
            1,
            18,
        )
    )

    story.append(

        Paragraph(
            "Security Score Mapping",
            section_title,
        )
    )

    mapping_rows = [

        [
            "CVSS severity",
            "CVSS range",
            "Displayed security score",
        ],

        [
            "CRITICAL",
            "9.0-10.0",
            "0-10 / 100",
        ],

        [
            "HIGH",
            "7.0-8.9",
            "10-30 / 100",
        ],

        [
            "MEDIUM",
            "4.0-6.9",
            "30-60 / 100",
        ],

        [
            "LOW",
            "0.1-3.9",
            "60-80 / 100",
        ],

        [
            "NONE / N/A",
            "0.0 or N/A",
            "80-100 / 100",
        ],
    ]

    mapping_table = Table(

        mapping_rows,

        colWidths=[
            2.0 * inch,
            2.0 * inch,
            3.0 * inch,
        ],
    )

    mapping_table.setStyle(

        TableStyle(
            [

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    header_bg,
                ),

                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white,
                ),

                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold",
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.grey,
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
            ]
        )
    )

    story.append(
        mapping_table
    )

    # =====================================================
    # Limitations
    # =====================================================

    story.append(

        Spacer(
            1,
            18,
        )
    )

    story.append(

        Paragraph(
            "Limitations and Disclaimer",
            section_title,
        )
    )

    story.append(

        Paragraph(

            _safe(

                (
                    "This is an automated, "
                    "external, point-in-time "
                    "assessment. Results require "
                    "manual validation. "

                    "The 0-100 gauge is a "
                    "SentinelScan project display "
                    "metric. Positive CVSS findings "
                    "use the configured CVSS-to-score "
                    "bands; CVSS N/A uses an 80-100 "
                    "observed hardening posture band. "

                    "It is not an official CVSS score."
                )
            ),

            body_style,
        )
    )

    story.append(

        Paragraph(
            (
                f"Scan duration: "
                f"{scan_duration:.2f} seconds"
            ),
            body_style,
        )
    )

    doc.build(
        story
    )