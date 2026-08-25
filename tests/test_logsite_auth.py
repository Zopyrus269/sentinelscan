"""
Tests for Firebase authentication and developer allowlist
gating on the SentinelScan Log Site.
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


class TestLogsiteAuth(unittest.TestCase):
    """Authentication and developer-authorization tests for Workstream C."""

    def setUp(self):
        """Create a fresh Flask test client for every test."""

        self.app = create_app()
        self.app.testing = True
        self.client = self.app.test_client()

    def _mock_db(
        self,
        developer_exists: bool,
    ):
        """Build a fake Firestore client for developers/{uid} lookups."""

        developer_doc = MagicMock()
        developer_doc.exists = developer_exists

        def collection(name):
            coll = MagicMock()

            if name == "developers":
                coll.document.return_value.get.return_value = (
                    developer_doc
                )

            return coll

        db = MagicMock()
        db.collection.side_effect = collection

        return db

    def test_healthz_requires_no_auth(self):
        """GET /healthz must remain public for Render health checks."""

        resp = self.client.get(
            "/healthz"
        )

        self.assertEqual(
            resp.status_code,
            200,
        )

        self.assertEqual(
            resp.get_json(),
            {
                "status": "ok",
            },
        )

    def test_protected_routes_unauthenticated_return_401(
        self,
    ):
        """Every developer API route must reject unauthenticated callers."""

        protected_paths = [
            "/api/status",
            "/api/uptime",
            "/api/active-users",
            "/api/events",
            "/api/sessions",
            "/api/sessions/sess-123",
            "/api/traces/tr-456",
            "/api/llm-usage",
            "/api/health",
            "/api/stats/2026-08-22",
        ]

        for path in protected_paths:

            resp = self.client.get(
                path
            )

            self.assertEqual(
                resp.status_code,
                401,
                f"Path {path} did not return 401",
            )

            body = resp.get_json()

            self.assertIsInstance(
                body,
                dict,
            )

            self.assertEqual(
                body["code"],
                401,
            )

    @patch("apps.backend.auth.auth_utils.get_db")
    @patch("apps.backend.auth.auth_utils.firebase_auth")
    def test_authenticated_non_developer_returns_403(
        self,
        mock_firebase_auth,
        mock_get_db,
    ):
        """Authenticated users absent from developers/{uid} must get 403."""

        mock_firebase_auth.verify_id_token.return_value = {
            "uid": "user-non-dev",
            "email": "user@example.com",
        }

        mock_get_db.return_value = self._mock_db(
            developer_exists=False
        )

        resp = self.client.get(
            "/api/status",
            headers={
                "Authorization":
                    "Bearer valid-user-token",
            },
        )

        self.assertEqual(
            resp.status_code,
            403,
        )

        self.assertEqual(
            resp.get_json()["code"],
            403,
        )

    @patch("apps.logsite.api._query_function")
    @patch("apps.backend.auth.auth_utils.get_db")
    @patch("apps.backend.auth.auth_utils.firebase_auth")
    def test_allowlisted_developer_succeeds(
        self,
        mock_firebase_auth,
        mock_get_db,
        mock_query_function,
    ):
        """An authenticated allowlisted developer must pass C's auth gate."""

        mock_firebase_auth.verify_id_token.return_value = {
            "uid": "dev-user-1",
            "email": "dev@example.com",
        }

        mock_get_db.return_value = self._mock_db(
            developer_exists=True
        )

        fake_health_query = MagicMock(
            return_value={
                "error_rate": 0.0,
                "p50_ms": 100.0,
                "p95_ms": 200.0,
                "requests_1h": 25,
                "workers": [],
                "llm_failure_rate": 0.0,
            }
        )

        mock_query_function.return_value = (
            fake_health_query
        )

        resp = self.client.get(
            "/api/status",
            headers={
                "Authorization":
                    "Bearer valid-dev-token",
            },
        )

        self.assertEqual(
            resp.status_code,
            200,
        )

        mock_firebase_auth.verify_id_token.assert_called_once_with(
            "valid-dev-token"
        )

        mock_query_function.assert_called_once_with(
            "get_health_snapshot"
        )

        fake_health_query.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()