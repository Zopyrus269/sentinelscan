"""Tests for apps.backend.logstore.sink -- the background draining/batching thread.

Uses a fake in-memory queue and a scriptable fake backend; no real Firestore needed.
Timing thresholds are set small so the suite stays fast, but this exercises the real
threading.Thread, not a mock of it -- the thread-safety guarantees are the point.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import queue
import time
import unittest

from apps.backend.logstore.sink import SinkThread


def _wait_until(predicate, timeout=2.0, interval=0.01):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def make_event(i):
    return {"event_id": str(i), "message": f"event {i}"}


class FakeBackend:
    """Records every batch it receives; can be scripted to fail N times or forever."""

    def __init__(self, fail_times=0, always_fail=False):
        self.batches = []
        self.calls = 0
        self.fail_times = fail_times
        self.always_fail = always_fail

    def write_batch(self, events):
        self.calls += 1
        if self.always_fail or self.calls <= self.fail_times:
            raise RuntimeError("simulated backend failure")
        self.batches.append(list(events))


class TestSinkThread(unittest.TestCase):

    def _make_sink(self, backend, flush_count=5, flush_interval_seconds=10.0,
                   max_retries=2, backoff_base_seconds=0.01, poll_timeout_seconds=0.02):
        q = queue.Queue()
        sink = SinkThread(
            q, backend,
            flush_count=flush_count,
            flush_interval_seconds=flush_interval_seconds,
            max_retries=max_retries,
            backoff_base_seconds=backoff_base_seconds,
            poll_timeout_seconds=poll_timeout_seconds,
        )
        sink.start()
        self.addCleanup(lambda: sink.stop(drain=False))
        return q, sink

    def test_flush_on_count_threshold(self):
        backend = FakeBackend()
        q, sink = self._make_sink(backend, flush_count=5, flush_interval_seconds=10.0)
        for i in range(5):
            q.put(make_event(i))

        self.assertTrue(_wait_until(lambda: len(backend.batches) == 1))
        self.assertEqual(len(backend.batches[0]), 5)

    def test_flush_on_time_threshold_before_count_reached(self):
        backend = FakeBackend()
        q, sink = self._make_sink(backend, flush_count=100, flush_interval_seconds=0.05)
        q.put(make_event(1))
        q.put(make_event(2))

        self.assertTrue(_wait_until(lambda: len(backend.batches) == 1, timeout=2.0))
        self.assertEqual(len(backend.batches[0]), 2)

    def test_retry_with_backoff_then_success(self):
        backend = FakeBackend(fail_times=2)
        q, sink = self._make_sink(
            backend, flush_count=3, flush_interval_seconds=10.0,
            max_retries=5, backoff_base_seconds=0.01,
        )
        for i in range(3):
            q.put(make_event(i))

        self.assertTrue(_wait_until(lambda: len(backend.batches) == 1, timeout=3.0))
        self.assertEqual(backend.calls, 3)
        self.assertEqual(len(backend.batches[0]), 3)

    def test_persistent_failure_drops_batch_but_thread_keeps_running(self):
        backend = FakeBackend(always_fail=True)
        q, sink = self._make_sink(
            backend, flush_count=2, flush_interval_seconds=10.0,
            max_retries=2, backoff_base_seconds=0.01,
        )
        q.put(make_event(1))
        q.put(make_event(2))

        # 1 initial attempt + 2 retries = 3 calls, then the batch is dropped.
        self.assertTrue(_wait_until(lambda: backend.calls >= 3, timeout=2.0))
        time.sleep(0.05)
        self.assertEqual(backend.batches, [])
        self.assertTrue(sink.is_alive())

        # Prove the thread survived the dropped batch: a fresh batch through a
        # backend that now succeeds must still go through.
        backend.always_fail = False
        q.put(make_event(3))
        q.put(make_event(4))
        self.assertTrue(_wait_until(lambda: len(backend.batches) == 1, timeout=2.0))

    def test_graceful_drain_flushes_remaining_buffer_on_stop(self):
        backend = FakeBackend()
        q, sink = self._make_sink(backend, flush_count=100, flush_interval_seconds=10.0)
        q.put(make_event(1))
        q.put(make_event(2))
        time.sleep(0.1)  # let the thread pick both events up into its buffer

        sink.stop(drain=True)

        self.assertEqual(len(backend.batches), 1)
        self.assertEqual(len(backend.batches[0]), 2)
        self.assertFalse(sink.is_alive())

    def test_emit_events_queued_after_stop_signal_are_still_drained(self):
        """A stop() must not drop events still sitting in the source queue."""
        backend = FakeBackend()
        q, sink = self._make_sink(backend, flush_count=100, flush_interval_seconds=10.0)
        q.put(make_event(1))

        sink.stop(drain=True)

        self.assertEqual(len(backend.batches), 1)
        self.assertEqual(len(backend.batches[0]), 1)


if __name__ == "__main__":
    unittest.main()
