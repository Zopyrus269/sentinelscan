"""Pytest unit test suite for SentinelScan Sitemap Worker (sitemap_worker.py)."""

import json
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

import pytest
import requests

from apps.backend.workers.sitemap_worker import (
    format_error_response,
    format_success_response,
    get_clean_tag,
    main,
    normalize_sitemap_url,
    parse_sitemap_xml,
    perform_sitemap_fetch,
    run_worker,
)


# ── XML fixtures ──────────────────────────────────────────────────────────────

VALID_SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/</loc></url>
  <url><loc>https://example.com/about</loc></url>
  <url><loc>https://example.com/contact</loc></url>
</urlset>
"""

SITEMAP_INDEX_XML = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/post-sitemap.xml</loc></sitemap>
  <sitemap><loc>https://example.com/page-sitemap.xml</loc></sitemap>
</sitemapindex>
"""

NO_NAMESPACE_SITEMAP_XML = """<?xml version="1.0"?>
<urlset>
  <url><loc>https://example.com/page1</loc></url>
  <url><loc>https://example.com/page2</loc></url>
</urlset>
"""

EMPTY_URLSET_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
</urlset>
"""

RELATIVE_URL_SITEMAP_XML = """<?xml version="1.0"?>
<urlset>
  <url><loc>/blog</loc></url>
  <url><loc>/products</loc></url>
</urlset>
"""

INVALID_XML = "<this is not valid xml!!"


def _mock_response(status_code: int = 200, text: str = "") -> MagicMock:
    """Create a mock requests.Response object."""
    mock_resp = MagicMock(spec=requests.Response)
    mock_resp.status_code = status_code
    mock_resp.text = text
    return mock_resp


# ── Helper Function Tests ─────────────────────────────────────────────────────

class TestHelperFunctions:
    """Tests for URL normalization, tag cleaning, and response formatting."""

    def test_normalize_url_bare_domain(self):
        """Bare domain gets https scheme and /sitemap.xml path."""
        assert normalize_sitemap_url("example.com") == "https://example.com/sitemap.xml"

    def test_normalize_url_with_scheme(self):
        """URL with scheme and trailing slash gets /sitemap.xml."""
        assert normalize_sitemap_url("https://example.com/") == "https://example.com/sitemap.xml"

    def test_normalize_url_already_xml(self):
        """URL ending with .xml is returned unchanged."""
        url = "https://example.com/custom-sitemap.xml"
        assert normalize_sitemap_url(url) == url

    def test_normalize_url_subpath_no_xml(self):
        """URL with subpath not ending in .xml gets /sitemap.xml appended."""
        result = normalize_sitemap_url("https://example.com/blog")
        assert result == "https://example.com/blog/sitemap.xml"

    def test_normalize_url_http_scheme(self):
        """HTTP scheme is preserved."""
        result = normalize_sitemap_url("http://example.com")
        assert result == "http://example.com/sitemap.xml"

    def test_get_clean_tag_with_namespace(self):
        """Tags with XML namespace prefixes are stripped."""
        elem = ET.fromstring('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"/>')
        assert get_clean_tag(elem) == "urlset"

    def test_get_clean_tag_without_namespace(self):
        """Tags without namespace are returned as-is."""
        elem = ET.fromstring("<urlset/>")
        assert get_clean_tag(elem) == "urlset"

    def test_format_success_response(self):
        """Success response has correct schema."""
        data = {"urls": ["https://example.com/"], "url_count": 1}
        result = format_success_response(data)
        assert result["worker"] == "sitemap"
        assert result["status"] == "success"
        assert result["data"] == data
        assert result["error"] is None

    def test_format_error_response(self):
        """Error response has correct schema."""
        result = format_error_response("Something went wrong")
        assert result["worker"] == "sitemap"
        assert result["status"] == "error"
        assert result["data"] == {}
        assert result["error"] == "Something went wrong"


# ── XML Parsing Tests ─────────────────────────────────────────────────────────

class TestParseSitemapXml:
    """Tests for parse_sitemap_xml covering standard, index, edge-case XML."""

    def test_valid_sitemap(self):
        """Standard sitemap with namespace yields correct URLs."""
        is_index, urls, sitemaps = parse_sitemap_xml(
            VALID_SITEMAP_XML, "https://example.com/sitemap.xml"
        )
        assert is_index is False
        assert urls == [
            "https://example.com/",
            "https://example.com/about",
            "https://example.com/contact",
        ]
        assert sitemaps == []

    def test_sitemap_index(self):
        """Sitemap index XML yields child sitemap URLs."""
        is_index, urls, sitemaps = parse_sitemap_xml(
            SITEMAP_INDEX_XML, "https://example.com/sitemap.xml"
        )
        assert is_index is True
        assert urls == []
        assert sitemaps == [
            "https://example.com/post-sitemap.xml",
            "https://example.com/page-sitemap.xml",
        ]

    def test_no_namespace_sitemap(self):
        """Sitemap without XML namespace is parsed correctly."""
        is_index, urls, sitemaps = parse_sitemap_xml(
            NO_NAMESPACE_SITEMAP_XML, "https://example.com/sitemap.xml"
        )
        assert is_index is False
        assert len(urls) == 2
        assert "https://example.com/page1" in urls

    def test_empty_urlset(self):
        """Empty urlset returns no URLs."""
        is_index, urls, sitemaps = parse_sitemap_xml(
            EMPTY_URLSET_XML, "https://example.com/sitemap.xml"
        )
        assert is_index is False
        assert urls == []
        assert sitemaps == []

    def test_relative_urls_resolved(self):
        """Relative <loc> values are resolved against the base URL."""
        is_index, urls, sitemaps = parse_sitemap_xml(
            RELATIVE_URL_SITEMAP_XML, "https://example.com/sitemap.xml"
        )
        assert is_index is False
        assert "https://example.com/blog" in urls
        assert "https://example.com/products" in urls

    def test_invalid_xml_raises(self):
        """Malformed XML raises ET.ParseError."""
        with pytest.raises(ET.ParseError):
            parse_sitemap_xml(INVALID_XML, "https://example.com/sitemap.xml")

    def test_empty_string_raises(self):
        """Empty string input raises ET.ParseError."""
        with pytest.raises(ET.ParseError):
            parse_sitemap_xml("", "https://example.com/sitemap.xml")

    def test_whitespace_only_raises(self):
        """Whitespace-only input raises ET.ParseError."""
        with pytest.raises(ET.ParseError):
            parse_sitemap_xml("   \n\t  ", "https://example.com/sitemap.xml")


# ── run_worker / perform_sitemap_fetch Integration Tests ──────────────────────

class TestRunWorker:
    """Tests for run_worker covering HTTP mocking and input validation."""

    # ── Success cases ─────────────────────────────────────────────────────

    @patch("apps.backend.workers.sitemap_worker.requests.get")
    def test_valid_sitemap_success(self, mock_get):
        """Valid sitemap.xml returns success with URL list."""
        mock_get.return_value = _mock_response(200, VALID_SITEMAP_XML)

        result = run_worker({"url": "https://example.com"})

        assert result["worker"] == "sitemap"
        assert result["status"] == "success"
        assert result["error"] is None
        assert result["data"]["url_count"] == 3
        assert result["data"]["is_sitemap_index"] is False
        assert result["data"]["sitemaps"] == []
        assert len(result["data"]["urls"]) == 3

    @patch("apps.backend.workers.sitemap_worker.requests.get")
    def test_sitemap_index_success(self, mock_get):
        """Sitemap index XML returns success with child sitemap list."""
        mock_get.return_value = _mock_response(200, SITEMAP_INDEX_XML)

        result = run_worker({"url": "https://example.com"})

        assert result["status"] == "success"
        assert result["data"]["is_sitemap_index"] is True
        assert result["data"]["url_count"] == 0
        assert result["data"]["urls"] == []
        assert len(result["data"]["sitemaps"]) == 2

    @patch("apps.backend.workers.sitemap_worker.requests.get")
    def test_empty_sitemap_success(self, mock_get):
        """Empty urlset returns success with zero URLs."""
        mock_get.return_value = _mock_response(200, EMPTY_URLSET_XML)

        result = run_worker({"url": "https://example.com"})

        assert result["status"] == "success"
        assert result["data"]["url_count"] == 0
        assert result["data"]["urls"] == []

    # ── HTTP error cases ──────────────────────────────────────────────────

    @patch("apps.backend.workers.sitemap_worker.requests.get")
    def test_http_404(self, mock_get):
        """HTTP 404 returns error response."""
        mock_get.return_value = _mock_response(404)

        result = run_worker({"url": "https://example.com"})

        assert result["status"] == "error"
        assert result["data"] == {}
        assert "404" in result["error"]

    @patch("apps.backend.workers.sitemap_worker.requests.get")
    def test_http_500(self, mock_get):
        """HTTP 500 returns error response."""
        mock_get.return_value = _mock_response(500)

        result = run_worker({"url": "https://example.com"})

        assert result["status"] == "error"
        assert "500" in result["error"]

    @patch("apps.backend.workers.sitemap_worker.requests.get")
    def test_http_other_error_code(self, mock_get):
        """Non-200/404/500 status codes return error response."""
        mock_get.return_value = _mock_response(403)

        result = run_worker({"url": "https://example.com"})

        assert result["status"] == "error"
        assert "403" in result["error"]

    # ── Network error cases ───────────────────────────────────────────────

    @patch("apps.backend.workers.sitemap_worker.fetch_with_browser")
    @patch("apps.backend.workers.sitemap_worker.requests.get")
    def test_connection_error(self, mock_get, mock_fetch_with_browser):
        """Connection error returns structured error response when the
        Playwright fallback also fails (both the primary request and the
        browser retry must fail for this to surface as a worker error)."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")
        mock_fetch_with_browser.side_effect = Exception("browser fallback failed")

        result = run_worker({"url": "https://example.com"})

        assert result["status"] == "error"
        assert result["data"] == {}
        assert "Browser fallback failed" in result["error"]

    @patch("apps.backend.workers.sitemap_worker.fetch_with_browser")
    @patch("apps.backend.workers.sitemap_worker.requests.get")
    def test_timeout_error(self, mock_get, mock_fetch_with_browser):
        """Timeout returns structured error response when the Playwright
        fallback also fails (both the primary request and the browser retry
        must fail for this to surface as a worker error)."""
        mock_get.side_effect = requests.exceptions.Timeout("timed out")
        mock_fetch_with_browser.side_effect = Exception("browser fallback failed")

        result = run_worker({"url": "https://example.com"})

        assert result["status"] == "error"
        assert "browser fallback failed" in result["error"].lower()

    @patch("apps.backend.workers.sitemap_worker.requests.get")
    def test_generic_request_exception(self, mock_get):
        """Generic RequestException returns structured error response."""
        mock_get.side_effect = requests.exceptions.RequestException("Unknown error")

        result = run_worker({"url": "https://example.com"})

        assert result["status"] == "error"
        assert "Unknown error" in result["error"]

    # ── Invalid XML response ──────────────────────────────────────────────

    @patch("apps.backend.workers.sitemap_worker.requests.get")
    def test_invalid_xml_response(self, mock_get):
        """Invalid XML from server returns error response."""
        mock_get.return_value = _mock_response(200, INVALID_XML)

        result = run_worker({"url": "https://example.com"})

        assert result["status"] == "error"
        assert "Invalid XML" in result["error"]

    # ── Input validation ──────────────────────────────────────────────────

    @pytest.mark.parametrize(
        "invalid_payload, expected_fragment",
        [
            (None, "Input payload must be a JSON object"),
            ("a string", "Input payload must be a JSON object"),
            (42, "Input payload must be a JSON object"),
            ({}, "Missing required field 'url'"),
            ({"url": ""}, "URL must be a non-empty string"),
            ({"url": "   "}, "URL must be a non-empty string"),
            ({"url": 123}, "URL must be a non-empty string"),
            ({"url": "https://example.com", "timeout": -1}, "Timeout must be a positive number"),
            ({"url": "https://example.com", "timeout": "abc"}, "Timeout must be a valid number"),
        ],
    )
    def test_invalid_input_payloads(self, invalid_payload, expected_fragment):
        """Various invalid inputs return structured error responses."""
        result = run_worker(invalid_payload)

        assert result["worker"] == "sitemap"
        assert result["status"] == "error"
        assert result["data"] == {}
        assert expected_fragment in result["error"]


# ── JSON Schema & Serializability Tests ───────────────────────────────────────

class TestJsonSchema:
    """Verify output schema and JSON serializability."""

    @patch("apps.backend.workers.sitemap_worker.requests.get")
    def test_success_schema_keys(self, mock_get):
        """Success response contains exactly the expected top-level and data keys."""
        mock_get.return_value = _mock_response(200, VALID_SITEMAP_XML)

        result = run_worker({"url": "https://example.com"})

        assert set(result.keys()) == {"worker", "status", "data", "error"}
        assert set(result["data"].keys()) == {"urls", "url_count", "is_sitemap_index", "sitemaps"}

    def test_error_schema_keys(self):
        """Error response contains exactly the expected top-level keys."""
        result = run_worker({})

        assert set(result.keys()) == {"worker", "status", "data", "error"}
        assert result["data"] == {}

    @patch("apps.backend.workers.sitemap_worker.requests.get")
    def test_success_json_serializable(self, mock_get):
        """Success response round-trips through json.dumps/loads."""
        mock_get.return_value = _mock_response(200, VALID_SITEMAP_XML)

        result = run_worker({"url": "https://example.com"})
        output = json.dumps(result)
        parsed = json.loads(output)

        assert parsed["status"] == "success"
        assert parsed["worker"] == "sitemap"

    def test_error_json_serializable(self):
        """Error response round-trips through json.dumps/loads."""
        result = run_worker({})
        output = json.dumps(result)
        parsed = json.loads(output)

        assert parsed["status"] == "error"
        assert parsed["worker"] == "sitemap"


# ── CLI main() Tests ──────────────────────────────────────────────────────────

class TestMainCli:
    """Tests for the CLI entry point main()."""

    @patch("apps.backend.workers.sitemap_worker.run_worker")
    @patch("sys.argv", ["sitemap_worker.py", '{"url": "https://example.com"}'])
    def test_main_with_cli_argument(self, mock_run):
        """main() reads JSON from sys.argv and invokes run_worker."""
        mock_run.return_value = {
            "worker": "sitemap", "status": "success", "data": {}, "error": None
        }
        with patch("builtins.print") as mock_print:
            main()
            mock_run.assert_called_once_with({"url": "https://example.com"})
            mock_print.assert_called_once()

    @patch("sys.argv", ["sitemap_worker.py"])
    @patch("sys.stdin")
    def test_main_with_stdin(self, mock_stdin):
        """main() reads JSON from stdin when no CLI argument is provided."""
        mock_stdin.isatty.return_value = False
        mock_stdin.read.return_value = '{"url": "https://stdin-example.com"}'

        with patch("apps.backend.workers.sitemap_worker.run_worker") as mock_run, \
             patch("builtins.print"):
            mock_run.return_value = {
                "worker": "sitemap", "status": "success", "data": {}, "error": None
            }
            main()
            mock_run.assert_called_once_with({"url": "https://stdin-example.com"})

    @patch("sys.argv", ["sitemap_worker.py"])
    @patch("sys.stdin")
    def test_main_no_input(self, mock_stdin):
        """main() prints error when no input is provided."""
        mock_stdin.isatty.return_value = True

        with patch("builtins.print") as mock_print:
            main()
            printed_json = mock_print.call_args[0][0]
            parsed = json.loads(printed_json)
            assert parsed["status"] == "error"
            assert "No input provided" in parsed["error"]

    @patch("sys.argv", ["sitemap_worker.py", "not valid json"])
    def test_main_invalid_json(self):
        """main() prints error for invalid JSON input."""
        with patch("builtins.print") as mock_print:
            main()
            printed_json = mock_print.call_args[0][0]
            parsed = json.loads(printed_json)
            assert parsed["status"] == "error"
            assert "Invalid JSON" in parsed["error"]


if __name__ == "__main__":
    pytest.main()
