"""Offline tests for telemetry_routes.py (POST /api/v1/telemetry).

Mocks firebase_auth.verify_id_token and pipeline.ensure_started so no real Firebase project
or background sink thread is needed. Resets apps.backend.logstore.pipeline's module-level
queue/started state before/after each test, matching test_logstore_pipeline.py's approach --
this decouples each test's queue from anything a previous test (or app.py's own module-level
create_app() call) may have started.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import queue
import unittest
from unittest.mock import patch, MagicMock

from apps.backend.logstore import pipeline
from apps.backend.logstore.event_validation import MAX_EVENTS_PER_BATCH, MAX_REQUEST_BYTES


class TestTelemetryRoutes(unittest.TestCase):

    def setUp(self):
        pipeline._queue = None
        pipeline._started = False

        self._ensure_started_patcher = patch("apps.backend.logstore.pipeline.ensure_started")
        self._ensure_started_patcher.start()
        self.addCleanup(self._ensure_started_patcher.stop)

        self._enabled_patcher = patch.dict(os.environ, {"SENTINELSCAN_TELEMETRY_ENABLED": "1"})
        self._enabled_patcher.start()
        self.addCleanup(self._enabled_patcher.stop)

        from apps.backend.app import create_app
        self.app = create_app()
        self.app.testing = True
        self.client = self.app.test_client()

    def tearDown(self):
        pipeline._queue = None
        pipeline._started = False

    def _drain_queue(self):
        events = []
        q = pipeline.get_queue()
        while True:
            try:
                events.append(q.get_nowait())
            except queue.Empty:
                break
        return events

    def _post(self, body, headers=None):
        return self.client.post(
            "/api/v1/telemetry",
            data=json.dumps(body) if not isinstance(body, (bytes, str)) else body,
            headers={"Content-Type": "application/json", **(headers or {})},
        )

    def _one_event(self, **overrides):
        event = {"level": "info", "category": "ui", "message": "clicked start scan"}
        event.update(overrides)
        return event

    def test_oversized_body_returns_413(self):
        oversized = json.dumps({
            "events": [self._one_event(data={"blob": "x" * (MAX_REQUEST_BYTES + 1000)})]
        })
        resp = self._post(oversized)
        self.assertEqual(resp.status_code, 413)

    def test_batch_over_cap_returns_400(self):
        events = [self._one_event() for _ in range(MAX_EVENTS_PER_BATCH + 1)]
        resp = self._post({"events": events})
        self.assertEqual(resp.status_code, 400)

    def test_missing_events_key_returns_400(self):
        resp = self._post({"not_events": []})
        self.assertEqual(resp.status_code, 400)

    def test_events_not_a_list_returns_400(self):
        resp = self._post({"events": "not-a-list"})
        self.assertEqual(resp.status_code, 400)

    def test_empty_events_list_returns_400(self):
        resp = self._post({"events": []})
        self.assertEqual(resp.status_code, 400)

    def test_valid_batch_returns_204_and_enqueues(self):
        resp = self._post({"events": [self._one_event(message="a"), self._one_event(message="b")]})
        self.assertEqual(resp.status_code, 204)

        events = self._drain_queue()
        self.assertEqual(len(events), 2)
        self.assertEqual({e["message"] for e in events}, {"a", "b"})

    def test_invalid_events_in_batch_are_dropped_but_batch_still_returns_204(self):
        resp = self._post({"events": [self._one_event(message="ok"), {"level": "bogus"}]})
        self.assertEqual(resp.status_code, 204)

        events = self._drain_queue()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["message"], "ok")

    def test_client_supplied_uid_is_ignored_without_auth_header(self):
        resp = self._post({"events": [self._one_event(uid="attacker-controlled")]})
        self.assertEqual(resp.status_code, 204)

        events = self._drain_queue()
        self.assertIsNone(events[0]["uid"])

    @patch("apps.backend.routes.telemetry_routes.firebase_auth")
    def test_verified_bearer_token_sets_uid(self, mock_firebase_auth):
        mock_firebase_auth.verify_id_token.return_value = {"uid": "real-user-1"}

        resp = self._post(
            {"events": [self._one_event(uid="attacker-controlled")]},
            headers={"Authorization": "Bearer fake-token"},
        )
        self.assertEqual(resp.status_code, 204)

        events = self._drain_queue()
        self.assertEqual(events[0]["uid"], "real-user-1")

    @patch("apps.backend.routes.telemetry_routes.firebase_auth")
    def test_invalid_bearer_token_does_not_fail_request(self, mock_firebase_auth):
        mock_firebase_auth.verify_id_token.side_effect = Exception("bad token")

        resp = self._post(
            {"events": [self._one_event()]},
            headers={"Authorization": "Bearer garbage"},
        )
        self.assertEqual(resp.status_code, 204)

        events = self._drain_queue()
        self.assertIsNone(events[0]["uid"])

    def test_disabled_returns_204_but_nothing_enqueued(self):
        with patch.dict(os.environ, {"SENTINELSCAN_TELEMETRY_ENABLED": "0"}):
            resp = self._post({"events": [self._one_event()]})
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(self._drain_queue(), [])


if __name__ == "__main__":
    unittest.main()
