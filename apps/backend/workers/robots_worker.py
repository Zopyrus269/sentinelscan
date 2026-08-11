"""
robots.txt Security Worker.

Fetches and parses a target's robots.txt to extract Disallow directive
paths, which can reveal sensitive or hidden site areas.
"""

import urllib.parse
from typing import Dict, Any
import requests
import logging
from apps.backend.utils.browser_fetcher import fetch_with_browser


def robots_worker(target: str) -> Dict[str, Any]:
    """
    Fetches target's /robots.txt and parses out all Disallow: paths.

    Args:
        target: The URL to inspect (e.g. "https://example.com").

    Returns:
        On success: {"robots_url": "...", "exists": bool, "status_code": int,
                      "disallowed_paths": [...], "total_disallowed": int}
        On failure: {"error": "...", "details": "..."}
    """
    parsed = urllib.parse.urlparse(target)
    if not parsed.scheme or not parsed.netloc:
        target = "http://" + target
        parsed = urllib.parse.urlparse(target)
    robots_url = urllib.parse.urljoin(f"{parsed.scheme}://{parsed.netloc}", "/robots.txt")

    try:
        response = requests.get(
            robots_url,
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

        if response.status_code != 200:
            return {
                "robots_url": robots_url,
                "exists": False,
                "status_code": response.status_code,
                "disallowed_paths": [],
                "total_disallowed": 0,
            }

        content = response.text
        disallowed_paths = []
        for line in content.splitlines():
            clean_line = line.split("#")[0].strip()
            if not clean_line:
                continue
            if clean_line.lower().startswith("disallow:"):
                parts = clean_line.split(":", 1)
                if len(parts) > 1:
                    path = parts[1].strip()
                    if path:
                        disallowed_paths.append(path)

        unique_disallowed = list(dict.fromkeys(disallowed_paths))

        return {
            "robots_url": robots_url,
            "exists": True,
            "status_code": response.status_code,
            "disallowed_paths": unique_disallowed,
            "total_disallowed": len(unique_disallowed),
        }

    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        logging.warning("Requests timed out. Falling back to Playwright browser...")
        try:
            browser_data = fetch_with_browser(robots_url)
            text = browser_data.get("text", "")
            
            disallowed_paths = []
            allowed_paths = []
            sitemap_urls = []
            
            if text:
                for line in text.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                        
                    lower_line = line.lower()
                    if lower_line.startswith("disallow:"):
                        path = line.split(":", 1)[1].strip()
                        if path:
                            disallowed_paths.append(path)
                    elif lower_line.startswith("allow:"):
                        path = line.split(":", 1)[1].strip()
                        if path:
                            allowed_paths.append(path)
                    elif lower_line.startswith("sitemap:"):
                        smap = line.split(":", 1)[1].strip()
                        if smap:
                            sitemap_urls.append(smap)
                            
            return {
                "has_robots_txt": bool(text.strip()),
                "disallowed_count": len(disallowed_paths),
                "allowed_count": len(allowed_paths),
                "disallowed_paths": disallowed_paths[:20],
                "sitemaps": sitemap_urls,
            }
        except Exception as browser_err:
            return {"error": "Browser fallback failed", "details": str(browser_err)}
    except requests.exceptions.RequestException as e:
        return {"error": "HTTP request failed", "details": str(e)}
    except Exception as e:
        return {"error": "Unexpected error", "details": str(e)}
