"""Tests for apps.backend.logstore.query -- the 10 frozen-signature read functions Workstream
C's log site codes against, plus the internal get_write_budget_status circuit-breaker helper.

Uses tests/_fake_firestore.py (an in-memory fake) rather than a live Firestore project or
hand-built MagicMock chains, since query.py's `.where().where().order_by().limit().stream()`
chains have too many filter combinations to mock call-by-call readably.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from unittest.mock import patch

from apps.backend.logstore import query
from apps.backend.logstore.schema import build_batch_document
from tests._fake_firestore import FakeFirestoreClient


def make_event(**overrides):
    event = {
        "event_id": "e1", "ts": "2026-08-22T10:00:00+00:00", "level": "info",
        "source": "backend", "category": "http", "message": "ok",
        "trace_id": None, "session_id": None, "uid": None, "scan_id": None,
        "duration_ms": 5, "data": {}, "release": "dev", "env": "dev",
    }
    event.update(overrides)
    return event


def seed_batch(db: FakeFirestoreClient, events, created_at: str = None):
    doc = build_batch_document(events)
    if created_at:
        doc["created_at"] = created_at
    db.seed("logs", doc["batch_id"], doc)
    return doc


class QueryTestCase(unittest.TestCase):
    """Base class: patches get_db to a fresh FakeFirestoreClient, and resets the
    write-budget cache (module-level state in query.py) between tests."""

    def setUp(self):
        self.db = FakeFirestoreClient()
        self._get_db_patcher = patch("apps.backend.logstore.query.get_db", return_value=self.db)
        self._get_db_patcher.start()
        self.addCleanup(self._get_db_patcher.stop)
        query._write_budget_cache = None
        query._write_budget_cache_at = 0.0


class TestQueryEvents(QueryTestCase):

    def test_no_db_returns_empty_result(self):
        with patch("apps.backend.logstore.query.get_db", return_value=None):
            self.assertEqual(query.query_events(), {"events": [], "next_cursor": None})

    def test_filters_by_level_and_category(self):
        seed_batch(self.db, [
            make_event(event_id="e1", level="error", category="http"),
            make_event(event_id="e2", level="info", category="http"),
            make_event(event_id="e3", level="error", category="worker"),
        ])
        result = query.query_events(level="error", category="http")
        self.assertEqual([e["event_id"] for e in result["events"]], ["e1"])

    def test_filters_by_session_id_uses_array_contains(self):
        seed_batch(self.db, [
            make_event(event_id="e1", session_id="s1"),
            make_event(event_id="e2", session_id="s2"),
        ])
        result = query.query_events(session_id="s1")
        self.assertEqual([e["event_id"] for e in result["events"]], ["e1"])

    def test_since_until_filter_on_event_ts(self):
        seed_batch(self.db, [
            make_event(event_id="e1", ts="2026-08-22T09:00:00+00:00"),
            make_event(event_id="e2", ts="2026-08-22T10:00:00+00:00"),
            make_event(event_id="e3", ts="2026-08-22T11:00:00+00:00"),
        ], created_at="2026-08-22T09:30:00+00:00")
        result = query.query_events(
            since="2026-08-22T09:30:00+00:00", until="2026-08-22T10:30:00+00:00",
        )
        self.assertEqual([e["event_id"] for e in result["events"]], ["e2"])

    def test_pagination_returns_cursor_when_more_remain(self):
        events = [make_event(event_id=f"e{i}", ts=f"2026-08-22T10:00:{i:02d}+00:00") for i in range(5)]
        seed_batch(self.db, events)

        page1 = query.query_events(limit=2)
        self.assertEqual([e["event_id"] for e in page1["events"]], ["e0", "e1"])
        self.assertIsNotNone(page1["next_cursor"])

        page2 = query.query_events(limit=2, cursor=page1["next_cursor"])
        self.assertEqual([e["event_id"] for e in page2["events"]], ["e2", "e3"])

        page3 = query.query_events(limit=2, cursor=page2["next_cursor"])
        self.assertEqual([e["event_id"] for e in page3["events"]], ["e4"])
        self.assertIsNone(page3["next_cursor"])

    def test_limit_is_clamped_to_max(self):
        events = [make_event(event_id=f"e{i}", ts=f"2026-08-22T10:00:{i:02d}+00:00") for i in range(3)]
        seed_batch(self.db, events)
        result = query.query_events(limit=query.MAX_QUERY_LIMIT + 100)
        self.assertEqual(len(result["events"]), 3)

    def test_empty_collection_returns_empty_result(self):
        self.assertEqual(query.query_events(), {"events": [], "next_cursor": None})


class TestGetTrace(QueryTestCase):

    def test_returns_only_events_sharing_trace_id(self):
        seed_batch(self.db, [
            make_event(event_id="e1", trace_id="t1"),
            make_event(event_id="e2", trace_id="t2"),
            make_event(event_id="e3", trace_id="t1"),
        ])
        result = query.get_trace("t1")
        self.assertEqual(result["trace_id"], "t1")
        self.assertEqual({e["event_id"] for e in result["events"]}, {"e1", "e3"})

    def test_no_db_returns_empty_events(self):
        with patch("apps.backend.logstore.query.get_db", return_value=None):
            result = query.get_trace("t1")
        self.assertEqual(result, {"trace_id": "t1", "events": []})

    def test_unknown_trace_id_returns_empty_events(self):
        seed_batch(self.db, [make_event(trace_id="t1")])
        result = query.get_trace("does-not-exist")
        self.assertEqual(result["events"], [])


class TestGetSessionTimeline(QueryTestCase):

    def test_orders_events_and_derives_started_last_seen(self):
        seed_batch(self.db, [
            make_event(event_id="e2", session_id="s1", ts="2026-08-22T10:05:00+00:00", uid="u1"),
            make_event(event_id="e1", session_id="s1", ts="2026-08-22T10:00:00+00:00", uid="u1"),
        ])
        result = query.get_session_timeline("s1")
        self.assertEqual([e["event_id"] for e in result["events"]], ["e1", "e2"])
        self.assertEqual(result["started_at"], "2026-08-22T10:00:00+00:00")
        self.assertEqual(result["last_seen"], "2026-08-22T10:05:00+00:00")
        self.assertEqual(result["uid"], "u1")

    def test_unknown_session_returns_empty_timeline(self):
        result = query.get_session_timeline("nope")
        self.assertEqual(result["events"], [])
        self.assertIsNone(result["started_at"])
        self.assertIsNone(result["uid"])


class TestListSessionsAndActiveUsers(QueryTestCase):

    def test_list_sessions_reads_presence_sorted_desc(self):
        self.db.seed("presence", "s1", {"session_id": "s1", "uid": "u1", "last_seen": "2026-08-22T10:00:00+00:00"})
        self.db.seed("presence", "s2", {"session_id": "s2", "uid": "u2", "last_seen": "2026-08-22T11:00:00+00:00"})

        sessions = query.list_sessions()
        self.assertEqual([s["session_id"] for s in sessions], ["s2", "s1"])

    def test_list_sessions_empty_presence_returns_empty_list(self):
        self.assertEqual(query.list_sessions(), [])

    def test_list_sessions_no_db_returns_empty_list(self):
        with patch("apps.backend.logstore.query.get_db", return_value=None):
            self.assertEqual(query.list_sessions(), [])

    @patch("apps.backend.logstore.query.datetime")
    def test_count_active_users_only_counts_recent_presence(self, mock_datetime):
        from datetime import datetime as real_datetime, timezone
        mock_datetime.now.return_value = real_datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
        mock_datetime.fromisoformat.side_effect = real_datetime.fromisoformat

        self.db.seed("presence", "recent", {"session_id": "recent", "uid": None, "last_seen": "2026-08-22T11:58:00+00:00"})
        self.db.seed("presence", "stale", {"session_id": "stale", "uid": None, "last_seen": "2026-08-22T11:00:00+00:00"})

        result = query.count_active_users(window_minutes=5)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["sessions"][0]["session_id"], "recent")


class TestGetDailyStats(QueryTestCase):

    def test_reads_counters_and_unique_sessions_from_stats_doc(self):
        self.db.seed("stats", "2026-08-22", {
            "events": 10, "errors": 2, "requests": 5, "scans": 1,
            "llm_calls": 3, "llm_tokens": 900, "session_ids": ["s1", "s2", "s3"],
        })
        result = query.get_daily_stats("2026-08-22")
        self.assertEqual(result["date"], "2026-08-22")
        self.assertEqual(result["events"], 10)
        self.assertEqual(result["unique_sessions"], 3)

    def test_missing_date_returns_zeroed_shape(self):
        result = query.get_daily_stats("2026-01-01")
        self.assertEqual(result["events"], 0)
        self.assertEqual(result["unique_sessions"], 0)

    def test_no_db_returns_zeroed_shape(self):
        with patch("apps.backend.logstore.query.get_db", return_value=None):
            result = query.get_daily_stats("2026-08-22")
        self.assertEqual(result["events"], 0)


class TestWriteBudgetStatus(QueryTestCase):

    def test_near_cap_when_writes_at_or_above_warn_ratio(self):
        self.db.seed("stats", "2026-08-22", {"firestore_writes": query._DAILY_WRITE_BUDGET})
        result = query.get_write_budget_status("2026-08-22")
        self.assertTrue(result["near_cap"])

    def test_not_near_cap_when_writes_low(self):
        self.db.seed("stats", "2026-08-22", {"firestore_writes": 10})
        result = query.get_write_budget_status("2026-08-22")
        self.assertFalse(result["near_cap"])

    def test_default_date_call_is_cached(self):
        self.db.seed("stats", "2026-08-22", {"firestore_writes": 10})
        first = query.get_write_budget_status()
        # Mutate the underlying doc directly -- a second no-date call within the cache
        # window must not see this, since it should be served from cache.
        self.db.collection("stats").docs["2026-08-22"]["firestore_writes"] = 999999
        second = query.get_write_budget_status()
        self.assertEqual(first, second)

    def test_no_db_returns_not_near_cap(self):
        with patch("apps.backend.logstore.query.get_db", return_value=None):
            result = query.get_write_budget_status("2026-08-22")
        self.assertFalse(result["near_cap"])
        self.assertEqual(result["writes_today"], 0)


class TestGetLlmUsage(QueryTestCase):

    def test_sums_recent_raw_llm_events_into_day_buckets(self):
        seed_batch(self.db, [
            make_event(
                event_id="e1", category="llm", ts="2026-08-22T10:00:00+00:00",
                data={"prompt_tokens": 100, "response_tokens": 50, "total_tokens": 150, "cached": False},
            ),
            make_event(
                event_id="e2", category="llm", ts="2026-08-22T11:00:00+00:00",
                data={"prompt_tokens": 20, "response_tokens": 10, "total_tokens": 30, "cached": True},
            ),
            make_event(event_id="e3", category="http", ts="2026-08-22T10:00:00+00:00"),
        ])
        result = query.get_llm_usage(since="2026-08-22T00:00:00+00:00", until="2026-08-22T23:59:59+00:00")
        self.assertEqual(result["calls"], 2)
        self.assertEqual(result["total_tokens"], 180)
        self.assertEqual(result["cache_hits"], 1)
        self.assertEqual(result["buckets"], [{"bucket": "2026-08-22", "tokens": 180, "calls": 2}])

    def test_blends_in_rollup_for_older_range(self):
        self.db.seed("logs_hourly", "2026-08-01T14", {
            "llm": {"calls": 5, "prompt_tokens": 500, "response_tokens": 250, "total_tokens": 750, "cache_hits": 2},
        })
        result = query.get_llm_usage(
            since="2026-08-01T14:00:00+00:00", until="2026-08-01T14:59:00+00:00", group_by="hour",
        )
        self.assertEqual(result["calls"], 5)
        self.assertEqual(result["total_tokens"], 750)
        self.assertEqual(result["buckets"], [{"bucket": "2026-08-01T14", "tokens": 750, "calls": 5}])

    def test_no_db_returns_empty_shape(self):
        with patch("apps.backend.logstore.query.get_db", return_value=None):
            result = query.get_llm_usage()
        self.assertEqual(result["calls"], 0)
        self.assertEqual(result["buckets"], [])


class TestGetHealthSnapshot(QueryTestCase):

    @patch("apps.backend.logstore.query.datetime")
    def test_derives_error_rate_latency_and_worker_breakdown(self, mock_datetime):
        from datetime import datetime as real_datetime, timezone
        mock_datetime.now.return_value = real_datetime(2026, 8, 22, 10, 30, tzinfo=timezone.utc)
        mock_datetime.fromisoformat.side_effect = real_datetime.fromisoformat

        seed_batch(self.db, [
            make_event(event_id="e1", category="http", level="info", duration_ms=100, ts="2026-08-22T10:05:00+00:00"),
            make_event(event_id="e2", category="http", level="error", duration_ms=400, ts="2026-08-22T10:10:00+00:00"),
            make_event(
                event_id="e3", category="worker", level="info", ts="2026-08-22T10:15:00+00:00",
                data={"logger": "apps.backend.workers.ssl_worker"},
            ),
            make_event(
                event_id="e4", category="worker", level="error", ts="2026-08-22T10:20:00+00:00",
                data={"logger": "apps.backend.workers.ssl_worker"},
            ),
            make_event(
                event_id="e5", category="llm", level="error", ts="2026-08-22T10:25:00+00:00",
                data={"model": "gemini"},
            ),
        ], created_at="2026-08-22T10:25:00+00:00")
        result = query.get_health_snapshot()

        self.assertEqual(result["requests_1h"], 2)
        # 3 of 5 events are error/fatal: e2 (http), e4 (worker), e5 (llm).
        self.assertAlmostEqual(result["error_rate"], 3 / 5)
        self.assertEqual(result["llm_failure_rate"], 1.0)
        self.assertEqual(len(result["workers"]), 1)
        worker = result["workers"][0]
        self.assertEqual(worker["name"], "ssl_worker")
        self.assertEqual(worker["ok"], 1)
        self.assertEqual(worker["failed"], 1)
        self.assertEqual(worker["success_rate"], 0.5)

    def test_no_events_returns_zeroed_shape(self):
        result = query.get_health_snapshot()
        self.assertEqual(result["requests_1h"], 0)
        self.assertEqual(result["error_rate"], 0.0)
        self.assertEqual(result["workers"], [])

    def test_no_db_returns_zeroed_shape(self):
        with patch("apps.backend.logstore.query.get_db", return_value=None):
            result = query.get_health_snapshot()
        self.assertEqual(result["requests_1h"], 0)


class TestUptime(QueryTestCase):

    def test_record_uptime_probe_increments_checks_and_failures(self):
        query.record_uptime_probe({"ok": True})
        query.record_uptime_probe({"ok": False})
        query.record_uptime_probe({"ok": True})

        today = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).date().isoformat()
        doc = self.db.collection("uptime").docs[today]
        self.assertEqual(doc["checks"], 3)
        self.assertEqual(doc["failures"], 1)

    def test_record_uptime_probe_no_db_is_noop(self):
        with patch("apps.backend.logstore.query.get_db", return_value=None):
            query.record_uptime_probe({"ok": True})  # must not raise

    def test_get_uptime_history_computes_percentage_and_handles_missing_days(self):
        self.db.seed("uptime", "2026-08-22", {"checks": 100, "failures": 5})
        history = query.get_uptime_history(days=2)
        self.assertEqual(len(history), 2)
        today_entry = history[-1]
        self.assertEqual(today_entry["date"], "2026-08-22")
        self.assertEqual(today_entry["uptime_pct"], 95.0)
        missing_entry = history[0]
        self.assertIsNone(missing_entry["uptime_pct"])
        self.assertEqual(missing_entry["checks"], 0)

    def test_get_uptime_history_no_db_returns_empty_list(self):
        with patch("apps.backend.logstore.query.get_db", return_value=None):
            self.assertEqual(query.get_uptime_history(), [])


if __name__ == "__main__":
    unittest.main()
