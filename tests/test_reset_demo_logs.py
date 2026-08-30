"""Tests for scripts/reset_demo_logs.py -- the delete-then-reseed tool for the demo
observability data sitting in the live Firestore project (see NEXT_TASK.md's integration
checklist item 3).

Two properties matter here, both direct consequences of Firestore quirks documented in the
script's own module docstring:

1. Running the tool twice over the same date range must not double the `stats/{date}`
   counters -- they're additive (`firestore.Increment`), so a reseed that doesn't clear them
   first would silently double every number.
2. The full-wipe collections (including `uptime/`) must end up containing exactly what the
   reseed wrote, not a merge with whatever was there before -- `uptime/`'s seeded documents in
   particular use a plain overwrite `.set()`, so any pre-existing document must be gone first,
   not merged into.

`scripts/` is not a package, so the module is loaded by path rather than imported (matching
tests/test_seed_fake_logs.py's own approach).
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from tests._fake_firestore import FakeFirestoreClient

_RESET_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "scripts", "reset_demo_logs.py",
)


def _load_reset_module():
    spec = importlib.util.spec_from_file_location("reset_demo_logs", _RESET_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reset_demo_logs = _load_reset_module()

_DAYS = 3
_SESSIONS_PER_DAY = 2


class TestResetDemoLogs(unittest.TestCase):

    def setUp(self):
        self.db = FakeFirestoreClient()
        for target in (
            "apps.backend.logstore.firestore_sink.get_db",
            "apps.backend.logstore.rollup.get_db",
        ):
            patcher = patch(target, return_value=self.db)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _run_once(self, seed: int):
        reset_demo_logs._delete_collection(self.db, "logs")
        reset_demo_logs._delete_collection(self.db, "presence")
        reset_demo_logs._delete_collection(self.db, "logs_hourly")
        reset_demo_logs._delete_collection(self.db, "logs_meta")
        reset_demo_logs._delete_collection(self.db, "uptime")
        reset_demo_logs._delete_stats_range(self.db, _DAYS)
        return reset_demo_logs._reseed(self.db, _DAYS, _SESSIONS_PER_DAY, seed)

    def _stats_snapshot(self):
        return {
            doc_id: dict(data)
            for doc_id, data in self.db.collection("stats").docs.items()
        }

    def test_running_twice_does_not_double_stats_counters(self):
        self._run_once(seed=1)
        first = self._stats_snapshot()

        self._run_once(seed=1)
        second = self._stats_snapshot()

        for date_str, counters in first.items():
            self.assertIn(date_str, second)
            for key in ("events", "requests", "llm_calls"):
                if key in counters:
                    self.assertEqual(
                        second[date_str][key], counters[key],
                        f"stats/{date_str}.{key} doubled on the second reset run",
                    )

    def test_stats_delete_is_scoped_to_the_reseeded_range_only(self):
        today = datetime.now(timezone.utc).date()
        outside_range = (today - timedelta(days=_DAYS + 5)).isoformat()
        self.db.collection("stats").document(outside_range).set({"events": 42})

        reset_demo_logs._delete_stats_range(self.db, _DAYS)

        self.assertIn(outside_range, self.db.collection("stats").docs)
        self.assertEqual(self.db.collection("stats").docs[outside_range]["events"], 42)

    def test_uptime_reset_replaces_rather_than_merges_existing_documents(self):
        today_str = datetime.now(timezone.utc).date().isoformat()
        # Simulates a real probe write that landed before the reset ran.
        self.db.collection("uptime").document(today_str).set(
            {"checks": 9999, "failures": 9999},
        )

        self._run_once(seed=2)

        self.assertNotEqual(
            self.db.collection("uptime").docs[today_str]["checks"], 9999,
            "the pre-existing document survived the wipe instead of being replaced",
        )

    def test_full_wipe_collections_end_up_empty_of_pre_existing_documents(self):
        self.db.collection("logs_meta").document("rollup_checkpoint").set(
            {"last_created_at": "stale"},
        )

        reset_demo_logs._delete_collection(self.db, "logs_meta")

        self.assertEqual(len(self.db.collection("logs_meta").docs), 0)


if __name__ == "__main__":
    unittest.main()
