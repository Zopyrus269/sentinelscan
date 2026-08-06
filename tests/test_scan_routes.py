"""
Offline tests for scan_routes.py.

Uses Flask's test client. Mocks apps.backend.agent.orchestrator.run_scan
(via its imported reference inside scan_routes) so no real Gemini API
calls happen during testing -- these tests verify routing, request/
response shapes, and status transitions, not the agent's decision logic
itself (already covered by test_orchestrator_offline.py).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import tempfile
import time
import unittest
from unittest.mock import patch

from apps.backend.app import create_app


class TestScanRoutes(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.testing = True
        self.client = self.app.test_client()

    def test_health_check(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), {"status": "ok"})

    def test_start_scan_missing_target_returns_400(self):
        resp = self.client.post("/api/v1/scans", json={})
        self.assertEqual(resp.status_code, 400)
        body = resp.get_json()
        self.assertEqual(body["code"], 400)
        self.assertIn("target", body["message"].lower())

    @patch("apps.backend.routes.scan_routes.run_scan")
    def test_start_scan_success_returns_pending(self, mock_run_scan):
        mock_run_scan.return_value = {
            "status": "complete",
            "report": {"pdf_path": "x.pdf", "json_path": "x.json"},
            "iterations": 1,
        }
        resp = self.client.post("/api/v1/scans", json={"target": "example.com"})
        self.assertEqual(resp.status_code, 202)
        body = resp.get_json()
        self.assertIn("scan_id", body)
        self.assertEqual(body["status"], "PENDING")

    def test_get_nonexistent_scan_returns_404(self):
        resp = self.client.get("/api/v1/scans/does-not-exist")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.get_json()["code"], 404)

    @patch("apps.backend.routes.scan_routes.run_scan")
    def test_scan_completes_and_status_updates(self, mock_run_scan):
        mock_run_scan.return_value = {
            "status": "complete",
            "report": {"pdf_path": "x.pdf", "json_path": "x.json"},
            "iterations": 1,
        }

        resp = self.client.post("/api/v1/scans", json={"target": "example.com"})
        scan_id = resp.get_json()["scan_id"]

        status_resp = None
        for _ in range(20):
            status_resp = self.client.get(f"/api/v1/scans/{scan_id}")
            if status_resp.get_json()["status"] == "COMPLETED":
                break
            time.sleep(0.05)

        final = status_resp.get_json()
        self.assertEqual(final["status"], "COMPLETED")
        self.assertEqual(final["progress_percent"], 100)

    def test_list_scans_returns_list(self):
        resp = self.client.get("/api/v1/scans")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertIn("scans", body)
        self.assertIsInstance(body["scans"], list)

    def test_get_report_json_for_incomplete_scan_returns_404(self):
        from apps.backend.models.scan_store import create_scan
        scan_id = create_scan("pending-target.com")
        resp = self.client.get(f"/api/v1/reports/{scan_id}/json")
        self.assertEqual(resp.status_code, 404)

    def test_get_report_json_success(self):
        from apps.backend.models.scan_store import create_scan, update_scan

        tmp_dir = tempfile.mkdtemp()
        json_path = os.path.join(tmp_dir, "fake_report.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({"target": "example.com", "findings": []}, f)

        scan_id = create_scan("example.com")
        update_scan(scan_id, status="COMPLETED", json_path=json_path)

        resp = self.client.get(f"/api/v1/reports/{scan_id}/json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["target"], "example.com")

    def test_get_report_pdf_for_nonexistent_scan_unauthenticated_returns_401(self):
        resp = self.client.get("/api/v1/reports/does-not-exist/pdf")
        self.assertEqual(resp.status_code, 401)

    def test_get_report_pdf_for_nonexistent_scan_authenticated_returns_404(self):
        from unittest.mock import patch
        with patch("apps.backend.routes.scan_routes._verify_token_inline", return_value="fake-uid-123"):
            with patch("apps.backend.routes.scan_routes.get_history_scan", return_value=None):
                resp = self.client.get("/api/v1/reports/does-not-exist/pdf")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
