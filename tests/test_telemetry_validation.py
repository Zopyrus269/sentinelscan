"""Tests for apps.backend.logstore.event_validation -- the temporary local schema stand-in
for Workstream A's observability.events.build_event/validate_event.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import unittest
from unittest.mock import patch

from apps.backend.logstore.event_validation import (
    MAX_DATA_BYTES,
    MAX_STRING_CHARS,
    build_frontend_event,
)

REQUIRED_KEYS = {
    "event_id", "ts", "level", "source", "category", "message", "trace_id",
    "session_id", "uid", "scan_id", "duration_ms", "data", "release", "env",
}


class TestBuildFrontendEvent(unittest.TestCase):

    def _valid_raw(self, **overrides):
        raw = {"level": "info", "category": "ui", "message": "clicked start scan"}
        raw.update(overrides)
        return raw

    def test_valid_event_has_every_key_always_present(self):
        event = build_frontend_event(self._valid_raw(), uid=None)
        self.assertIsNotNone(event)
        self.assertEqual(set(event.keys()), REQUIRED_KEYS)

    def test_bad_level_is_rejected(self):
        self.assertIsNone(build_frontend_event(self._valid_raw(level="verbose"), uid=None))

    def test_missing_level_is_rejected(self):
        raw = self._valid_raw()
        del raw["level"]
        self.assertIsNone(build_frontend_event(raw, uid=None))

    def test_bad_category_is_rejected(self):
        self.assertIsNone(build_frontend_event(self._valid_raw(category="nonsense"), uid=None))

    def test_missing_message_is_rejected(self):
        raw = self._valid_raw()
        del raw["message"]
        self.assertIsNone(build_frontend_event(raw, uid=None))

    def test_empty_message_is_rejected(self):
        self.assertIsNone(build_frontend_event(self._valid_raw(message="   "), uid=None))

    def test_non_dict_raw_is_rejected(self):
        self.assertIsNone(build_frontend_event("not a dict", uid=None))

    def test_unknown_extra_keys_are_dropped(self):
        raw = self._valid_raw()
        raw["evil_field"] = "should not survive"
        event = build_frontend_event(raw, uid=None)
        self.assertNotIn("evil_field", event)

    def test_message_is_truncated(self):
        raw = self._valid_raw(message="x" * (MAX_STRING_CHARS + 500))
        event = build_frontend_event(raw, uid=None)
        self.assertEqual(len(event["message"]), MAX_STRING_CHARS)

    def test_oversized_data_is_dropped_not_partially_redacted(self):
        raw = self._valid_raw(data={"blob": "x" * (MAX_DATA_BYTES + 1000)})
        event = build_frontend_event(raw, uid=None)
        self.assertEqual(event["data"], {})

    def test_reasonable_data_is_kept(self):
        raw = self._valid_raw(data={"button_id": "startScanButton"})
        event = build_frontend_event(raw, uid=None)
        self.assertEqual(event["data"], {"button_id": "startScanButton"})

    def test_non_dict_data_is_replaced_with_empty_dict(self):
        raw = self._valid_raw(data="not a dict")
        event = build_frontend_event(raw, uid=None)
        self.assertEqual(event["data"], {})

    def test_source_is_always_frontend_even_if_client_sends_something_else(self):
        raw = self._valid_raw(source="backend")
        event = build_frontend_event(raw, uid=None)
        self.assertEqual(event["source"], "frontend")

    def test_client_supplied_uid_is_ignored_server_uid_wins(self):
        raw = self._valid_raw(uid="attacker-controlled-uid")
        event = build_frontend_event(raw, uid="real-server-verified-uid")
        self.assertEqual(event["uid"], "real-server-verified-uid")

    def test_uid_is_none_when_server_could_not_derive_one(self):
        raw = self._valid_raw(uid="attacker-controlled-uid")
        event = build_frontend_event(raw, uid=None)
        self.assertIsNone(event["uid"])

    def test_client_supplied_event_id_and_ts_are_ignored(self):
        raw = self._valid_raw(event_id="client-chosen-id", ts="2000-01-01T00:00:00+00:00")
        event = build_frontend_event(raw, uid=None)
        self.assertNotEqual(event["event_id"], "client-chosen-id")
        self.assertNotEqual(event["ts"], "2000-01-01T00:00:00+00:00")

    def test_release_and_env_read_from_environment(self):
        with patch.dict(os.environ, {"SENTINELSCAN_RELEASE": "abc123", "SENTINELSCAN_ENV": "prod"}):
            event = build_frontend_event(self._valid_raw(), uid=None)
        self.assertEqual(event["release"], "abc123")
        self.assertEqual(event["env"], "prod")

    def test_optional_ids_default_to_none_when_absent_or_wrong_type(self):
        event = build_frontend_event(self._valid_raw(trace_id=123), uid=None)
        self.assertIsNone(event["trace_id"])

    def test_data_is_json_serializable(self):
        raw = self._valid_raw(data={"a": 1, "b": [1, 2, 3]})
        event = build_frontend_event(raw, uid=None)
        json.dumps(event)  # must not raise


if __name__ == "__main__":
    unittest.main()
