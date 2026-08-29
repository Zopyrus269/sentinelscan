"""
Tests for POST /api/probe uptime ingest endpoint.
"""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from apps.logsite.app import create_app


class TestLogsiteProbe(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.testing = True
        self.client = self.app.test_client()
        self.test_token = "secret-probe-token-123"
        os.environ["LOGSITE_PROBE_TOKEN"] = self.test_token

    def tearDown(self):
        os.environ.pop("LOGSITE_PROBE_TOKEN", None)

    def test_missing_probe_token_returns_401(self):
        """Missing X-Probe-Token header returns 401 Unauthorized."""
        resp = self.client.post("/api/probe", json={})
        self.assertEqual(resp.status_code, 401)

    def test_wrong_probe_token_returns_401(self):
        """Wrong X-Probe-Token header returns 401 Unauthorized."""
        resp = self.client.post(
            "/api/probe",
            headers={"X-Probe-Token": "wrong-token"},
            json={},
        )
        self.assertEqual(resp.status_code, 401)

    def test_invalid_body_structure_returns_400(self):
        """Missing required fields in payload returns 400 Bad Request."""
        resp = self.client.post(
            "/api/probe",
            headers={"X-Probe-Token": self.test_token},
            json={"component": "web"}, # missing ok, status, latency_ms, checked_at
        )
        self.assertEqual(resp.status_code, 400)

    @patch("apps.logsite.probe._get_query_fn")
    def test_valid_probe_post_calls_record_and_returns_204(self, mock_get_query_fn):
        """Valid probe post delegates to record_uptime_probe and returns 204 No Content."""
        mock_record_fn = MagicMock()
        mock_get_query_fn.return_value = mock_record_fn

        payload = {
            "component": "web",
            "ok": True,
            "status": 200,
            "latency_ms": 350,
            "checked_at": "2026-08-22T14:30:00Z",
        }

        resp = self.client.post(
            "/api/probe",
            headers={"X-Probe-Token": self.test_token},
            json=payload,
        )

        self.assertEqual(resp.status_code, 204)
        mock_record_fn.assert_called_once_with(payload)

    def test_uses_hmac_compare_digest(self):
        """Verify hmac.compare_digest is used for token verification."""
        with patch("hmac.compare_digest", return_value=True) as mock_compare:
            payload = {
                "component": "web",
                "ok": True,
                "status": 200,
                "latency_ms": 350,
                "checked_at": "2026-08-22T14:30:00Z",
            }
            self.client.post(
                "/api/probe",
                headers={"X-Probe-Token": self.test_token},
                json=payload,
            )
            mock_compare.assert_called()


if __name__ == "__main__":
    unittest.main()
