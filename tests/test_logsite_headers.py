"""
Tests for security headers on the SentinelScan Log Site.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from apps.logsite.app import create_app


class TestLogsiteHeaders(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.testing = True
        self.client = self.app.test_client()

    def test_security_headers_on_healthz(self):
        """GET /healthz receives all required security headers."""
        resp = self.client.get("/healthz")
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(resp.headers.get("X-Robots-Tag"), "noindex, nofollow")
        self.assertEqual(resp.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(resp.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")
        self.assertIn("Content-Security-Policy", resp.headers)
        self.assertIn("default-src 'self'", resp.headers["Content-Security-Policy"])

        self.assertNotIn("Server", resp.headers)
        self.assertNotIn("X-Powered-By", resp.headers)

    def test_security_headers_on_api_endpoints(self):
        """API endpoints include security headers even on 401 unauthenticated responses."""
        resp = self.client.get("/api/status")
        self.assertEqual(resp.status_code, 401)

        self.assertEqual(resp.headers.get("X-Robots-Tag"), "noindex, nofollow")
        self.assertEqual(resp.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(resp.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")
        self.assertIn("Content-Security-Policy", resp.headers)


if __name__ == "__main__":
    unittest.main()
