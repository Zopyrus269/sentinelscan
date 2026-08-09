"""SentinelScan Sitemap Worker module.

This module provides a stateless worker that fetches and parses XML sitemaps
or sitemap index files for a target URL, returning structured JSON output
in accordance with SentinelScan specifications.
"""

import json
import sys
from typing import Any, Dict, List, Tuple
from urllib.parse import urljoin, urlparse, urlunparse
import xml.etree.ElementTree as ET
from defusedxml.ElementTree import fromstring as defused_fromstring

import requests


WORKER_NAME = "sitemap"
DEFAULT_TIMEOUT = 15.0
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def normalize_sitemap_url(raw_url: str) -> str:
    """Normalize a target URL by ensuring scheme and appending sitemap.xml if needed.

    Args:
        raw_url (str): Input URL string.

    Returns:
        str: Normalized full sitemap URL.
    """
    clean_url = raw_url.strip()
    if not clean_url.startswith(("http://", "https://")):
        clean_url = f"https://{clean_url}"

    parsed = urlparse(clean_url)
    path = parsed.path

    if not path or path == "/":
        path = "/sitemap.xml"
    elif not path.endswith(".xml"):
        if not path.endswith("/"):
            path += "/"
        path += "sitemap.xml"

    normalized = urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )
    return normalized


def get_clean_tag(elem: ET.Element) -> str:
    """Extract XML tag name without namespace prefix.

    Args:
        elem (ET.Element): XML element object.

    Returns:
        str: Tag name stripped of XML namespace.
    """
    if isinstance(elem.tag, str) and "}" in elem.tag:
        return elem.tag.split("}")[-1]
    return str(elem.tag)


def parse_sitemap_xml(
    xml_content: str, base_url: str
) -> Tuple[bool, List[str], List[str]]:
    """Parse sitemap XML content into URL list or child sitemap index list.

    Supports XML namespaces, missing namespaces, relative/absolute URLs, and sitemap indexes.

    Args:
        xml_content (str): Raw sitemap XML content.
        base_url (str): Base URL used for resolving relative loc URLs.

    Returns:
        Tuple[bool, List[str], List[str]]: Tuple containing:
            - is_sitemap_index (bool): True if document is a sitemap index.
            - urls (List[str]): List of webpage URLs if standard sitemap.
            - sitemaps (List[str]): List of child sitemap URLs if sitemap index.

    Raises:
        ET.ParseError: If XML content is malformed or empty.
    """
    if not xml_content or not xml_content.strip():
        raise ET.ParseError("Empty XML content.")

    try:
        root = defused_fromstring(xml_content.strip())
    except ET.ParseError as err:
        raise ET.ParseError(f"Invalid XML structure: {str(err)}")

    root_tag = get_clean_tag(root).lower()
    is_sitemap_index = root_tag == "sitemapindex"

    urls: List[str] = []
    sitemaps: List[str] = []

    # Detect if root contains <sitemap> containers indicating an index
    if not is_sitemap_index:
        for child in root:
            if get_clean_tag(child).lower() == "sitemap":
                is_sitemap_index = True
                break

    for elem in root.iter():
        tag = get_clean_tag(elem).lower()
        if is_sitemap_index and tag == "sitemap":
            loc_elem = next(
                (c for c in elem if get_clean_tag(c).lower() == "loc"), None
            )
            if loc_elem is not None and loc_elem.text:
                loc_text = loc_elem.text.strip()
                if loc_text:
                    full_url = urljoin(base_url, loc_text)
                    if full_url not in sitemaps:
                        sitemaps.append(full_url)
        elif not is_sitemap_index and tag == "url":
            loc_elem = next(
                (c for c in elem if get_clean_tag(c).lower() == "loc"), None
            )
            if loc_elem is not None and loc_elem.text:
                loc_text = loc_elem.text.strip()
                if loc_text:
                    full_url = urljoin(base_url, loc_text)
                    if full_url not in urls:
                        urls.append(full_url)

    # Fallback: if no container tags (<url> or <sitemap>) found, search <loc> directly
    if not urls and not sitemaps:
        for elem in root.iter():
            if get_clean_tag(elem).lower() == "loc" and elem.text:
                loc_text = elem.text.strip()
                if loc_text:
                    full_url = urljoin(base_url, loc_text)
                    if is_sitemap_index:
                        if full_url not in sitemaps:
                            sitemaps.append(full_url)
                    else:
                        if full_url not in urls:
                            urls.append(full_url)

    return is_sitemap_index, urls, sitemaps


def format_success_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Format success output dictionary matching SentinelScan schema.

    Args:
        data (Dict[str, Any]): Extracted sitemap data.

    Returns:
        Dict[str, Any]: Standardized success payload.
    """
    return {
        "worker": WORKER_NAME,
        "status": "success",
        "data": data,
        "error": None,
    }


def format_error_response(error_message: str) -> Dict[str, Any]:
    """Format error output dictionary matching SentinelScan schema.

    Args:
        error_message (str): Detailed error message.

    Returns:
        Dict[str, Any]: Standardized error payload.
    """
    return {
        "worker": WORKER_NAME,
        "status": "error",
        "data": {},
        "error": error_message,
    }


def perform_sitemap_fetch(
    url: str, timeout: float = DEFAULT_TIMEOUT
) -> Dict[str, Any]:
    """Fetch and parse sitemap XML for a target URL.

    Args:
        url (str): Target webpage or sitemap URL.
        timeout (float): Connection timeout in seconds.

    Returns:
        Dict[str, Any]: Standardized response dictionary.
    """
    if not url or not isinstance(url, str) or not url.strip():
        return format_error_response("URL must be a non-empty string.")

    target_url = normalize_sitemap_url(url)
    headers = {"User-Agent": USER_AGENT}

    try:
        response = requests.get(target_url, timeout=timeout, headers=headers)
    except requests.exceptions.Timeout:
        return format_error_response(
            f"Request timed out fetching sitemap from '{target_url}'."
        )
    except requests.exceptions.ConnectionError as err:
        return format_error_response(
            f"Connection error fetching sitemap from '{target_url}': {str(err)}"
        )
    except requests.exceptions.RequestException as err:
        return format_error_response(
            f"Failed to fetch sitemap from '{target_url}': {str(err)}"
        )
    except Exception as err:
        return format_error_response(f"HTTP request failed: {str(err)}")

    if response.status_code == 404:
        return format_error_response(
            f"HTTP 404: Sitemap not found at '{target_url}'."
        )
    if response.status_code == 500:
        return format_error_response(
            f"HTTP 500: Server error fetching sitemap from '{target_url}'."
        )
    if response.status_code != 200:
        return format_error_response(
            f"HTTP {response.status_code} error fetching sitemap from '{target_url}'."
        )

    try:
        is_sitemap_index, urls, sitemaps = parse_sitemap_xml(
            response.text, target_url
        )
    except ET.ParseError as err:
        return format_error_response(
            f"Invalid XML content in sitemap: {str(err)}"
        )

    data = {
        "urls": urls,
        "url_count": len(urls),
        "is_sitemap_index": is_sitemap_index,
        "sitemaps": sitemaps,
    }

    return format_success_response(data)


def run_worker(input_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate input payload schema and execute worker task.

    Args:
        input_payload (Dict[str, Any]): Input payload dictionary containing 'url'.

    Returns:
        Dict[str, Any]: Standardized JSON-serializable response payload.
    """
    if not isinstance(input_payload, dict):
        return format_error_response("Input payload must be a JSON object.")

    if "url" not in input_payload:
        return format_error_response("Missing required field 'url' in input payload.")

    url = input_payload.get("url")
    if not isinstance(url, str) or not url.strip():
        return format_error_response("URL must be a non-empty string.")

    timeout = input_payload.get("timeout", DEFAULT_TIMEOUT)
    try:
        timeout_float = float(timeout)
        if timeout_float <= 0:
            return format_error_response("Timeout must be a positive number.")
    except (ValueError, TypeError):
        return format_error_response("Timeout must be a valid number.")

    return perform_sitemap_fetch(url, timeout_float)


def main() -> None:
    """CLI Entry point for executing the Sitemap worker.

    Reads JSON payload from CLI command-line argument or stdin and outputs
    structured JSON to standard output.
    """
    input_str = ""
    if len(sys.argv) > 1:
        input_str = sys.argv[1]
    elif not sys.stdin.isatty():
        input_str = sys.stdin.read()

    if not input_str.strip():
        result = format_error_response("No input provided via CLI argument or stdin.")
        print(json.dumps(result, indent=4))
        return

    try:
        input_payload = json.loads(input_str)
    except json.JSONDecodeError as err:
        result = format_error_response(f"Invalid JSON input: {str(err)}")
        print(json.dumps(result, indent=4))
        return

    result = run_worker(input_payload)
    print(json.dumps(result, indent=4))


if __name__ == "__main__":
    main()
