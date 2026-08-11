"""
HTTP Headers Security Worker.

Analyzes a target URL's HTTP response headers for missing security-critical
headers (HSTS, CSP, X-Frame-Options, etc.).
"""

from typing import Dict, Any
import requests
import logging
from apps.backend.utils.browser_fetcher import fetch_with_browser

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
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            },
            timeout=45,
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

    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        logging.warning("Requests timed out. Falling back to Playwright browser...")
        try:
            browser_data = fetch_with_browser(target)
            resp_headers = browser_data["headers"]

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
        except Exception as browser_err:
            return {"error": "Browser fallback failed", "details": str(browser_err)}
    except requests.exceptions.RequestException as e:
        return {"error": "HTTP request failed", "details": str(e)}
    except Exception as e:
        return {"error": "Unexpected error", "details": str(e)}
