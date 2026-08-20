"""
Unit tests for headers_worker.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'apps', 'backend', 'workers'))

import unittest
from unittest.mock import patch, MagicMock
import requests

from headers_worker import headers_worker


class TestHeadersWorker(unittest.TestCase):
    """Automated unit test suite for headers_worker using mock HTTP responses."""

    def setUp(self):
        self.target_url = "https://example.com"

    @patch("requests.get")
    def test_headers_worker_missing_security_headers(self, mock_get):
        """Test detection of missing critical security headers."""
        mock_response = MagicMock()
        mock_response.headers = {
            "Content-Type": "text/html",
            "X-Frame-Options": "SAMEORIGIN",
        }
        mock_get.return_value = mock_response

        result = headers_worker(self.target_url)

        self.assertIn("Strict-Transport-Security", result["missing_headers"])
        self.assertIn("Content-Security-Policy", result["missing_headers"])
        self.assertIn("X-Frame-Options", result["present_headers"])
        self.assertEqual(result["missing_count"], 5)

    @patch("requests.get")
    def test_headers_worker_all_headers_present(self, mock_get):
        """Test when all critical security headers are present."""
        mock_response = MagicMock()
        mock_response.headers = {
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'self'",
            "Referrer-Policy": "no-referrer",
            "Permissions-Policy": "geolocation=()",
        }
        mock_get.return_value = mock_response

        result = headers_worker(self.target_url)

        self.assertEqual(result["missing_count"], 0)
        self.assertEqual(len(result["missing_headers"]), 0)

    @patch("requests.get")
    @patch("headers_worker.fetch_with_browser")
    def test_headers_worker_timeout_exception(self, mock_fetch_with_browser, mock_get):
        """Test timeout exception handling in headers_worker when the
        Playwright fallback also fails (both the primary request and the
        browser retry must fail for this to surface as a worker error)."""
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")
        mock_fetch_with_browser.side_effect = Exception("browser fallback failed")

        result = headers_worker(self.target_url)

        self.assertIn("error", result)
        self.assertEqual(result["error"], "Browser fallback failed")


if __name__ == "__main__":
    unittest.main()
