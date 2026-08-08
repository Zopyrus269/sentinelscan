"""
robots.txt Security Worker.

Fetches and parses a target's robots.txt to extract Disallow directive
paths, which can reveal sensitive or hidden site areas.
"""

import urllib.parse
from typing import Dict, Any
import requests


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
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            timeout=15,
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

    except requests.exceptions.Timeout:
        return {"error": "Request timed out.", "details": "Timeout"}
    except requests.exceptions.ConnectionError as e:
        return {"error": "Failed to connect to target URL.", "details": str(e)}
    except requests.exceptions.RequestException as e:
        return {"error": "HTTP request failed", "details": str(e)}
    except Exception as e:
        return {"error": "Unexpected error", "details": str(e)}
