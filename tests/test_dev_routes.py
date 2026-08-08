"""
Offline tests for dev_routes.py (team secrets bootstrap endpoint).

Mocks firebase_auth.verify_id_token (auth layer) and get_db (Firestore
layer) so no real Firebase project is needed to verify the routing,
allowlist gating, and response shape.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from unittest.mock import patch, MagicMock

from apps.backend.app import create_app


class TestDevRoutes(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.testing = True
        self.client = self.app.test_client()

    def _mock_db(self, developer_exists: bool, secrets_exists: bool = True, secrets_data=None):
        """Builds a fake Firestore client covering developers/{uid} and config/secrets lookups."""
        developer_doc = MagicMock()
        developer_doc.exists = developer_exists

        secrets_doc = MagicMock()
        secrets_doc.exists = secrets_exists
        secrets_doc.to_dict.return_value = secrets_data or {"GEMINI_API_KEY": "AIza-test"}

        def collection(name):
            coll = MagicMock()
            if name == "developers":
                coll.document.return_value.get.return_value = developer_doc
            elif name == "config":
                coll.document.return_value.get.return_value = secrets_doc
            return coll

        db = MagicMock()
        db.collection.side_effect = collection
        return db

    def test_no_auth_header_returns_401(self):
        resp = self.client.get("/api/v1/dev/bootstrap-secrets")
        self.assertEqual(resp.status_code, 401)

    @patch("apps.backend.auth.auth_utils.get_db")
    @patch("apps.backend.auth.auth_utils.firebase_auth")
    def test_authenticated_non_developer_returns_403(self, mock_firebase_auth, mock_get_db):
        mock_firebase_auth.verify_id_token.return_value = {"uid": "user-1", "email": "user@example.com"}
        mock_get_db.return_value = self._mock_db(developer_exists=False)

        resp = self.client.get(
            "/api/v1/dev/bootstrap-secrets",
            headers={"Authorization": "Bearer fake-token"},
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.get_json()["code"], 403)

    @patch("apps.backend.routes.dev_routes.get_db")
    @patch("apps.backend.auth.auth_utils.get_db")
    @patch("apps.backend.auth.auth_utils.firebase_auth")
    def test_allowlisted_developer_gets_secrets(self, mock_firebase_auth, mock_auth_get_db, mock_route_get_db):
        mock_firebase_auth.verify_id_token.return_value = {"uid": "dev-1", "email": "dev@example.com"}
        db = self._mock_db(developer_exists=True, secrets_data={"GEMINI_API_KEY": "AIza-real", "FLASK_SECRET_KEY": "shh"})
        mock_auth_get_db.return_value = db
        mock_route_get_db.return_value = db

        resp = self.client.get(
            "/api/v1/dev/bootstrap-secrets",
            headers={"Authorization": "Bearer fake-token"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body["GEMINI_API_KEY"], "AIza-real")
        self.assertEqual(body["FLASK_SECRET_KEY"], "shh")

    @patch("apps.backend.routes.dev_routes.get_db")
    @patch("apps.backend.auth.auth_utils.get_db")
    @patch("apps.backend.auth.auth_utils.firebase_auth")
    def test_developer_but_secrets_not_seeded_returns_404(self, mock_firebase_auth, mock_auth_get_db, mock_route_get_db):
        mock_firebase_auth.verify_id_token.return_value = {"uid": "dev-1", "email": "dev@example.com"}
        db = self._mock_db(developer_exists=True, secrets_exists=False)
        mock_auth_get_db.return_value = db
        mock_route_get_db.return_value = db

        resp = self.client.get(
            "/api/v1/dev/bootstrap-secrets",
            headers={"Authorization": "Bearer fake-token"},
        )
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
