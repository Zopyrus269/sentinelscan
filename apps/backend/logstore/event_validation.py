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
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

LEVELS = ("debug", "info", "warn", "error", "fatal")
SOURCES = ("frontend",)  # this endpoint only ever receives browser-originated events
CATEGORIES = ("http", "auth", "scan", "agent", "worker", "llm", "ui", "error", "health")

# The three correlation ids (session_id/trace_id/scan_id) are used verbatim as Firestore
# document names downstream (`firestore_sink.py` writes `presence/{session_id}`), so they
# have to satisfy Firestore's document-id rules before they get anywhere near a write: no
# "/", at most 1500 bytes, no reserved `__like_this__` shape. This pattern is deliberately
# far stricter than those rules -- it matches what the only two producers actually emit
# (`crypto.randomUUID()` and its `${Date.now()}-${hex}` fallback in telemetry.js, and
# `uuid.uuid4()` in scripts/seed_fake_logs.py) and rejects everything else. Getting this
# wrong is not a dropped event: an unwritable presence document fails the whole batch, and
# the sink drops all ~100 events in it, other sessions' included.
_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
# Underscores are otherwise fine, but Firestore reserves the `__like_this__` shape for its
# own internal document ids and refuses to create one.
_RESERVED_ID_PATTERN = re.compile(r"^__.*__$")

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
        "trace_id": _clean_id(raw.get("trace_id")),
        "session_id": _clean_id(raw.get("session_id")),
        "uid": uid,
        "scan_id": _clean_id(raw.get("scan_id")),
        "duration_ms": duration_ms,
        "data": data,
        "release": os.environ.get("SENTINELSCAN_RELEASE", "dev"),
        "env": os.environ.get("SENTINELSCAN_ENV", "dev"),
    }


def _clean_id(value: Any) -> Optional[str]:
    """Returns `value` if it is a usable correlation id, else None.

    Nulling a malformed id out (rather than rejecting the whole event) keeps a client with a
    broken id generator from losing its telemetry entirely -- the event is still recorded,
    just uncorrelated.
    """
    if not isinstance(value, str):
        return None
    if not _ID_PATTERN.match(value) or _RESERVED_ID_PATTERN.match(value):
        return None
    return value


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
