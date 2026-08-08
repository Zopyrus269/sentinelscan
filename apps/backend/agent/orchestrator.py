"""Gemini-driven SentinelScan orchestration with evidence integrity.

Gemini chooses the order of the assessment stages and supplies a concise,
user-visible reason for each selection.  The orchestrator owns the authoritative
scan state, constrains every worker to the submitted target, ensures every
assessment category is accounted for, runs CVSS once, and generates one report.

Workers are the only source of factual observations.  Gemini never supplies the
final evidence payload or invents findings.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional, Set
from urllib.parse import urlparse

from google.genai import types

from apps.backend.agent.gemini_client import GeminiClient
from apps.backend.agent.worker_dispatch import dispatch_tool
from apps.backend.workers.report_worker import generate_report

logger = logging.getLogger(__name__)

DEFAULT_MAX_ITERATIONS = 36

EVIDENCE_TOOLS: Set[str] = {
    "dns_lookup",
    "reverse_dns_lookup",
    "whois_lookup",
    "ssl_check",
    "http_headers",
    "cookie_analysis",
    "robots_txt_parse",
    "sitemap_parse",
    "port_scan",
    "ddos_resilience_check",
}
TERMINAL_TOOLS = {"calculate_cvss", "generate_report"}
ALLOWED_TOOLS = EVIDENCE_TOOLS | TERMINAL_TOOLS

# These workers provide context/posture and are never direct CVSS inputs.
CVSS_EXCLUDED_WORKERS = {
    "dns_lookup",
    "reverse_dns_lookup",
    "whois_lookup",
    "http_headers",
    "robots_txt_parse",
    "sitemap_parse",
    "port_scan",
    "ddos_resilience_check",
}

EXPECTED_WEB_PORTS = {80, 443}
AUTH_COOKIE_TOKENS = {"auth", "session", "sess", "login", "jwt", "token", "identity", "account", "sid"}
LEGACY_TLS_PROTOCOLS = {"SSLV2", "SSLV3", "TLSV1", "TLSV1.0", "TLSV1.1"}

TOOL_GUIDANCE: Dict[str, Dict[str, str]] = {
    "dns_lookup": {
        "label": "DNS Lookup",
        "reason": "DNS establishes the target's public addresses and infrastructure used by later checks.",
        "action": "Querying public A, AAAA, MX, NS, TXT and CNAME records.",
    },
    "reverse_dns_lookup": {
        "label": "Reverse DNS Lookup",
        "reason": "PTR records for DNS-resolved addresses can provide public hosting context.",
        "action": "Resolving PTR names only for an IP already observed by the DNS worker.",
    },
    "whois_lookup": {
        "label": "WHOIS / RDAP Lookup",
        "reason": "Public registration metadata provides registrar and domain-lifecycle context.",
        "action": "Retrieving public registration information through the supported WHOIS/RDAP path.",
    },
    "ssl_check": {
        "label": "SSL/TLS Check",
        "reason": "HTTPS certificate validity and negotiated TLS settings are externally observable security evidence.",
        "action": "Inspecting certificate validity, hostname, issuer, expiry, protocol and cipher.",
    },
    "http_headers": {
        "label": "HTTP Security Headers",
        "reason": "Browser-facing security controls can be observed directly in the target's HTTP response.",
        "action": "Reviewing the configured security-header baseline without changing the target.",
    },
    "cookie_analysis": {
        "label": "Cookie Analysis",
        "reason": "Public response cookies can be inspected for transport and script-access attributes.",
        "action": "Inspecting only cookies returned by the unauthenticated public response.",
    },
    "robots_txt_parse": {
        "label": "robots.txt Parser",
        "reason": "robots.txt is a public crawler-control artifact that may describe exposed paths.",
        "action": "Retrieving and parsing the public robots.txt resource.",
    },
    "sitemap_parse": {
        "label": "Sitemap XML Parser",
        "reason": "A public sitemap provides a bounded view of publicly indexed URLs.",
        "action": "Retrieving and parsing the public sitemap.xml resource.",
    },
    "port_scan": {
        "label": "Bounded Port Scan",
        "reason": "A bounded TCP-connect check shows which common public services are actually reachable.",
        "action": "Testing only the configured common TCP port set with bounded timeouts and no exploitation.",
    },
    "ddos_resilience_check": {
        "label": "Passive DDoS Resilience Check",
        "reason": "Public CDN, WAF, reverse-proxy and rate-limit indicators can be observed without attack traffic.",
        "action": "Inspecting passive DNS and HTTP metadata only; no flooding, load, or stress testing is performed.",
    },
    "calculate_cvss": {
        "label": "CVSS Evaluation",
        "reason": "All evidence categories are accounted for, so evidence-backed actionable findings can be scored once.",
        "action": "Calculating CVSS v3.1 for the final deduplicated actionable findings in one batch.",
    },
    "generate_report": {
        "label": "Report Generation",
        "reason": "Evidence collection and the single CVSS phase are complete.",
        "action": "Generating JSON and PDF from the authoritative retained assessment state.",
    },
}


def _emit_progress(callback: Optional[Callable[..., None]], **payload: Any) -> None:
    if callback is None:
        return
    try:
        callback(**payload)
    except TypeError:
        callback(
            iteration=payload.get("iteration", 0),
            max_iterations=payload.get("max_iterations", DEFAULT_MAX_ITERATIONS),
            tool_name=payload.get("tool_name", "processing"),
            reasoning=payload.get("reasoning", payload.get("reason", "")),
        )


def _host(target: str) -> str:
    value = str(target or "").strip()
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return (parsed.hostname or value).strip().rstrip(".")


def _url(target: str) -> str:
    value = str(target or "").strip()
    return value if value.startswith(("http://", "https://")) else f"https://{value}"


def _status_for(tool_name: str, raw: Dict[str, Any]) -> str:
    explicit = str(raw.get("status", "")).upper()
    if explicit in {"COMPLETED", "WARNING", "FAILED", "TIMEOUT", "UNREACHABLE", "NOT_APPLICABLE"}:
        return explicit
    if raw.get("error"):
        detail = f"{raw.get('error')} {raw.get('details', '')}".lower()
        if "timeout" in detail or "timed out" in detail:
            return "TIMEOUT"
        if any(token in detail for token in ("connect", "unreachable", "resolution failed", "getaddrinfo")):
            return "UNREACHABLE"
        return "FAILED"
    if tool_name == "robots_txt_parse" and raw.get("exists") is False:
        return "NOT_APPLICABLE"
    if tool_name == "sitemap_parse" and (raw.get("exists") is False or raw.get("found") is False):
        return "NOT_APPLICABLE"
    if tool_name == "reverse_dns_lookup" and raw.get("hostnames") == []:
        return "NOT_APPLICABLE"
    return "COMPLETED"


def _summary_for(tool_name: str, raw: Dict[str, Any], status: str) -> str:
    if raw.get("summary"):
        return str(raw["summary"])
    if raw.get("error"):
        return str(raw.get("details") or raw.get("error"))
    if tool_name == "dns_lookup":
        return ", ".join(f"{key}: {len(raw.get(key, []) or [])}" for key in ("A", "AAAA", "MX", "NS", "TXT", "CNAME"))
    if tool_name == "reverse_dns_lookup":
        names = raw.get("hostnames", []) or []
        return f"Observed {len(names)} PTR hostname(s)." if names else "No PTR hostname was published for the tested address."
    if tool_name == "whois_lookup":
        return f"Public registration metadata retrieved; registrar: {raw.get('registrar') or 'not supplied'}."
    if tool_name == "ssl_check":
        return f"Certificate valid: {bool(raw.get('is_valid'))}; protocol: {raw.get('protocol') or 'unknown'}; days to expiry: {raw.get('days_until_expiry', 'unknown')}."
    if tool_name == "http_headers":
        return f"Checked {raw.get('total_critical_checked', 0)} configured headers; {raw.get('missing_count', 0)} were not observed."
    if tool_name == "cookie_analysis":
        return f"Observed {raw.get('total_cookies_found', 0)} cookie(s); {raw.get('vulnerable_cookies_count', 0)} omitted one or more reviewed attributes."
    if tool_name == "robots_txt_parse":
        return "robots.txt was not published at the tested location." if status == "NOT_APPLICABLE" else f"robots.txt published {raw.get('total_disallowed', 0)} non-empty Disallow directive(s)."
    if tool_name == "sitemap_parse":
        count = raw.get("total_urls") or raw.get("url_count") or len(raw.get("urls", []) or [])
        return f"Sitemap processing returned {count or 0} public URL(s)."
    if tool_name == "port_scan":
        ports = raw.get("open_ports", []) or []
        rendered = ", ".join(str(item.get("port")) for item in ports if isinstance(item, dict)) or "none"
        return f"Bounded TCP check observed {len(ports)} open port(s): {rendered}."
    if tool_name == "ddos_resilience_check":
        ev = raw.get("evidence", {}) if isinstance(raw.get("evidence"), dict) else {}
        return f"Passive edge-protection posture: {ev.get('posture', 'INCONCLUSIVE')}."
    return f"Worker finished with status {status}."


def _normalize_result(tool_name: str, raw_result: Any, duration: float, attempts: int) -> Dict[str, Any]:
    raw = dict(raw_result) if isinstance(raw_result, dict) else {"error": "Invalid worker result", "details": repr(raw_result)}
    status = _status_for(tool_name, raw)
    evidence = raw.get("evidence") if isinstance(raw.get("evidence"), dict) else raw
    return {
        "worker": tool_name,
        "status": status,
        "summary": _summary_for(tool_name, raw, status),
        "evidence": evidence,
        "error": str(raw.get("details") or raw.get("error")) if raw.get("error") else None,
        "duration_seconds": round(duration, 3),
        "attempts": attempts,
    }


def _finding_key(item: Dict[str, Any]) -> str:
    stable = json.dumps(
        {"worker": item.get("worker"), "title": item.get("title"), "evidence": item.get("evidence")},
        sort_keys=True, default=str,
    )
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def _looks_like_session_cookie(cookie: Dict[str, Any]) -> bool:
    name = str(cookie.get("name", "")).lower()
    return any(token in name for token in AUTH_COOKIE_TOKENS)


def _derive_findings(worker_results: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Turn retained worker evidence into conservative report observations.

    Only conditions with defensible security impact are marked actionable and
    supplied to CVSS.  Missing hardening headers, ordinary open web ports, DNS,
    WHOIS, robots/sitemap data, reverse DNS, and passive DDoS indicators remain
    informational rather than being promoted into fake vulnerabilities.
    """
    findings: List[Dict[str, Any]] = []

    def add(worker: str, title: str, severity: str, summary: str, meaning: str,
            recommendation: str = "", evidence: Any = None,
            actionable: bool = False, metrics: Optional[Dict[str, str]] = None) -> None:
        item: Dict[str, Any] = {
            "worker": worker,
            "title": title,
            "severity": severity,
            "summary": summary,
            "what_it_means": meaning,
            "recommendation": recommendation,
            "evidence": evidence,
            "actionable": actionable,
        }
        if actionable and metrics:
            item["cvss_metrics"] = metrics
        findings.append(item)

    for tool_name, result in worker_results.items():
        if tool_name not in EVIDENCE_TOOLS:
            continue
        status = str(result.get("status", "")).upper()
        evidence = result.get("evidence", {}) if isinstance(result.get("evidence"), dict) else {}

        if status in {"FAILED", "TIMEOUT", "UNREACHABLE"}:
            add(tool_name, f"{TOOL_GUIDANCE[tool_name]['label']} limitation", "INFORMATIONAL",
                result.get("summary", "Worker did not complete."),
                "This check did not produce sufficient evidence, so no vulnerability conclusion was drawn.",
                evidence={"status": status, "error": result.get("error")})
            continue

        if tool_name == "dns_lookup":
            add(tool_name, "Public DNS records", "INFORMATIONAL", result["summary"],
                "Public DNS records were queried as infrastructure context; their presence is not a vulnerability.", evidence=evidence)
        elif tool_name == "reverse_dns_lookup":
            add(tool_name, "Reverse DNS observation", "INFORMATIONAL", result["summary"],
                "PTR records provide public naming context and are not vulnerabilities by themselves.", evidence=evidence)
        elif tool_name == "whois_lookup":
            add(tool_name, "Public registration metadata", "INFORMATIONAL", result["summary"],
                "Public WHOIS/RDAP registration metadata is contextual information, not a vulnerability.", evidence=evidence)
        elif tool_name == "ssl_check":
            protocol = str(evidence.get("protocol") or "").upper().replace(" ", "")
            if evidence.get("is_valid") is False:
                add(tool_name, "TLS certificate validation failed", "MEDIUM",
                    "The observed TLS certificate failed validation.",
                    "An invalid, expired, untrusted, or hostname-mismatched certificate can weaken connection authenticity.",
                    "Replace/renew the certificate and verify hostname and trust-chain configuration.", evidence, True,
                    {"AV": "N", "AC": "H", "PR": "N", "UI": "R", "S": "U", "C": "L", "I": "L", "A": "N"})
            elif protocol in LEGACY_TLS_PROTOCOLS:
                add(tool_name, "Legacy TLS protocol observed", "MEDIUM",
                    f"The server negotiated legacy protocol {evidence.get('protocol')}.",
                    "Legacy SSL/TLS protocol versions provide weaker security than TLS 1.2/1.3.",
                    "Disable obsolete SSL/TLS versions and support TLS 1.2 or TLS 1.3.", evidence, True,
                    {"AV": "N", "AC": "H", "PR": "N", "UI": "N", "S": "U", "C": "L", "I": "L", "A": "N"})
            else:
                add(tool_name, "TLS configuration observed", "INFORMATIONAL", result["summary"],
                    "Certificate and negotiated TLS information were inspected; no scorable TLS issue was confirmed by this worker.", evidence=evidence)
        elif tool_name == "http_headers":
            missing = list(evidence.get("missing_headers") or [])
            summary = ("Recommended browser-security headers were not observed: " + ", ".join(missing) + ".") if missing else "All configured HTTP security-header checks were observed."
            add(tool_name, "HTTP security-header baseline", "INFORMATIONAL", summary,
                "Header presence is a hardening observation. Missing headers are not assigned CVSS without application-specific exploitability and impact.",
                "Review missing headers and configure those appropriate for the application." if missing else "", evidence=evidence)
        elif tool_name == "cookie_analysis":
            cookies = evidence.get("cookies", []) if isinstance(evidence.get("cookies"), list) else []
            actionable = 0
            for cookie in cookies:
                if not isinstance(cookie, dict) or not _looks_like_session_cookie(cookie):
                    continue
                missing = {str(flag).lower() for flag in (cookie.get("missing_flags") or [])}
                sensitive_missing = missing & {"secure", "httponly"}
                if not sensitive_missing:
                    continue
                actionable += 1
                flags = ", ".join(sorted(flag.title() for flag in sensitive_missing))
                add(tool_name, "Potential session-cookie attribute weakness", "LOW",
                    f"Cookie '{cookie.get('name') or '(unnamed)'} appears session-related and omitted {flags}.",
                    "A likely session/authentication cookie omitted a transport or script-access protection; application context should still be validated.",
                    "Confirm the cookie purpose and apply Secure/HttpOnly where appropriate; review SameSite requirements.", cookie, True,
                    {"AV": "N", "AC": "H", "PR": "N", "UI": "R", "S": "U", "C": "L", "I": "L", "A": "N"})
            if actionable == 0:
                add(tool_name, "Cookie attribute observation", "INFORMATIONAL", result["summary"],
                    "No clearly session-related cookie with a scorable missing Secure/HttpOnly condition was confirmed in the unauthenticated response.", evidence=evidence)
        elif tool_name == "robots_txt_parse":
            add(tool_name, "robots.txt observation", "INFORMATIONAL", result["summary"],
                "robots.txt is a public crawler-control artifact; listed paths are not vulnerabilities by themselves.", evidence=evidence)
        elif tool_name == "sitemap_parse":
            add(tool_name, "Sitemap observation", "INFORMATIONAL", result["summary"],
                "A sitemap is a public indexing artifact; its presence or absence is not a vulnerability by itself.", evidence=evidence)
        elif tool_name == "port_scan":
            open_ports = evidence.get("open_ports", []) if isinstance(evidence.get("open_ports"), list) else []
            extras = [p for p in open_ports if isinstance(p, dict) and p.get("port") not in EXPECTED_WEB_PORTS]
            if extras:
                rendered = ", ".join(f"{p.get('port')}/{p.get('service') or 'unknown'}" for p in extras)
                add(tool_name, "Additional public services observed", "INFORMATIONAL",
                    f"The bounded port check observed additional public services: {rendered}.",
                    "A reachable service is not automatically a vulnerability; ownership, necessity, authentication and patch status require validation.",
                    "Confirm that each additional public service is intended and maintained.", evidence=evidence)
            else:
                add(tool_name, "Bounded port observation", "INFORMATIONAL", result["summary"],
                    "Open web ports such as 80/443 are expected for public websites and are not vulnerabilities by themselves.", evidence=evidence)
        elif tool_name == "ddos_resilience_check":
            add(tool_name, "Passive edge-protection indicators", "INFORMATIONAL", result["summary"],
                "This passive check can observe public CDN/WAF/edge indicators but cannot prove DDoS resistance or absence of protection.", evidence=evidence)

    unique: Dict[str, Dict[str, Any]] = {}
    for finding in findings:
        unique.setdefault(_finding_key(finding), finding)
    return list(unique.values())


def _cvss_items(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for finding in findings:
        if finding.get("worker") in CVSS_EXCLUDED_WORKERS:
            continue
        metrics = finding.get("cvss_metrics")
        if finding.get("actionable") is not True or not isinstance(metrics, dict):
            continue
        evidence = finding.get("evidence")
        if evidence in (None, "", {}, []):
            continue
        items.append({
            "finding": finding.get("title") or finding.get("summary") or "Finding",
            "evidence": json.dumps(evidence, default=str, ensure_ascii=False)[:2000],
            "recommendation": finding.get("recommendation", ""),
            "base_metrics": metrics,
        })
    return items


def _worker_args(tool_name: str, requested: Dict[str, Any], target: str,
                 worker_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    host = _host(target)
    url = _url(target)
    if tool_name == "reverse_dns_lookup":
        dns = worker_results.get("dns_lookup", {}).get("evidence", {})
        addresses = list(dns.get("A") or []) + list(dns.get("AAAA") or []) if isinstance(dns, dict) else []
        return {"ip": addresses[0]} if addresses else {}
    if tool_name == "sitemap_parse":
        return {"url": url}
    if tool_name in {"http_headers", "cookie_analysis", "robots_txt_parse", "ddos_resilience_check"}:
        return {"target": url}
    if tool_name == "ssl_check":
        try:
            port = int(requested.get("port") or 443)
        except (TypeError, ValueError):
            port = 443
        return {"target": host, "port": port}
    if tool_name == "port_scan":
        return {"target": host, "ports": requested.get("ports")}
    return {"target": host}


def _coverage_entry(tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "worker": TOOL_GUIDANCE[tool_name]["label"],
        "tool_name": tool_name,
        "status": result.get("status", "FAILED"),
        "duration": float(result.get("duration_seconds", 0.0) or 0.0),
        "result": result.get("summary", ""),
    }


def run_scan(target: str, max_iterations: int = DEFAULT_MAX_ITERATIONS,
             on_progress: Optional[Callable[..., None]] = None) -> Dict[str, Any]:
    """Run one authorized Gemini-guided assessment with all 12 stages accounted for."""
    client = GeminiClient()
    scan_started = time.monotonic()
    history: List[types.Content] = [
        types.Content(role="user", parts=[types.Part.from_text(text=(
            f"Begin the authorized SentinelScan assessment for target: {target}. "
            "Choose the order of the ten evidence workers dynamically. Every evidence category must be accounted for before CVSS. "
            "Use only real worker evidence. After evidence collection, call calculate_cvss once, then generate_report once."
        ))])
    ]

    worker_results: Dict[str, Dict[str, Any]] = {}
    coverage: Dict[str, Dict[str, Any]] = {}
    failure_counts: Dict[str, int] = {}
    resolved_evidence: Set[str] = set()
    cvss_completed = False
    cvss_call_count = 0
    cvss_scores: List[Dict[str, Any]] = []

    for iteration in range(1, max_iterations + 1):
        try:
            response = client.generate(history, use_cache=False)
        except Exception as exc:
            logger.exception("Gemini orchestration failed")
            return {
                "status": "incomplete", "error": f"AI orchestration failed: {exc}", "iterations": iteration,
                "worker_results": list(worker_results.values()), "findings": _derive_findings(worker_results),
                "cvss_scores": cvss_scores, "worker_coverage": list(coverage.values()),
                "cvss_call_count": cvss_call_count,
            }

        if response.get("model_content") is not None:
            history.append(response["model_content"])

        if response.get("type") != "tool_call":
            remaining = sorted(EVIDENCE_TOOLS - resolved_evidence)
            nudge = f"Call the next missing evidence worker now. Remaining: {remaining}." if remaining else (
                "All evidence categories are accounted for. Call calculate_cvss exactly once." if not cvss_completed else "CVSS is complete. Call generate_report now."
            )
            history.append(types.Content(role="user", parts=[types.Part.from_text(text=nudge)]))
            continue

        tool_name = str(response.get("tool_name") or "")
        requested = dict(response.get("tool_args") or {})
        model_reason = str(requested.pop("reasoning", "") or response.get("reasoning", "")).strip()

        if tool_name not in ALLOWED_TOOLS:
            history.append(types.Content(role="user", parts=[types.Part.from_function_response(
                name=tool_name or "unknown_tool", response={"error": "Tool is not permitted."})]))
            continue

        guidance = TOOL_GUIDANCE[tool_name]
        reason = model_reason or guidance["reason"]

        if tool_name == "calculate_cvss":
            if cvss_completed:
                history.append(types.Content(role="user", parts=[types.Part.from_function_response(
                    name=tool_name, response={"error": "CVSS phase already completed; duplicate request ignored.", "scores": cvss_scores})]))
                continue
            missing = sorted(EVIDENCE_TOOLS - resolved_evidence)
            if missing:
                history.append(types.Content(role="user", parts=[types.Part.from_function_response(
                    name=tool_name, response={"error": "Evidence gathering is incomplete.", "missing_evidence_tools": missing})]))
                continue

            findings = _derive_findings(worker_results)
            items = _cvss_items(findings)
            _emit_progress(on_progress, iteration=iteration, max_iterations=max_iterations, tool_name=tool_name,
                           phase="selected", reasoning=reason, action=guidance["action"])
            started = time.monotonic()
            raw = dispatch_tool(tool_name, {"items": items})
            duration = time.monotonic() - started
            if isinstance(raw, dict) and raw.get("error"):
                return {"status": "incomplete", "error": f"CVSS worker failed: {raw.get('details') or raw.get('error')}",
                        "iterations": iteration, "worker_results": list(worker_results.values()), "findings": findings,
                        "cvss_scores": [], "worker_coverage": list(coverage.values()), "cvss_call_count": cvss_call_count}
            cvss_call_count += 1
            cvss_completed = True
            cvss_scores = list(raw.get("scores") or []) if isinstance(raw, dict) else []
            cvss_result = {
                "worker": tool_name, "status": "COMPLETED",
                "summary": f"CVSS evaluated {len(items)} actionable finding(s); {len(cvss_scores)} score(s) produced.",
                "evidence": {"input_count": len(items), "scores": cvss_scores}, "error": None,
                "duration_seconds": round(duration, 3), "attempts": 1,
            }
            coverage[tool_name] = _coverage_entry(tool_name, cvss_result)
            _emit_progress(on_progress, iteration=iteration, max_iterations=max_iterations, tool_name=tool_name,
                           phase="completed", reasoning=reason, action=guidance["action"],
                           summary=cvss_result["summary"], status="COMPLETED", duration=duration)
            history.append(types.Content(role="user", parts=[types.Part.from_function_response(
                name=tool_name, response={"scores": cvss_scores, "scored_count": len(cvss_scores),
                                          "input_count": len(items), "instruction": "CVSS is complete. Call generate_report exactly once."})]))
            continue

        if tool_name == "generate_report":
            if not cvss_completed:
                missing = sorted(EVIDENCE_TOOLS - resolved_evidence)
                history.append(types.Content(role="user", parts=[types.Part.from_function_response(
                    name=tool_name, response={"error": "Report generation is gated until all evidence categories and CVSS are complete.",
                                              "missing_evidence_tools": missing, "cvss_completed": cvss_completed})]))
                continue

            findings = _derive_findings(worker_results)
            # A report that exists necessarily completed its own generation stage.
            report_coverage = list(coverage.values()) + [{
                "worker": TOOL_GUIDANCE["generate_report"]["label"], "tool_name": "generate_report",
                "status": "COMPLETED", "duration": 0.0,
                "result": "JSON and PDF report generation completed successfully.",
            }]
            _emit_progress(on_progress, iteration=iteration, max_iterations=max_iterations, tool_name=tool_name,
                           phase="selected", reasoning=reason, action=guidance["action"])
            started = time.monotonic()
            report = generate_report(
                target=target, findings=findings, cvss_scores=cvss_scores,
                worker_coverage=report_coverage, scan_duration=time.monotonic() - scan_started,
            )
            duration = time.monotonic() - started
            if report.get("error"):
                return {"status": "incomplete", "error": report.get("details") or report["error"],
                        "iterations": iteration, "worker_results": list(worker_results.values()), "findings": findings,
                        "cvss_scores": cvss_scores, "worker_coverage": report_coverage, "cvss_call_count": cvss_call_count}
            if not all(report.get(key) and os.path.exists(report[key]) for key in ("pdf_path", "json_path")):
                return {"status": "incomplete", "error": "Report files were not both created.", "iterations": iteration,
                        "worker_results": list(worker_results.values()), "findings": findings, "cvss_scores": cvss_scores,
                        "worker_coverage": report_coverage, "cvss_call_count": cvss_call_count}
            report_coverage[-1]["duration"] = round(duration, 3)
            _emit_progress(on_progress, iteration=iteration, max_iterations=max_iterations, tool_name=tool_name,
                           phase="completed", reasoning=reason, action=guidance["action"],
                           summary="JSON and PDF reports were generated and verified.", status="COMPLETED", duration=duration)
            return {
                "status": "complete", "report": report, "iterations": iteration,
                "reason": "Gemini-guided 12-stage assessment completed",
                "worker_results": list(worker_results.values()), "findings": findings, "cvss_scores": cvss_scores,
                "worker_coverage": report_coverage, "cvss_call_count": cvss_call_count,
                "stage_count": 12,
            }

        if cvss_completed:
            history.append(types.Content(role="user", parts=[types.Part.from_function_response(
                name=tool_name, response={"error": "Evidence collection is closed after CVSS."})]))
            continue

        if tool_name in resolved_evidence:
            history.append(types.Content(role="user", parts=[types.Part.from_function_response(
                name=tool_name, response={"error": f"{tool_name} is already accounted for.",
                                          "remaining_evidence_tools": sorted(EVIDENCE_TOOLS - resolved_evidence)})]))
            continue

        attempts = failure_counts.get(tool_name, 0) + 1
        args = _worker_args(tool_name, requested, target, worker_results)
        _emit_progress(on_progress, iteration=iteration, max_iterations=max_iterations, tool_name=tool_name,
                       phase="selected", reasoning=reason, action=guidance["action"])

        if tool_name == "reverse_dns_lookup" and not args.get("ip"):
            raw: Dict[str, Any] = {
                "status": "NOT_APPLICABLE",
                "summary": "Reverse DNS was not applicable because DNS did not return a usable A/AAAA address.",
                "evidence": {"hostnames": [], "reason": "No DNS address prerequisite"},
                "error": None,
            }
            duration = 0.0
        else:
            started = time.monotonic()
            raw = dispatch_tool(tool_name, args)
            duration = time.monotonic() - started

        normalized = _normalize_result(tool_name, raw, duration, attempts)
        worker_results[tool_name] = normalized
        coverage[tool_name] = _coverage_entry(tool_name, normalized)

        retryable = normalized["status"] in {"TIMEOUT", "UNREACHABLE"}
        if normalized["status"] in {"FAILED", "TIMEOUT", "UNREACHABLE"}:
            failure_counts[tool_name] = failure_counts.get(tool_name, 0) + 1
            if not retryable or failure_counts[tool_name] >= 2:
                resolved_evidence.add(tool_name)
        else:
            failure_counts[tool_name] = 0
            resolved_evidence.add(tool_name)

        _emit_progress(on_progress, iteration=iteration, max_iterations=max_iterations, tool_name=tool_name,
                       phase="completed", reasoning=reason, action=guidance["action"], summary=normalized["summary"],
                       status=normalized["status"], duration=duration)

        remaining = sorted(EVIDENCE_TOOLS - resolved_evidence)
        if normalized["status"] in {"TIMEOUT", "UNREACHABLE"} and tool_name not in resolved_evidence:
            instruction = f"{tool_name} had a transient failure and may be retried once. Otherwise continue with a missing evidence worker: {remaining}."
        elif remaining:
            instruction = f"Select the next missing evidence worker. Remaining: {remaining}."
        else:
            instruction = "All ten evidence categories are now accounted for. Call calculate_cvss exactly once."

        history.append(types.Content(role="user", parts=[types.Part.from_function_response(
            name=tool_name, response={"worker_result": normalized,
                                      "accounted_evidence_tools": sorted(resolved_evidence),
                                      "remaining_evidence_tools": remaining,
                                      "instruction": instruction})]))

    return {
        "status": "incomplete",
        "error": "Reached the maximum AI-agent iteration limit before all 12 stages completed.",
        "iterations": max_iterations,
        "worker_results": list(worker_results.values()),
        "findings": _derive_findings(worker_results),
        "cvss_scores": cvss_scores,
        "worker_coverage": list(coverage.values()),
        "cvss_call_count": cvss_call_count,
    }
