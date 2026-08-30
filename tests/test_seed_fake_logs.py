"""Tests for scripts/seed_fake_logs.py -- the fake-data seeder Workstream C's log site
is built against before Workstreams A and B are live.

The property that actually matters here is not "did it write documents" but "can the read
API find them again". query.py filters on a batch's `created_at` first and tolerates only
`_CREATED_AT_SKEW` of drift from an event's own `ts`, so a seeder that stamps a whole day's
batches at one fixed time produces data that is present in Firestore and invisible to every
time-range query -- which is most of what the log site does.

`scripts/` is not a package, so the module is loaded by path rather than imported.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import importlib.util
import random
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

from apps.backend.logstore import query
from apps.backend.logstore.firestore_sink import FirestoreSink
from apps.backend.logstore.query import _CREATED_AT_SKEW
from tests._fake_firestore import FakeFirestoreClient

_SEED_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "scripts", "seed_fake_logs.py",
)


def _load_seed_module():
    spec = importlib.util.spec_from_file_location("seed_fake_logs", _SEED_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


seed_fake_logs = _load_seed_module()

_SEEDED_DAY = date(2026, 8, 10)


class TestSeededDayIsQueryable(unittest.TestCase):

    def setUp(self):
        self.db = FakeFirestoreClient()
        for target in (
            "apps.backend.logstore.firestore_sink.get_db",
            "apps.backend.logstore.query.get_db",
        ):
            patcher = patch(target, return_value=self.db)
            patcher.start()
            self.addCleanup(patcher.stop)
        query._write_budget_cache = None
        query._write_budget_cache_at = 0.0

        seed_fake_logs._seed_day(
            FirestoreSink(), random.Random(42), _SEEDED_DAY,
            sessions_per_day=3, is_today=False,
        )

    def _batches(self):
        return list(self.db.collection("logs").docs.values())

    def test_a_seeded_day_is_reachable_by_a_time_range_query(self):
        result = query.query_events(
            since=f"{_SEEDED_DAY.isoformat()}T00:00:00+00:00",
            until=f"{_SEEDED_DAY.isoformat()}T23:59:59+00:00",
            limit=500,
        )
        self.assertGreater(len(result["events"]), 0)

    def test_every_seeded_event_is_returned_by_that_query(self):
        seeded = sum(batch["event_count"] for batch in self._batches())
        result = query.query_events(
            since=f"{_SEEDED_DAY.isoformat()}T00:00:00+00:00",
            until=f"{_SEEDED_DAY.isoformat()}T23:59:59+00:00",
            limit=500,
        )
        self.assertEqual(len(result["events"]), seeded)

    def test_each_batch_is_stamped_close_to_its_own_events(self):
        for batch in self._batches():
            created_at = datetime.fromisoformat(batch["created_at"])
            newest_event = max(
                datetime.fromisoformat(event["ts"]) for event in batch["events"]
            )
            self.assertLessEqual(created_at - newest_event, _CREATED_AT_SKEW)
            self.assertGreaterEqual(created_at, newest_event)

    def test_narrow_window_inside_the_day_returns_only_that_window(self):
        # The failure this guards against is total, not partial: a fixed daily `created_at`
        # makes every window that does not contain it return nothing at all.
        events = query.query_events(
            since=f"{_SEEDED_DAY.isoformat()}T00:00:00+00:00",
            until=f"{_SEEDED_DAY.isoformat()}T23:59:59+00:00",
            limit=500,
        )["events"]
        first_ts = datetime.fromisoformat(events[0]["ts"])
        window = query.query_events(
            since=first_ts.isoformat(),
            until=(first_ts + timedelta(minutes=1)).isoformat(),
            limit=500,
        )["events"]
        self.assertGreater(len(window), 0)
        self.assertLessEqual(len(window), len(events))


if __name__ == "__main__":
    unittest.main()
