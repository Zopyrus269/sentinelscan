"""
Unit tests for cookie_worker.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'apps', 'backend', 'workers'))

import unittest
from unittest.mock import patch, MagicMock
from http.cookiejar import Cookie
from requests.cookies import RequestsCookieJar
import requests

from cookie_worker import cookie_worker


class TestCookieWorker(unittest.TestCase):
    """Automated unit test suite for cookie_worker using mock HTTP responses."""

    def setUp(self):
        self.target_url = "https://example.com"

    @patch("requests.get")
    def test_cookie_missing_secure_and_httponly(self, mock_get):
        """Test identification of a cookie missing Secure and HttpOnly flags."""
        mock_response = MagicMock()
        jar = RequestsCookieJar()
        cookie1 = Cookie(
            version=0, name="session_id", value="12345", port=None, port_specified=False,
            domain="example.com", domain_specified=True, domain_initial_dot=False, path="/",
            path_specified=True, secure=False, expires=None, discard=True, comment=None,
            comment_url=None, rest={}, rfc2109=False
        )
        jar.set_cookie(cookie1)
        mock_response.cookies = jar
        mock_response.headers = {}
        mock_response.raw = None
        mock_get.return_value = mock_response

        result = cookie_worker(self.target_url)

        self.assertEqual(result["total_cookies_found"], 1)
        self.assertEqual(result["vulnerable_cookies_count"], 1)
        cookie_info = result["cookies"][0]
        self.assertEqual(cookie_info["name"], "session_id")
        self.assertIn("Secure", cookie_info["missing_flags"])
        self.assertIn("HttpOnly", cookie_info["missing_flags"])
        self.assertTrue(cookie_info["is_vulnerable"])

    @patch("requests.get")
    def test_cookies_worker_raw_set_cookie_header_fallback(self, mock_get):
        """Test fallback parsing when inspecting raw Set-Cookie response headers."""
        mock_response = MagicMock()
        mock_response.cookies = RequestsCookieJar()
        mock_response.headers = {
            "Set-Cookie": "tracker_id=xyz987; Path=/; Domain=example.com"
        }
        mock_response.raw = None
        mock_get.return_value = mock_response

        result = cookie_worker(self.target_url)

        self.assertEqual(result["total_cookies_found"], 1)
        cookie_info = result["cookies"][0]
        self.assertEqual(cookie_info["name"], "tracker_id")
        self.assertIn("Secure", cookie_info["missing_flags"])
        self.assertIn("HttpOnly", cookie_info["missing_flags"])

    @patch("requests.get")
    def test_cookies_worker_connection_error(self, mock_get):
        """Test connection error handling in cookie_worker."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Failed to resolve host")

        result = cookie_worker(self.target_url)

        self.assertIn("error", result)
        self.assertEqual(result["error"], "Failed to connect to target URL.")


if __name__ == "__main__":
    unittest.main()
