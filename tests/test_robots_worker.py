"""
Unit tests for robots_worker.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'apps', 'backend', 'workers'))

import unittest
from unittest.mock import patch, MagicMock
import requests

from robots_worker import robots_worker


class TestRobotsWorker(unittest.TestCase):
    """Automated unit test suite for robots_worker using mock HTTP responses."""

    def setUp(self):
        self.target_url = "https://example.com"

    @patch("requests.get")
    def test_robots_worker_extract_disallow_paths(self, mock_get):
        """Test fetching and parsing Disallow: directives from robots.txt."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = (
            "User-agent: *\n"
            "Disallow: /admin/\n"
            "Disallow: /private/data # Sensitive directory\n"
            "DISALLOW: /config.json\n"
            "Disallow: \n"
            "Allow: /public/\n"
        )
        mock_get.return_value = mock_response

        result = robots_worker(self.target_url)

        self.assertEqual(result["robots_url"], "https://example.com/robots.txt")
        self.assertTrue(result["exists"])
        self.assertEqual(result["total_disallowed"], 3)
        self.assertIn("/admin/", result["disallowed_paths"])
        self.assertIn("/private/data", result["disallowed_paths"])
        self.assertIn("/config.json", result["disallowed_paths"])

    @patch("requests.get")
    def test_robots_worker_not_found(self, mock_get):
        """Test response when robots.txt does not exist (HTTP 404)."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = robots_worker(self.target_url)

        self.assertFalse(result["exists"])
        self.assertEqual(result["total_disallowed"], 0)

    @patch("requests.get")
    def test_robots_worker_request_exception(self, mock_get):
        """Test generic RequestException handling in robots_worker."""
        mock_get.side_effect = requests.exceptions.RequestException("SSLError occurred")

        result = robots_worker(self.target_url)

        self.assertIn("error", result)
        self.assertEqual(result["error"], "HTTP request failed")


if __name__ == "__main__":
    unittest.main()
