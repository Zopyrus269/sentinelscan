"""Cross-branch integration tests: Workstream A's ``observability.emit`` and Workstream
B's ``logstore`` pipeline, together.

Before this branch existed, ``observability.emit`` kept its own private queue that nothing
ever drained -- ``logstore.sink``'s thread only ever drained ``logstore.pipeline``'s queue,
which only the browser ingest route (``telemetry_routes.py``) fed. Both sides' own docstrings
described the *intended* design (a single shared queue) without it actually being wired that
way, since the two branches had never been merged. This file proves the fix: a backend-
originated event pushed through ``observability.emit``'s public API is the same event a real
``SinkThread`` flushes to a backend, and that event is shape-compatible with what
``logstore.schema``/``logstore.firestore_sink`` expect to write.

Follows the existing per-module test patterns rather than inventing a new one: the fake
in-memory-queue + ``FakeBackend`` + real ``SinkThread`` setup mirrors
``tests/test_logstore_sink.py``; the mocked-Firestore-client setup mirrors
``tests/test_logstore_firestore_sink.py``.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import time
import unittest
from unittest.mock import patch, MagicMock

from apps.backend.logstore import pipeline
from apps.backend.logstore.sink import SinkThread
from apps.backend.logstore.schema import build_batch_document
from apps.backend.logstore.firestore_sink import FirestoreSink
from apps.backend.logstore.schema import LOGS_COLLECTION, PRESENCE_COLLECTION, STATS_COLLECTION
# Named imports, not `import ... as emit_mod` -- apps/backend/observability/__init__.py
# does `from .emit import emit, get_queue, ...`, which rebinds the *package's* `emit`
# attribute to this function. Any attribute-traversal form (`import a.b.emit as x`,
# `from a.b import emit`) resolves through that shadowed attribute and silently returns
# the function instead of the submodule. Importing the names directly from the submodule
# path, as here, goes through the submodule's own namespace instead and isn't affected.
from apps.backend.observability.emit import emit as observability_emit, get_queue as observability_get_queue
from apps.backend.observability.events import build_event


def _wait_until(predicate, timeout=2.0, interval=0.01):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


class FakeBackend:
    """Records every batch it receives -- same shape as test_logstore_sink.py's."""

    def __init__(self):
        self.batches = []

    def write_batch(self, events):
        self.batches.append(list(events))


class TestObservabilityFeedsTheSharedQueue(unittest.TestCase):

    def setUp(self):
        pipeline._queue = None
        pipeline._started = False
        self._env_patch = patch.dict(os.environ, {"SENTINELSCAN_TELEMETRY_ENABLED": "1"})
        self._env_patch.start()

    def tearDown(self):
        self._env_patch.stop()
        pipeline._queue = None
        pipeline._started = False

    def test_emit_and_pipeline_share_the_same_queue_object(self):
        """The fix, stated directly: observability.emit no longer owns a private queue."""
        self.assertIs(observability_get_queue(), pipeline.get_queue())

    def test_backend_event_flows_through_the_real_sink_thread_to_a_backend(self):
        """End-to-end proof: emit() -> shared queue -> a real SinkThread -> the backend.

        This is exactly the path that was broken before the merge: emit() used to enqueue
        onto a queue nothing drained, so an event like this would never have reached any
        backend at all.
        """
        backend = FakeBackend()
        sink = SinkThread(
            pipeline.get_queue(), backend,
            flush_count=1, flush_interval_seconds=10.0,
            poll_timeout_seconds=0.02,
        )
        sink.start()
        self.addCleanup(lambda: sink.stop(drain=False))

        observability_emit(
            level="error", source="backend", category="error",
            message="unhandled exception in worker",
            trace_id="trace-1", session_id="session-1", scan_id="scan-1",
        )

        self.assertTrue(_wait_until(lambda: len(backend.batches) == 1))
        [written_event] = backend.batches[0]
        self.assertEqual(written_event["category"], "error")
        self.assertEqual(written_event["trace_id"], "trace-1")
        self.assertEqual(written_event["session_id"], "session-1")
        self.assertEqual(written_event["scan_id"], "scan-1")


class TestBackendEventSchemaCompatibility(unittest.TestCase):
    """Confirms observability.events.build_event's real output -- not a hand-shaped stand-in
    dict -- is accepted end-to-end by the logstore write path it now actually reaches."""

    def test_build_batch_document_denormalizes_ids_from_a_real_backend_event(self):
        event = build_event(
            level="info", source="agent", category="agent",
            message="AI selected port_scan", trace_id="trace-2",
            session_id="session-2", scan_id="scan-2",
        )
        batch = build_batch_document([event])

        self.assertEqual(batch["session_ids"], ["session-2"])
        self.assertEqual(batch["trace_ids"], ["trace-2"])
        self.assertEqual(batch["scan_ids"], ["scan-2"])
        self.assertEqual(batch["event_count"], 1)

    @patch("apps.backend.logstore.firestore_sink.get_db")
    def test_firestore_sink_accepts_a_real_backend_event_without_raising(self, mock_get_db):
        collections = {
            LOGS_COLLECTION: MagicMock(),
            STATS_COLLECTION: MagicMock(),
            PRESENCE_COLLECTION: MagicMock(),
        }
        db = MagicMock()
        db.collection.side_effect = lambda name: collections[name]
        mock_get_db.return_value = db

        event = build_event(
            level="warn", source="backend", category="http",
            message="GET /api/scan -> 429", trace_id="trace-3",
            session_id="session-3", scan_id=None,
        )
        FirestoreSink().write_batch([event])

        collections[LOGS_COLLECTION].document.assert_called_once()
        collections[PRESENCE_COLLECTION].document.assert_called_once_with("session-3")


if __name__ == "__main__":
    unittest.main()
