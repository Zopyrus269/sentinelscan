"""Tests for apps.backend.logstore.stdout_sink -- the local-dev sink backend."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import io
import json
import unittest
from contextlib import redirect_stdout

from apps.backend.logstore.stdout_sink import StdoutSink


class TestStdoutSink(unittest.TestCase):

    def test_writes_one_json_line_per_event(self):
        events = [{"event_id": "e1", "message": "a"}, {"event_id": "e2", "message": "b"}]
        buf = io.StringIO()

        with redirect_stdout(buf):
            StdoutSink().write_batch(events)

        lines = [line for line in buf.getvalue().splitlines() if line]
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["event_id"], "e1")
        self.assertEqual(json.loads(lines[1])["event_id"], "e2")

    def test_empty_batch_prints_nothing(self):
        buf = io.StringIO()

        with redirect_stdout(buf):
            StdoutSink().write_batch([])

        self.assertEqual(buf.getvalue(), "")

    def test_non_json_native_values_are_stringified_not_raised(self):
        """`data` payloads may contain e.g. datetimes; must never crash the sink."""
        import datetime
        events = [{"event_id": "e1", "ts": datetime.datetime(2026, 8, 22)}]
        buf = io.StringIO()

        with redirect_stdout(buf):
            StdoutSink().write_batch(events)

        parsed = json.loads(buf.getvalue().strip())
        self.assertIn("2026-08-22", parsed["ts"])


if __name__ == "__main__":
    unittest.main()
