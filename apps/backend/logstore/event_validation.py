"""Temporary local stand-in for Workstream A's ``observability.events`` module.

Workstream A (``apps/backend/observability/``, the recorder) has not been merged into this
branch yet, so ``telemetry_routes.py`` cannot import her ``build_event``/``validate_event``.
This module mirrors the frozen event schema (``docs/workstreams/WORKSTREAM_A.md`` section 4)
closely enough that once her branch merges, swapping the import in ``telemetry_routes.py`` for
the real thing should be close to a one-line change -- the signature here is deliberately
shaped the same way.
"""
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

LEVELS = ("debug", "info", "warn", "error", "fatal")
SOURCES = ("frontend",)  # this endpoint only ever receives browser-originated events
CATEGORIES = ("http", "auth", "scan", "agent", "worker", "llm", "ui", "error", "health")

MAX_DATA_BYTES = 8192
MAX_STRING_CHARS = 2000
MAX_EVENTS_PER_BATCH = 100
MAX_REQUEST_BYTES = 65536


def build_frontend_event(raw: Dict[str, Any], *, uid: Optional[str]) -> Optional[Dict[str, Any]]:
    """Builds a schema-conformant event from one client-submitted event dict.

    Returns ``None`` if the event fails validation (bad/missing level, bad/missing category,
    or an empty message) -- callers should drop it from the batch rather than fail the whole
    request. Only the known field names are ever read from ``raw``; anything else the client
    sent is silently ignored. Every identity-bearing field (``source``, ``uid``, ``event_id``,
    ``ts``, ``release``, ``env``) is always server-set, never taken from the client, even if
    the client supplied one -- this is the server-side half of "never trust a client's claim
    about who it is".
    """
    if not isinstance(raw, dict):
        return None

    level = raw.get("level")
    if level not in LEVELS:
        return None

    category = raw.get("category")
    if category not in CATEGORIES:
        return None

    message = raw.get("message")
    if not isinstance(message, str) or not message.strip():
        return None
    message = message[:MAX_STRING_CHARS]

    duration_ms = raw.get("duration_ms", 0)
    if not isinstance(duration_ms, int) or isinstance(duration_ms, bool):
        duration_ms = 0

    data = raw.get("data")
    if not isinstance(data, dict):
        data = {}
    data = _cap_data_size(data)

    return {
        "event_id": str(uuid4()),
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "source": "frontend",
        "category": category,
        "message": message,
        "trace_id": _clean_optional_str(raw.get("trace_id")),
        "session_id": _clean_optional_str(raw.get("session_id")),
        "uid": uid,
        "scan_id": _clean_optional_str(raw.get("scan_id")),
        "duration_ms": duration_ms,
        "data": data,
        "release": os.environ.get("SENTINELSCAN_RELEASE", "dev"),
        "env": os.environ.get("SENTINELSCAN_ENV", "dev"),
    }


def _clean_optional_str(value: Any) -> Optional[str]:
    """Returns `value` if it's a non-empty string, else None -- never trusts other types."""
    if isinstance(value, str) and value:
        return value
    return None


def _cap_data_size(data: Dict[str, Any]) -> Dict[str, Any]:
    """Drops `data` entirely (replacing it with {}) if it exceeds MAX_DATA_BYTES serialized.

    No redaction module exists yet on this branch (that's Workstream A's `redaction.py`), so
    this is a size guard only, not a privacy guard -- dropping an oversized payload rather than
    attempting a partial truncation of arbitrary nested structure.
    """
    try:
        serialized = json.dumps(data, default=str)
    except (TypeError, ValueError):
        return {}
    if len(serialized.encode("utf-8")) > MAX_DATA_BYTES:
        return {}
    return data
