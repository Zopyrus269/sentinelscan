"""
Cookies Security Worker.

Inspects a target URL's HTTP response cookies (and raw Set-Cookie headers
as a fallback) for missing Secure and HttpOnly flags.
"""

from typing import Dict, Any, List
import logging
import requests
from apps.backend.utils.browser_fetcher import fetch_with_browser


def cookie_worker(target: str) -> Dict[str, Any]:
    """
    Fetches target and inspects its cookies for Secure/HttpOnly flags.

    Args:
        target: The URL to inspect (e.g. "https://example.com").

    Returns:
        On success: {"total_cookies_found": int, "vulnerable_cookies_count": int,
                      "cookies": [{"name": ..., "secure": bool, "http_only": bool,
                                    "missing_flags": [...], "is_vulnerable": bool}, ...]}
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

        cookie_findings: List[Dict[str, Any]] = []
        flagged_count = 0

        jar_cookies = response.cookies

        raw_set_cookie_headers: List[str] = []
        try:
            if (
                response.raw
                and hasattr(response.raw, "headers")
                and callable(getattr(response.raw.headers, "getlist", None))
            ):
                getlist_val = response.raw.headers.getlist("Set-Cookie")
                if isinstance(getlist_val, list):
                    raw_set_cookie_headers = getlist_val
        except Exception as e:
            logging.warning(f"Error encountered: {e}")

        if not raw_set_cookie_headers and "Set-Cookie" in response.headers:
            header_val = response.headers.get("Set-Cookie")
            if isinstance(header_val, str):
                raw_set_cookie_headers = [header_val]

        if jar_cookies:
            for cookie in jar_cookies:
                is_http_only = (
                    cookie.has_nonstandard_attr("HttpOnly")
                    or cookie.has_nonstandard_attr("httponly")
                    or "HttpOnly" in cookie._rest
                    or "httponly" in cookie._rest
                )
                is_secure = cookie.secure

                missing_flags = []
                if not is_secure:
                    missing_flags.append("Secure")
                if not is_http_only:
                    missing_flags.append("HttpOnly")

                cookie_info = {
                    "name": cookie.name,
                    "domain": cookie.domain,
                    "path": cookie.path,
                    "secure": is_secure,
                    "http_only": is_http_only,
                    "missing_flags": missing_flags,
                    "is_vulnerable": len(missing_flags) > 0,
                }
                if cookie_info["is_vulnerable"]:
                    flagged_count += 1
                cookie_findings.append(cookie_info)

        elif raw_set_cookie_headers:
            for header_str in raw_set_cookie_headers:
                parts = [p.strip() for p in header_str.split(";")]
                cookie_name_val = parts[0] if parts else ""
                name = (
                    cookie_name_val.split("=")[0].strip()
                    if "=" in cookie_name_val
                    else cookie_name_val
                )
                lower_directives = [p.lower() for p in parts[1:]]
                is_secure = "secure" in lower_directives
                is_http_only = "httponly" in lower_directives

                missing_flags = []
                if not is_secure:
                    missing_flags.append("Secure")
                if not is_http_only:
                    missing_flags.append("HttpOnly")

                cookie_info = {
                    "name": name,
                    "secure": is_secure,
                    "http_only": is_http_only,
                    "missing_flags": missing_flags,
                    "is_vulnerable": len(missing_flags) > 0,
                }
                if cookie_info["is_vulnerable"]:
                    flagged_count += 1
                cookie_findings.append(cookie_info)

        return {
            "total_cookies_found": len(cookie_findings),
            "vulnerable_cookies_count": flagged_count,
            "cookies": cookie_findings,
        }

    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        logging.warning("Requests timed out. Falling back to Playwright browser...")
        try:
            browser_data = fetch_with_browser(target)
            
            cookie_findings = []
            flagged_count = 0
            
            for cookie in browser_data.get("cookies", []):
                is_secure = cookie.get("secure", False)
                is_http_only = cookie.get("httpOnly", False)
                
                missing_flags = []
                if not is_secure:
                    missing_flags.append("Secure")
                if not is_http_only:
                    missing_flags.append("HttpOnly")
                    
                cookie_info = {
                    "name": cookie.get("name", ""),
                    "domain": cookie.get("domain", ""),
                    "path": cookie.get("path", ""),
                    "secure": is_secure,
                    "http_only": is_http_only,
                    "missing_flags": missing_flags,
                    "is_vulnerable": len(missing_flags) > 0,
                }
                if cookie_info["is_vulnerable"]:
                    flagged_count += 1
                cookie_findings.append(cookie_info)
                
            return {
                "total_cookies_found": len(cookie_findings),
                "vulnerable_cookies_count": flagged_count,
                "cookies": cookie_findings,
            }
        except Exception as browser_err:
            return {"error": "Browser fallback failed", "details": str(browser_err)}
    except requests.exceptions.RequestException as e:
        return {"error": "HTTP request failed", "details": str(e)}
    except Exception as e:
        return {"error": "Unexpected error", "details": str(e)}
