"""
Tests for SentinelScan Log Site API parameter validation, error shapes, and query delegations.
"""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from apps.logsite.app import create_app


class TestLogsiteAPI(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.testing = True
        self.client = self.app.test_client()

    def _auth_headers(self):
        return {"Authorization": "Bearer fake-dev-token"}

    def _mock_dev_auth(self, mock_firebase_auth, mock_get_db):
        """Helper to bypass auth decorators for testing route logic directly."""
        mock_firebase_auth.verify_id_token.return_value = {"uid": "dev-1", "email": "dev@example.com"}
        developer_doc = MagicMock()
        developer_doc.exists = True
        db = MagicMock()
        db.collection.return_value.document.return_value.get.return_value = developer_doc
        mock_get_db.return_value = db

    @patch("apps.backend.auth.auth_utils.get_db")
    @patch("apps.backend.auth.auth_utils.firebase_auth")
    def test_events_limit_exceeds_500_returns_400(self, mock_firebase_auth, mock_get_db):
        """Requesting limit > 500 on /api/events must return HTTP 400."""
        self._mock_dev_auth(mock_firebase_auth, mock_get_db)
        resp = self.client.get("/api/events?limit=501", headers=self._auth_headers())
        self.assertEqual(resp.status_code, 400)
        body = resp.get_json()
        self.assertEqual(body["code"], 400)
        self.assertIn("Limit cannot exceed 500", body["message"])

    @patch("apps.backend.auth.auth_utils.get_db")
    @patch("apps.backend.auth.auth_utils.firebase_auth")
    def test_events_invalid_enum_parameters_return_400(self, mock_firebase_auth, mock_get_db):
        """Invalid level, source, or category parameters return 400."""
        self._mock_dev_auth(mock_firebase_auth, mock_get_db)

        resp = self.client.get("/api/events?level=invalid_level", headers=self._auth_headers())
        self.assertEqual(resp.status_code, 400)

        resp = self.client.get("/api/events?source=invalid_source", headers=self._auth_headers())
        self.assertEqual(resp.status_code, 400)

        resp = self.client.get("/api/events?category=invalid_category", headers=self._auth_headers())
        self.assertEqual(resp.status_code, 400)

    @patch("apps.backend.auth.auth_utils.get_db")
    @patch("apps.backend.auth.auth_utils.firebase_auth")
    def test_events_invalid_iso_date_returns_400(self, mock_firebase_auth, mock_get_db):
        """Invalid since/until date strings return 400."""
        self._mock_dev_auth(mock_firebase_auth, mock_get_db)
        resp = self.client.get("/api/events?since=not-a-date", headers=self._auth_headers())
        self.assertEqual(resp.status_code, 400)

    @patch("apps.backend.auth.auth_utils.get_db")
    @patch("apps.backend.auth.auth_utils.firebase_auth")
    def test_status_endpoint_returns_expected_shape(self, mock_firebase_auth, mock_get_db):
        """GET /api/status returns overall status, timestamp, and component list."""
        self._mock_dev_auth(mock_firebase_auth, mock_get_db)
        resp = self.client.get("/api/status", headers=self._auth_headers())
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertIn("overall", body)
        self.assertIn("checked_at", body)
        self.assertIn("components", body)
        self.assertIsInstance(body["components"], list)

    @patch("apps.backend.auth.auth_utils.get_db")
    @patch("apps.backend.auth.auth_utils.firebase_auth")
    def test_stats_invalid_date_returns_400(self, mock_firebase_auth, mock_get_db):
        """GET /api/stats/<date> rejects non-YYYY-MM-DD strings with 400."""
        self._mock_dev_auth(mock_firebase_auth, mock_get_db)
        resp = self.client.get("/api/stats/2026-99-99", headers=self._auth_headers())
        self.assertEqual(resp.status_code, 400)

    @patch("apps.backend.auth.auth_utils.get_db")
    @patch("apps.backend.auth.auth_utils.firebase_auth")
    def test_delegation_to_query_layer(self, mock_firebase_auth, mock_get_db):
        """Verify API calls delegate to query layer functions when available."""
        self._mock_dev_auth(mock_firebase_auth, mock_get_db)

        mock_query_events = MagicMock(return_value={"events": [{"event_id": "e1"}], "next_cursor": "c1"})
        
        # Install stub module in sys.modules to simulate B query layer
        fake_query_mod = MagicMock()
        fake_query_mod.query_events = mock_query_events
        sys.modules["apps.backend.logstore.query"] = fake_query_mod

        try:
            resp = self.client.get("/api/events?limit=50", headers=self._auth_headers())
            self.assertEqual(resp.status_code, 200)
            body = resp.get_json()
            self.assertEqual(body["events"][0]["event_id"], "e1")
            self.assertEqual(body["next_cursor"], "c1")
            mock_query_events.assert_called_once()
        finally:
            sys.modules.pop("apps.backend.logstore.query", None)


if __name__ == "__main__":
    unittest.main()
