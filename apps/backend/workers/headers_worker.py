"""
HTTP Headers Security Worker.

Analyzes a target URL's HTTP response headers for missing security-critical
headers (HSTS, CSP, X-Frame-Options, etc.).
"""

from typing import Dict, Any
import requests

CRITICAL_HEADERS = [
    "Strict-Transport-Security",
    "X-Frame-Options",
    "X-Content-Type-Options",
    "Content-Security-Policy",
    "Referrer-Policy",
    "Permissions-Policy",
]


def headers_worker(target: str) -> Dict[str, Any]:
    """
    Fetches target and checks its response headers against a critical list.

    Args:
        target: The URL to inspect (e.g. "https://example.com").

    Returns:
        On success: {"missing_headers": [...], "present_headers": {...},
                      "total_critical_checked": int, "missing_count": int}
        On failure: {"error": "...", "details": "..."}
    """
    try:
        response = requests.get(
            target,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            timeout=15,
            allow_redirects=True,
        )
        resp_headers = response.headers

        missing = []
        present = {}
        for header in CRITICAL_HEADERS:
            if header in resp_headers:
                present[header] = resp_headers[header]
            else:
                missing.append(header)

        return {
            "missing_headers": missing,
            "present_headers": present,
            "total_critical_checked": len(CRITICAL_HEADERS),
            "missing_count": len(missing),
        }

    except requests.exceptions.Timeout:
        return {"error": "Request timed out.", "details": "Timeout"}
    except requests.exceptions.ConnectionError as e:
        return {"error": "Failed to connect to target URL.", "details": str(e)}
    except requests.exceptions.RequestException as e:
        return {"error": "HTTP request failed", "details": str(e)}
    except Exception as e:
        return {"error": "Unexpected error", "details": str(e)}
