"""Tests for apps.backend.logstore.rollup -- collapsing raw batches older than
RAW_RETENTION_DAYS into hourly logs_hourly/ summaries, with checkpoint-based idempotence.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from apps.backend.logstore import rollup
from apps.backend.logstore.schema import build_batch_document
from tests._fake_firestore import FakeFirestoreClient


def make_event(**overrides):
    event = {
        "event_id": "e1", "ts": "2026-08-10T14:00:00+00:00", "level": "info",
        "source": "backend", "category": "http", "message": "ok",
        "trace_id": None, "session_id": None, "uid": None, "scan_id": None,
        "duration_ms": 5, "data": {}, "release": "dev", "env": "dev",
    }
    event.update(overrides)
    return event


def seed_batch(db: FakeFirestoreClient, events, created_at: str):
    doc = build_batch_document(events)
    doc["created_at"] = created_at
    db.seed("logs", doc["batch_id"], doc)
    return doc


_NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)  # events at 2026-08-10 are well past
# RAW_RETENTION_DAYS (7) relative to this fixed "now".


class RollupTestCase(unittest.TestCase):
    def setUp(self):
        self.db = FakeFirestoreClient()
        self._get_db_patcher = patch("apps.backend.logstore.rollup.get_db", return_value=self.db)
        self._get_db_patcher.start()
        self.addCleanup(self._get_db_patcher.stop)


class TestRunRollup(RollupTestCase):

    def test_no_db_is_noop(self):
        with patch("apps.backend.logstore.rollup.get_db", return_value=None):
            result = rollup.run_rollup(now=_NOW)
        self.assertEqual(result, {"batches_processed": 0, "hours_written": 0, "checkpoint": None})

    def test_nothing_older_than_retention_window_is_a_noop(self):
        seed_batch(self.db, [make_event(ts="2026-08-22T11:00:00+00:00")], created_at="2026-08-22T11:00:00+00:00")
        result = rollup.run_rollup(now=_NOW)
        self.assertEqual(result["batches_processed"], 0)

    def test_aggregates_old_batch_into_hourly_bucket(self):
        seed_batch(self.db, [
            make_event(event_id="e1", ts="2026-08-10T14:05:00+00:00", level="info", category="http", duration_ms=100),
            make_event(event_id="e2", ts="2026-08-10T14:10:00+00:00", level="error", category="http", duration_ms=300),
            make_event(
                event_id="e3", ts="2026-08-10T14:15:00+00:00", category="llm",
                data={"prompt_tokens": 10, "response_tokens": 5, "total_tokens": 15, "cached": True},
            ),
        ], created_at="2026-08-10T14:20:00+00:00")

        result = rollup.run_rollup(now=_NOW)

        self.assertEqual(result["batches_processed"], 1)
        self.assertEqual(result["hours_written"], 1)

        bucket = self.db.collection("logs_hourly").docs["2026-08-10T14"]
        self.assertEqual(bucket["event_count"], 3)
        self.assertEqual(bucket["by_level"]["info"], 2)  # e1 and e3 (default level)
        self.assertEqual(bucket["by_level"]["error"], 1)
        self.assertEqual(bucket["by_category"]["http"], 2)
        self.assertEqual(bucket["by_category"]["llm"], 1)
        self.assertEqual(bucket["http"]["count"], 2)
        self.assertEqual(bucket["http"]["duration_ms_sum"], 400)
        self.assertEqual(bucket["http"]["error_count"], 1)
        self.assertEqual(bucket["llm"]["total_tokens"], 15)
        self.assertEqual(bucket["llm"]["cache_hits"], 1)

    def test_events_spanning_two_hours_split_into_two_buckets(self):
        seed_batch(self.db, [
            make_event(event_id="e1", ts="2026-08-10T14:55:00+00:00"),
            make_event(event_id="e2", ts="2026-08-10T15:05:00+00:00"),
        ], created_at="2026-08-10T15:06:00+00:00")

        result = rollup.run_rollup(now=_NOW)

        self.assertEqual(result["hours_written"], 2)
        self.assertEqual(self.db.collection("logs_hourly").docs["2026-08-10T14"]["event_count"], 1)
        self.assertEqual(self.db.collection("logs_hourly").docs["2026-08-10T15"]["event_count"], 1)

    def test_checkpoint_advances_and_prevents_reprocessing(self):
        seed_batch(self.db, [make_event(ts="2026-08-10T14:00:00+00:00")], created_at="2026-08-10T14:20:00+00:00")

        first = rollup.run_rollup(now=_NOW)
        self.assertEqual(first["batches_processed"], 1)

        second = rollup.run_rollup(now=_NOW)
        self.assertEqual(second["batches_processed"], 0)

        # The bucket's event_count must still be 1, not double-counted by the second run.
        bucket = self.db.collection("logs_hourly").docs["2026-08-10T14"]
        self.assertEqual(bucket["event_count"], 1)

    def test_a_new_batch_after_checkpoint_is_picked_up_by_a_later_run(self):
        seed_batch(self.db, [make_event(event_id="e1", ts="2026-08-10T14:00:00+00:00")], created_at="2026-08-10T14:20:00+00:00")
        rollup.run_rollup(now=_NOW)

        seed_batch(self.db, [make_event(event_id="e2", ts="2026-08-10T16:00:00+00:00")], created_at="2026-08-10T16:20:00+00:00")
        second = rollup.run_rollup(now=_NOW)

        self.assertEqual(second["batches_processed"], 1)
        self.assertEqual(self.db.collection("logs_hourly").docs["2026-08-10T16"]["event_count"], 1)
        # First hour's bucket is untouched by the second run.
        self.assertEqual(self.db.collection("logs_hourly").docs["2026-08-10T14"]["event_count"], 1)

    def test_repeated_merge_writes_do_not_clobber_other_levels_in_the_same_bucket(self):
        seed_batch(self.db, [
            make_event(event_id="e1", ts="2026-08-10T14:00:00+00:00", level="info"),
        ], created_at="2026-08-10T14:05:00+00:00")
        rollup.run_rollup(now=_NOW)

        seed_batch(self.db, [
            make_event(event_id="e2", ts="2026-08-10T14:30:00+00:00", level="error"),
        ], created_at="2026-08-10T14:35:00+00:00")
        rollup.run_rollup(now=_NOW)

        bucket = self.db.collection("logs_hourly").docs["2026-08-10T14"]
        self.assertEqual(bucket["by_level"]["info"], 1)
        self.assertEqual(bucket["by_level"]["error"], 1)
        self.assertEqual(bucket["event_count"], 2)


if __name__ == "__main__":
    unittest.main()
