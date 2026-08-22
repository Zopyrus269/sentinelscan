"""Tests for apps.backend.logstore.pipeline -- the queue + sink-thread wiring.

Mocks get_db() and sink.start() so no real Firestore project or long-running thread is
needed; resets the module's global state before/after each test since ensure_started()/
get_queue() are deliberately module-level singletons (mirroring how app.py calls them).
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from unittest.mock import patch, MagicMock

from apps.backend.logstore import pipeline
from apps.backend.logstore.firestore_sink import FirestoreSink
from apps.backend.logstore.stdout_sink import StdoutSink


class TestPipeline(unittest.TestCase):

    def setUp(self):
        pipeline._queue = None
        pipeline._started = False

    def tearDown(self):
        pipeline._queue = None
        pipeline._started = False

    def test_get_queue_is_stable_across_calls(self):
        q1 = pipeline.get_queue()
        q2 = pipeline.get_queue()
        self.assertIs(q1, q2)

    def test_get_queue_respects_size_env_var(self):
        with patch.dict(os.environ, {"SENTINELSCAN_TELEMETRY_QUEUE_SIZE": "5"}):
            q = pipeline.get_queue()
        self.assertEqual(q.maxsize, 5)

    @patch("apps.backend.logstore.pipeline.sink.start")
    @patch("apps.backend.logstore.pipeline.get_db")
    def test_ensure_started_picks_firestore_sink_when_configured(self, mock_get_db, mock_sink_start):
        mock_get_db.return_value = MagicMock()
        pipeline.ensure_started()

        self.assertEqual(mock_sink_start.call_count, 1)
        _, backend = mock_sink_start.call_args[0]
        self.assertIsInstance(backend, FirestoreSink)

    @patch("apps.backend.logstore.pipeline.sink.start")
    @patch("apps.backend.logstore.pipeline.get_db")
    def test_ensure_started_picks_stdout_sink_when_firestore_unconfigured(self, mock_get_db, mock_sink_start):
        mock_get_db.return_value = None
        pipeline.ensure_started()

        self.assertEqual(mock_sink_start.call_count, 1)
        _, backend = mock_sink_start.call_args[0]
        self.assertIsInstance(backend, StdoutSink)

    @patch("apps.backend.logstore.pipeline.sink.start")
    @patch("apps.backend.logstore.pipeline.get_db")
    def test_ensure_started_is_idempotent(self, mock_get_db, mock_sink_start):
        mock_get_db.return_value = None
        pipeline.ensure_started()
        pipeline.ensure_started()

        self.assertEqual(mock_sink_start.call_count, 1)

    def test_is_enabled_truthy_values(self):
        for value in ("1", "true", "True", "yes", "on"):
            with patch.dict(os.environ, {"SENTINELSCAN_TELEMETRY_ENABLED": value}):
                self.assertTrue(pipeline.is_enabled(), value)

    def test_is_enabled_falsy_values(self):
        for value in ("0", "false", "no", "off", ""):
            with patch.dict(os.environ, {"SENTINELSCAN_TELEMETRY_ENABLED": value}):
                self.assertFalse(pipeline.is_enabled(), value)

    def test_is_enabled_defaults_to_false_when_unset(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SENTINELSCAN_TELEMETRY_ENABLED", None)
            self.assertFalse(pipeline.is_enabled())


if __name__ == "__main__":
    unittest.main()
