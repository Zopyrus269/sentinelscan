"""
Tests for SentinelScan Log Site API parameter validation,
error shapes, status response contracts, and query delegation.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(__file__),
        "..",
    ),
)

from apps.logsite.app import create_app


class TestLogsiteAPI(unittest.TestCase):
    """Tests for Workstream C's developer Log Site API."""

    def setUp(self):
        """Create a fresh Flask test client for every test."""

        self.app = create_app()
        self.app.testing = True
        self.client = self.app.test_client()

    def _auth_headers(self):
        """Return a fake Firebase bearer token header."""

        return {
            "Authorization": "Bearer fake-dev-token"
        }

    def _mock_dev_auth(
        self,
        mock_firebase_auth,
        mock_get_db,
    ):
        """Configure Firebase/Admin mocks for an allowlisted developer."""

        mock_firebase_auth.verify_id_token.return_value = {
            "uid": "dev-1",
            "email": "dev@example.com",
        }

        developer_doc = MagicMock()
        developer_doc.exists = True

        db = MagicMock()

        db.collection.return_value.document.return_value.get.return_value = (
            developer_doc
        )

        mock_get_db.return_value = db

    @patch("apps.backend.auth.auth_utils.get_db")
    @patch("apps.backend.auth.auth_utils.firebase_auth")
    def test_events_limit_exceeds_500_returns_400(
        self,
        mock_firebase_auth,
        mock_get_db,
    ):
        """Requesting more than 500 events must return HTTP 400."""

        self._mock_dev_auth(
            mock_firebase_auth,
            mock_get_db,
        )

        resp = self.client.get(
            "/api/events?limit=501",
            headers=self._auth_headers(),
        )

        self.assertEqual(
            resp.status_code,
            400,
        )

        body = resp.get_json()

        self.assertEqual(
            body["code"],
            400,
        )

        self.assertIn(
            "Limit cannot exceed 500",
            body["message"],
        )

    @patch("apps.backend.auth.auth_utils.get_db")
    @patch("apps.backend.auth.auth_utils.firebase_auth")
    def test_events_invalid_enum_parameters_return_400(
        self,
        mock_firebase_auth,
        mock_get_db,
    ):
        """Invalid level, source, and category values must return HTTP 400."""

        self._mock_dev_auth(
            mock_firebase_auth,
            mock_get_db,
        )

        resp = self.client.get(
            "/api/events?level=invalid_level",
            headers=self._auth_headers(),
        )

        self.assertEqual(
            resp.status_code,
            400,
        )

        resp = self.client.get(
            "/api/events?source=invalid_source",
            headers=self._auth_headers(),
        )

        self.assertEqual(
            resp.status_code,
            400,
        )

        resp = self.client.get(
            "/api/events?category=invalid_category",
            headers=self._auth_headers(),
        )

        self.assertEqual(
            resp.status_code,
            400,
        )

    @patch("apps.backend.auth.auth_utils.get_db")
    @patch("apps.backend.auth.auth_utils.firebase_auth")
    def test_events_invalid_iso_date_returns_400(
        self,
        mock_firebase_auth,
        mock_get_db,
    ):
        """Invalid ISO date filters must return HTTP 400."""

        self._mock_dev_auth(
            mock_firebase_auth,
            mock_get_db,
        )

        resp = self.client.get(
            "/api/events?since=not-a-date",
            headers=self._auth_headers(),
        )

        self.assertEqual(
            resp.status_code,
            400,
        )

    @patch("apps.logsite.api._query_function")
    @patch("apps.backend.auth.auth_utils.get_db")
    @patch("apps.backend.auth.auth_utils.firebase_auth")
    def test_status_endpoint_returns_expected_shape(
        self,
        mock_firebase_auth,
        mock_get_db,
        mock_query_function,
    ):
        """GET /api/status must return the documented C status shape."""

        self._mock_dev_auth(
            mock_firebase_auth,
            mock_get_db,
        )

        fake_health_query = MagicMock(
            return_value={
                "error_rate": 0.01,
                "p50_ms": 120.0,
                "p95_ms": 350.0,
                "requests_1h": 100,
                "workers": [
                    {
                        "name": "dns_lookup",
                        "ok": 10,
                        "failed": 0,
                        "success_rate": 1.0,
                    }
                ],
                "llm_failure_rate": 0.0,
            }
        )

        mock_query_function.return_value = (
            fake_health_query
        )

        resp = self.client.get(
            "/api/status",
            headers=self._auth_headers(),
        )

        self.assertEqual(
            resp.status_code,
            200,
        )

        body = resp.get_json()

        self.assertIn(
            "overall",
            body,
        )

        self.assertIn(
            "checked_at",
            body,
        )

        self.assertIn(
            "components",
            body,
        )

        self.assertIsInstance(
            body["components"],
            list,
        )

        self.assertGreater(
            len(body["components"]),
            0,
        )

        for component in body["components"]:
            self.assertIn(
                "name",
                component,
            )

            self.assertIn(
                "state",
                component,
            )

            self.assertIn(
                component["state"],
                {
                    "operational",
                    "degraded",
                    "down",
                },
            )

        mock_query_function.assert_called_once_with(
            "get_health_snapshot"
        )

        fake_health_query.assert_called_once_with()

    @patch("apps.backend.auth.auth_utils.get_db")
    @patch("apps.backend.auth.auth_utils.firebase_auth")
    def test_stats_invalid_date_returns_400(
        self,
        mock_firebase_auth,
        mock_get_db,
    ):
        """GET /api/stats/<date> rejects invalid YYYY-MM-DD values."""

        self._mock_dev_auth(
            mock_firebase_auth,
            mock_get_db,
        )

        resp = self.client.get(
            "/api/stats/2026-99-99",
            headers=self._auth_headers(),
        )

        self.assertEqual(
            resp.status_code,
            400,
        )

    @patch("apps.logsite.api._query_function")
    @patch("apps.backend.auth.auth_utils.get_db")
    @patch("apps.backend.auth.auth_utils.firebase_auth")
    def test_delegation_to_query_layer(
        self,
        mock_firebase_auth,
        mock_get_db,
        mock_query_function,
    ):
        """API calls delegate through C's Workstream B query boundary."""

        self._mock_dev_auth(
            mock_firebase_auth,
            mock_get_db,
        )

        mock_query_events = MagicMock(
            return_value={
                "events": [
                    {
                        "event_id": "e1",
                    }
                ],
                "next_cursor": "c1",
            }
        )

        mock_query_function.return_value = (
            mock_query_events
        )

        resp = self.client.get(
            "/api/events?limit=50",
            headers=self._auth_headers(),
        )

        self.assertEqual(
            resp.status_code,
            200,
        )

        body = resp.get_json()

        self.assertEqual(
            body["events"][0]["event_id"],
            "e1",
        )

        self.assertEqual(
            body["next_cursor"],
            "c1",
        )

        mock_query_function.assert_called_once_with(
            "query_events"
        )

        mock_query_events.assert_called_once()

        called_kwargs = (
            mock_query_events.call_args.kwargs
        )

        self.assertEqual(
            called_kwargs["limit"],
            50,
        )


if __name__ == "__main__":
    unittest.main()