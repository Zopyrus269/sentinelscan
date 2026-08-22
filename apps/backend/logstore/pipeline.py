"""Wires the sink thread (Phase 1) up to a real queue for a producer to feed.

Phase 1 built ``sink.py`` (drains any ``queue.Queue``) and the two backends, but nothing yet
owned the queue itself or decided when to start the thread -- that was deferred until there was
a producer. ``telemetry_routes.py`` (Phase 2) is that first producer. Workstream A's
``observability.emit`` will eventually own a queue of its own for backend-originated events;
reconciling the two into a single shared queue is integration work, once her branch exists.
"""
import os
from typing import Optional
from queue import Queue
from typing import Any, Dict

from apps.backend.auth.firebase_client import get_db
from apps.backend.logstore import sink
from apps.backend.logstore.firestore_sink import FirestoreSink
from apps.backend.logstore.stdout_sink import StdoutSink

DEFAULT_QUEUE_SIZE = 10_000

_queue: Optional["Queue[Dict[str, Any]]"] = None
_started = False


def is_enabled() -> bool:
    """True when SENTINELSCAN_TELEMETRY_ENABLED is one of 1/true/yes/on.

    Read per call (not cached at import time) so tests can monkeypatch the environment.
    Matches the frozen contract this env var name has across all three workstreams.
    """
    return os.environ.get("SENTINELSCAN_TELEMETRY_ENABLED", "0").strip().lower() in (
        "1", "true", "yes", "on",
    )


def get_queue() -> "Queue[Dict[str, Any]]":
    """The bounded queue the sink thread drains. Created lazily, sized once."""
    global _queue
    if _queue is None:
        size = os.environ.get("SENTINELSCAN_TELEMETRY_QUEUE_SIZE", str(DEFAULT_QUEUE_SIZE))
        try:
            maxsize = int(size)
        except ValueError:
            maxsize = DEFAULT_QUEUE_SIZE
        _queue = Queue(maxsize=maxsize)
    return _queue


def ensure_started() -> None:
    """Starts the sink thread against `get_queue()`, if it isn't already running.

    Picks FirestoreSink when Firestore is configured, else StdoutSink for local dev -- same
    graceful-degrade check `apps.backend.models.history_store` already uses. Idempotent: a
    second call is a no-op, so app.py can call this unconditionally at startup. Must be called
    from the main thread (app-creation time), since `sink.start()` registers a SIGTERM handler
    that only takes effect there.
    """
    global _started
    if _started:
        return
    backend = FirestoreSink() if get_db() else StdoutSink()
    sink.start(get_queue(), backend)
    _started = True
