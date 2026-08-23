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


class TestCheckpointIsAdvancedIncrementally(RollupTestCase):
    """A crash mid-run must not cost the whole run's progress.

    `_write_hour` uses Increment, which is additive rather than idempotent, so any hour
    reprocessed by a later run is double-counted. The checkpoint is what prevents that --
    and writing it only once, after every hour had been written, meant a crash anywhere in
    the loop threw away the record of everything that had already succeeded.
    """

    def _seed_batches(self, count):
        for i in range(count):
            seed_batch(
                self.db,
                [make_event(event_id=f"e{i}", ts="2026-08-10T14:00:00+00:00")],
                created_at=f"2026-08-10T14:{i:02d}:00+00:00",
            )

    def test_crash_mid_run_keeps_the_completed_chunks_checkpoint(self):
        self._seed_batches(rollup._CHECKPOINT_CHUNK_BATCHES + 5)

        real_write_hour = rollup._write_hour
        calls = {"n": 0}

        def failing_write_hour(db, hour_key, bucket):
            calls["n"] += 1
            if calls["n"] > 1:
                raise RuntimeError("simulated crash partway through the run")
            return real_write_hour(db, hour_key, bucket)

        with patch("apps.backend.logstore.rollup._write_hour", side_effect=failing_write_hour):
            with self.assertRaises(RuntimeError):
                rollup.run_rollup(now=_NOW)

        checkpoint = self.db.collection("logs_meta").document("rollup_checkpoint").get().to_dict()
        self.assertIsNotNone(checkpoint)
        self.assertEqual(
            checkpoint["last_processed_created_at"],
            f"2026-08-10T14:{rollup._CHECKPOINT_CHUNK_BATCHES - 1:02d}:00+00:00",
        )

    def test_rerun_after_a_crash_does_not_double_count_the_completed_chunk(self):
        self._seed_batches(rollup._CHECKPOINT_CHUNK_BATCHES + 5)

        real_write_hour = rollup._write_hour
        calls = {"n": 0}

        def failing_write_hour(db, hour_key, bucket):
            calls["n"] += 1
            if calls["n"] > 1:
                raise RuntimeError("simulated crash partway through the run")
            return real_write_hour(db, hour_key, bucket)

        with patch("apps.backend.logstore.rollup._write_hour", side_effect=failing_write_hour):
            with self.assertRaises(RuntimeError):
                rollup.run_rollup(now=_NOW)

        rollup.run_rollup(now=_NOW)

        bucket = self.db.collection("logs_hourly").document("2026-08-10T14").get().to_dict()
        self.assertEqual(bucket["event_count"], rollup._CHECKPOINT_CHUNK_BATCHES + 5)


if __name__ == "__main__":
    unittest.main()
