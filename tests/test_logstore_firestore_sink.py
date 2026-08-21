"""Tests for apps.backend.logstore.firestore_sink -- the Firestore write path.

Mocks get_db() so no live Firestore project is needed, following the same
collection-name-keyed mocking pattern tests/test_dev_routes.py already uses for the
rest of the app's Firebase-backed code.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from unittest.mock import patch, MagicMock

from apps.backend.logstore.firestore_sink import FirestoreSink
from apps.backend.logstore.schema import LOGS_COLLECTION, PRESENCE_COLLECTION, STATS_COLLECTION


def make_event(**overrides):
    event = {
        "event_id": "e1", "ts": "2026-08-22T10:00:00+00:00", "level": "info",
        "source": "backend", "category": "http", "message": "ok",
        "trace_id": "t1", "session_id": "s1", "uid": "u1", "scan_id": None,
        "duration_ms": 5, "data": {}, "release": "dev", "env": "dev",
    }
    event.update(overrides)
    return event


def _mock_db():
    """Builds a fake Firestore client with one distinct child mock per top-level
    collection, keyed further by document id where the test cares about that."""
    collections = {
        LOGS_COLLECTION: MagicMock(),
        STATS_COLLECTION: MagicMock(),
        PRESENCE_COLLECTION: MagicMock(),
    }
    db = MagicMock()
    db.collection.side_effect = lambda name: collections[name]
    return db, collections


class TestFirestoreSink(unittest.TestCase):

    @patch("apps.backend.logstore.firestore_sink.get_db")
    def test_degrades_to_noop_when_db_unconfigured(self, mock_get_db):
        mock_get_db.return_value = None
        # Must not raise even with events queued -- the sink thread treats any
        # exception as retryable, so a "not configured" state must be a clean no-op.
        FirestoreSink().write_batch([make_event()])

    @patch("apps.backend.logstore.firestore_sink.get_db")
    def test_empty_batch_is_a_noop(self, mock_get_db):
        db, collections = _mock_db()
        mock_get_db.return_value = db

        FirestoreSink().write_batch([])

        db.collection.assert_not_called()

    @patch("apps.backend.logstore.firestore_sink.get_db")
    def test_writes_one_batch_document_with_denormalized_ids(self, mock_get_db):
        db, collections = _mock_db()
        mock_get_db.return_value = db
        events = [make_event(event_id="e1", session_id="s1"), make_event(event_id="e2", session_id="s2")]

        FirestoreSink().write_batch(events)

        logs_doc = collections[LOGS_COLLECTION].document.return_value
        logs_doc.set.assert_called_once()
        written = logs_doc.set.call_args[0][0]
        self.assertEqual(written["event_count"], 2)
        self.assertEqual(sorted(written["session_ids"]), ["s1", "s2"])
        collections[LOGS_COLLECTION].document.assert_called_once_with(written["batch_id"])

    @patch("apps.backend.logstore.firestore_sink.get_db")
    def test_stats_counters_incremented_per_date(self, mock_get_db):
        db, collections = _mock_db()
        mock_get_db.return_value = db
        events = [
            make_event(category="http", level="info"),
            make_event(category="error", level="error"),
            make_event(category="llm", level="info", data={"total_tokens": 42}),
        ]

        FirestoreSink().write_batch(events)

        stats_doc = collections[STATS_COLLECTION].document.return_value
        stats_doc.set.assert_called_once()
        payload, kwargs = stats_doc.set.call_args
        self.assertTrue(kwargs.get("merge"))

    @patch("apps.backend.logstore.firestore_sink.get_db")
    def test_stats_split_across_two_dates_writes_two_documents(self, mock_get_db):
        db, collections = _mock_db()
        mock_get_db.return_value = db
        date_docs = {}
        collections[STATS_COLLECTION].document.side_effect = lambda date: date_docs.setdefault(date, MagicMock())
        events = [
            make_event(ts="2026-08-21T23:59:00+00:00"),
            make_event(ts="2026-08-22T00:01:00+00:00"),
        ]

        FirestoreSink().write_batch(events)

        self.assertEqual(set(date_docs.keys()), {"2026-08-21", "2026-08-22"})
        for doc in date_docs.values():
            doc.set.assert_called_once()

    @patch("apps.backend.logstore.firestore_sink.get_db")
    def test_presence_upserted_per_session_using_latest_event(self, mock_get_db):
        db, collections = _mock_db()
        mock_get_db.return_value = db
        session_docs = {}
        collections[PRESENCE_COLLECTION].document.side_effect = lambda sid: session_docs.setdefault(sid, MagicMock())
        events = [
            make_event(session_id="s1", ts="2026-08-22T10:00:00+00:00", uid="u1"),
            make_event(session_id="s1", ts="2026-08-22T10:05:00+00:00", uid="u1"),
            make_event(session_id=None),
        ]

        FirestoreSink().write_batch(events)

        self.assertEqual(set(session_docs.keys()), {"s1"})
        payload, kwargs = session_docs["s1"].set.call_args
        self.assertEqual(payload[0]["last_seen"], "2026-08-22T10:05:00+00:00")
        self.assertTrue(kwargs.get("merge"))


if __name__ == "__main__":
    unittest.main()
