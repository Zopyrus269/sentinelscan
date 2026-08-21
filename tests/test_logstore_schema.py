"""Tests for apps.backend.logstore.schema -- the batch document shape."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from datetime import datetime

from apps.backend.logstore.schema import (
    TOTAL_RETENTION_DAYS,
    build_batch_document,
)


def make_event(**overrides):
    event = {
        "event_id": "e1", "ts": "2026-08-22T10:00:00+00:00", "level": "info",
        "source": "backend", "category": "http", "message": "ok",
        "trace_id": "t1", "session_id": "s1", "uid": "u1", "scan_id": None,
        "duration_ms": 5, "data": {}, "release": "dev", "env": "dev",
    }
    event.update(overrides)
    return event


class TestBuildBatchDocument(unittest.TestCase):

    def test_shape_and_event_count(self):
        events = [make_event(event_id="e1"), make_event(event_id="e2")]
        doc = build_batch_document(events)

        self.assertEqual(doc["event_count"], 2)
        self.assertEqual(doc["events"], events)
        self.assertIn("batch_id", doc)
        self.assertIn("created_at", doc)
        self.assertIn("expires_at", doc)

    def test_expires_at_honors_total_retention(self):
        doc = build_batch_document([make_event()])
        created_at = datetime.fromisoformat(doc["created_at"])
        delta = doc["expires_at"] - created_at
        self.assertEqual(delta.days, TOTAL_RETENTION_DAYS)

    def test_two_calls_get_distinct_batch_ids(self):
        doc1 = build_batch_document([make_event()])
        doc2 = build_batch_document([make_event()])
        self.assertNotEqual(doc1["batch_id"], doc2["batch_id"])

    def test_denormalized_ids_are_unique_sorted_and_exclude_null(self):
        events = [
            make_event(session_id="s2", trace_id="t1", scan_id=None),
            make_event(session_id="s1", trace_id="t1", scan_id="scan-1"),
            make_event(session_id=None, trace_id=None, scan_id=None),
        ]
        doc = build_batch_document(events)

        self.assertEqual(doc["session_ids"], ["s1", "s2"])
        self.assertEqual(doc["trace_ids"], ["t1"])
        self.assertEqual(doc["scan_ids"], ["scan-1"])

    def test_all_null_ids_produce_empty_lists(self):
        events = [make_event(session_id=None, trace_id=None, scan_id=None)]
        doc = build_batch_document(events)

        self.assertEqual(doc["session_ids"], [])
        self.assertEqual(doc["trace_ids"], [])
        self.assertEqual(doc["scan_ids"], [])


if __name__ == "__main__":
    unittest.main()
