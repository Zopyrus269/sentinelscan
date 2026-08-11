"""Passive DDoS/CDN/WAF resilience indicator worker.

This worker is deliberately non-intrusive. It does not generate attack traffic,
perform load/stress testing, flood the target, or attempt exploitation. It only
inspects public DNS and HTTP metadata for externally observable indicators of
CDN, WAF, reverse-proxy, edge-network, rate-limit, or challenge infrastructure.

Absence of an observable indicator is NOT proof that DDoS protection is absent.
The result is informational and must not be treated as a CVSS vulnerability by
itself.
"""

from __future__ import annotations

import socket
import time
from typing import Any, Dict, List, Set
from urllib.parse import urlparse
import logging

import requests
from apps.backend.utils.browser_fetcher import fetch_with_browser


WORKER_NAME = "ddos_resilience_check"
USER_AGENT = "SentinelScan/1.0 (+authorized passive assessment)"
CONNECT_TIMEOUT_SECONDS = 5
READ_TIMEOUT_SECONDS = 10
MAX_DNS_ADDRESSES = 12

PROVIDER_SIGNATURES: Dict[str, Dict[str, Any]] = {
    "cloudflare": {
        "headers": {
            "server": ["cloudflare"],
            "cf-ray": None,
            "cf-cache-status": None,
        },
        "dns": ["cloudflare"],
    },
    "akamai": {
        "headers": {
            "server": ["akamaighost"],
            "x-akamai-transformed": None,
        },
        "dns": ["akamaiedge", "edgesuite", "akamai"],
    },
    "fastly": {
        "headers": {
            "x-served-by": None,
            "via": ["varnish"],
        },
        "dns": ["fastly"],
    },
    "cloudfront": {
        "headers": {
            "x-amz-cf-id": None,
            "x-amz-cf-pop": None,
        },
        "dns": ["cloudfront"],
    },
    "imperva": {
        "headers": {
            "x-iinfo": None,
        },
        "cookies": ["visid_incap", "incap_ses"],
        "dns": ["incapdns", "imperva"],
    },
    "sucuri": {
        "headers": {
            "x-sucuri-id": None,
            "x-sucuri-cache": None,
        },
        "dns": ["sucuri"],
    },
}

RELEVANT_HEADERS = {
    "server",
    "via",
    "x-cache",
    "x-cache-hits",
    "x-served-by",
    "cf-ray",
    "cf-cache-status",
    "x-amz-cf-id",
    "x-amz-cf-pop",
    "x-akamai-transformed",
    "x-sucuri-id",
    "x-sucuri-cache",
    "x-iinfo",
    "retry-after",
    "ratelimit-limit",
    "ratelimit-remaining",
    "ratelimit-reset",
    "x-ratelimit-limit",
    "x-ratelimit-remaining",
    "x-ratelimit-reset",
}

RATE_LIMIT_HEADERS = {
    "retry-after",
    "ratelimit-limit",
    "ratelimit-remaining",
    "ratelimit-reset",
    "x-ratelimit-limit",
    "x-ratelimit-remaining",
    "x-ratelimit-reset",
}

CHALLENGE_MARKERS = (
    "checking your browser",
    "verify you are human",
    "access denied",
    "captcha",
    "too many requests",
    "rate limit",
    "security check",
)


def _normalize_url(target: str) -> str:
    value = str(target or "").strip()
    if not value:
        raise ValueError("Target is required")
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    parsed = urlparse(value)
    if not parsed.hostname:
        raise ValueError("Target must contain a valid hostname")
    return value


def _collect_dns(hostname: str, evidence: Dict[str, Any]) -> None:
    try:
        results = socket.getaddrinfo(hostname, 443, proto=socket.IPPROTO_TCP)
        addresses = sorted({item[4][0] for item in results})[:MAX_DNS_ADDRESSES]
        evidence["dns_addresses"] = addresses

        reverse_names: List[str] = []
        for address in addresses:
            try:
                name = socket.gethostbyaddr(address)[0]
                if name:
                    reverse_names.append(name.lower())
            except (socket.herror, socket.gaierror, OSError):
                continue
        evidence["dns_hostnames"] = sorted(set(reverse_names))
    except OSError as exc:
        evidence["limitations"].append(f"DNS metadata unavailable: {exc}")


def _detect_providers(headers: Dict[str, str], cookie_names: Set[str], dns_hostnames: List[str]) -> List[str]:
    detected: List[str] = []
    dns_text = " ".join(str(x).lower() for x in dns_hostnames)

    for provider, signatures in PROVIDER_SIGNATURES.items():
        matched = False

        for header_name, expected_values in signatures.get("headers", {}).items():
            name = str(header_name).lower()
            if name not in headers:
                continue
            if expected_values is None:
                matched = True
                break
            observed = headers[name].lower()
            if any(str(token).lower() in observed for token in expected_values):
                matched = True
                break

        if not matched:
            for cookie_prefix in signatures.get("cookies", []):
                prefix = str(cookie_prefix).lower()
                if any(cookie.startswith(prefix) for cookie in cookie_names):
                    matched = True
                    break

        if not matched and any(str(token).lower() in dns_text for token in signatures.get("dns", [])):
            matched = True

        if matched:
            detected.append(provider)

    return sorted(set(detected))


def _challenge_observed(response: requests.Response) -> bool:
    if response.status_code not in {403, 429, 503}:
        return False
    try:
        body = response.text[:4000].lower()
    except Exception:
        body = ""
    return any(marker in body for marker in CHALLENGE_MARKERS)


def _result(status: str, summary: str, evidence: Dict[str, Any], error: str | None, started: float, attempts: int) -> Dict[str, Any]:
    return {
        "worker": WORKER_NAME,
        "status": status,
        "summary": summary,
        "evidence": evidence,
        # Intentionally empty. Passive absence of public CDN/WAF indicators
        # is not a confirmed vulnerability and must not receive CVSS.
        "findings": [],
        "error": error,
        "duration_seconds": round(time.monotonic() - started, 3),
        "attempts": attempts,
    }


def ddos_resilience_check(target: str) -> Dict[str, Any]:
    """Inspect passive public indicators of DDoS/CDN/WAF resilience infrastructure."""
    started = time.monotonic()
    attempts = 0
    evidence: Dict[str, Any] = {
        "target": target,
        "final_url": None,
        "http_status": None,
        "posture": "INCONCLUSIVE",
        "cdn_or_waf_detected": None,
        "provider_indicators": [],
        "headers_checked": {},
        "rate_limit_indicators": {},
        "dns_addresses": [],
        "dns_hostnames": [],
        "challenge_observed": False,
        "limitations": [
            "Passive observation only: this worker does not test traffic capacity, mitigation strength, availability, or resistance to a real denial-of-service attack."
        ],
    }

    try:
        url = _normalize_url(target)
        hostname = urlparse(url).hostname or ""
        attempts += 1
        _collect_dns(hostname, evidence)

        response = requests.get(
            url,
            timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
            allow_redirects=True,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )

        headers = {str(k).lower(): str(v) for k, v in response.headers.items()}
        evidence["final_url"] = response.url
        evidence["http_status"] = response.status_code
        evidence["headers_checked"] = {k: v for k, v in headers.items() if k in RELEVANT_HEADERS}
        evidence["rate_limit_indicators"] = {k: v for k, v in headers.items() if k in RATE_LIMIT_HEADERS}

        cookie_names = {str(cookie.name).lower() for cookie in response.cookies}
        providers = _detect_providers(headers, cookie_names, evidence["dns_hostnames"])
        evidence["provider_indicators"] = providers
        evidence["challenge_observed"] = _challenge_observed(response)

        if evidence["challenge_observed"]:
            evidence["limitations"].append(
                f"A passive challenge/rate-limit style response was observed (HTTP {response.status_code}); the origin application may not be directly observable."
            )

        if providers:
            evidence["posture"] = "DETECTED"
            evidence["cdn_or_waf_detected"] = True
            summary = "Public CDN/WAF/reverse-proxy indicators observed: " + ", ".join(providers) + "."
        else:
            evidence["posture"] = "NOT_OBSERVED"
            evidence["cdn_or_waf_detected"] = False
            evidence["limitations"].append(
                "No public CDN/WAF signature was observed. This does not prove that DDoS protection is absent; upstream or private controls may not be externally identifiable."
            )
            summary = "No public CDN/WAF indicators were observed. This does not prove that DDoS protection is absent."

        return _result("COMPLETED", summary, evidence, None, started, attempts)

    except (requests.Timeout, requests.ConnectionError):
        logging.warning("Requests timed out. Falling back to Playwright browser...")
        try:
            browser_data = fetch_with_browser(url)
            
            evidence["http_status"] = browser_data.get("status_code", 0)
            headers = {str(k).lower(): str(v) for k, v in browser_data.get("headers", {}).items()}
            evidence["headers_checked"] = {k: v for k, v in headers.items() if k in RELEVANT_HEADERS}
            evidence["rate_limit_indicators"] = {k: v for k, v in headers.items() if k in RATE_LIMIT_HEADERS}
            
            cookie_names = {str(cookie.get("name", "")).lower() for cookie in browser_data.get("cookies", [])}
            providers = _detect_providers(headers, cookie_names, evidence["dns_hostnames"])
            evidence["provider_indicators"] = providers
            
            text_body = browser_data.get("text", "").lower()
            evidence["challenge_observed"] = any(marker in text_body for marker in CHALLENGE_MARKERS)
            
            if evidence["challenge_observed"]:
                evidence["limitations"].append(
                    f"A passive challenge/rate-limit style response was observed via browser; the origin application may not be directly observable."
                )
                
            if providers:
                evidence["posture"] = "DETECTED"
                evidence["cdn_or_waf_detected"] = True
                summary = "Public CDN/WAF/reverse-proxy indicators observed: " + ", ".join(providers) + "."
            else:
                evidence["posture"] = "NOT_OBSERVED"
                evidence["cdn_or_waf_detected"] = False
                summary = "No public CDN/WAF indicators were observed. This does not prove that DDoS protection is absent."

            return _result("COMPLETED", summary, evidence, None, started, attempts)
        except Exception as browser_err:
            return _result("FAILED", "Browser fallback failed", evidence, str(browser_err), started, attempts)
    except requests.RequestException as exc:
        return _result(
            "UNREACHABLE",
            "The public HTTP service could not be inspected for passive DDoS/CDN indicators; resilience posture is inconclusive.",
            evidence,
            str(exc),
            started,
            attempts,
        )
    except ValueError as exc:
        return _result("FAILED", "Passive DDoS/CDN indicator check could not start because the target was invalid.", evidence, str(exc), started, attempts)
    except Exception as exc:
        return _result("FAILED", "Passive DDoS/CDN indicator analysis failed.", evidence, str(exc), started, attempts)
