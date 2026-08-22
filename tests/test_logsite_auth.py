"""
Tests for authentication and developer allowlist gating on the SentinelScan Log Site.
"""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from apps.logsite.app import create_app


class TestLogsiteAuth(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.testing = True
        self.client = self.app.test_client()

    def _mock_db(self, developer_exists: bool):
        """Builds a fake Firestore client covering developers/{uid} lookups."""
        developer_doc = MagicMock()
        developer_doc.exists = developer_exists

        def collection(name):
            coll = MagicMock()
            if name == "developers":
                coll.document.return_value.get.return_value = developer_doc
            return coll

        db = MagicMock()
        db.collection.side_effect = collection
        return db

    def test_healthz_requires_no_auth(self):
        """GET /healthz should return 200 OK without any auth header."""
        resp = self.client.get("/healthz")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), {"status": "ok"})

    def test_protected_routes_unauthenticated_return_401(self):
        """Every protected /api/* endpoint returns 401 without valid auth."""
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
            resp = self.client.get(path)
            self.assertEqual(resp.status_code, 401, f"Path {path} did not return 401")
            self.assertEqual(resp.get_json()["code"], 401)

    @patch("apps.backend.auth.auth_utils.get_db")
    @patch("apps.backend.auth.auth_utils.firebase_auth")
    def test_authenticated_non_developer_returns_403(self, mock_firebase_auth, mock_get_db):
        """Authenticated users not on developers/{uid} allowlist return 403 Forbidden."""
        mock_firebase_auth.verify_id_token.return_value = {
            "uid": "user-non-dev",
            "email": "user@example.com",
        }
        mock_get_db.return_value = self._mock_db(developer_exists=False)

        resp = self.client.get(
            "/api/status",
            headers={"Authorization": "Bearer valid-user-token"},
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.get_json()["code"], 403)

    @patch("apps.backend.auth.auth_utils.get_db")
    @patch("apps.backend.auth.auth_utils.firebase_auth")
    def test_allowlisted_developer_succeeds(self, mock_firebase_auth, mock_get_db):
        """Allowlisted developers pass the auth gate successfully."""
        mock_firebase_auth.verify_id_token.return_value = {
            "uid": "dev-user-1",
            "email": "dev@example.com",
        }
        mock_get_db.return_value = self._mock_db(developer_exists=True)

        resp = self.client.get(
            "/api/status",
            headers={"Authorization": "Bearer valid-dev-token"},
        )
        self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
