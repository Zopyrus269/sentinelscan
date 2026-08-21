"""Firestore-backed sink backend.

Writes each batch to ``logs/{batch_id}``, increments ``stats/{date}`` counters, and
upserts ``presence/{session_id}``. Reuses the single Firestore client from
``apps.backend.auth.firebase_client`` rather than creating a second one, and degrades to
a no-op when Firestore isn't configured -- the same graceful-fallback pattern
``apps.backend.models.history_store`` already uses for local development.
"""
import logging
from typing import Any, Dict, List

try:
    from firebase_admin import firestore
except ImportError:
    firestore = None

from apps.backend.auth.firebase_client import get_db
from apps.backend.logstore.schema import (
    LOGS_COLLECTION,
    PRESENCE_COLLECTION,
    STATS_COLLECTION,
    build_batch_document,
)

logger = logging.getLogger(__name__)


class FirestoreSink:
    """Sink backend that persists batched events to Firestore."""

    def write_batch(self, events: List[Dict[str, Any]]) -> None:
        """Writes one batch document and updates its derived stats/presence records.

        A no-op, not an error, when there are no events or Firestore isn't configured --
        callers (the sink thread) treat any exception as retryable, so this only ever
        raises for a genuine write failure.
        """
        if not events:
            return
        db = get_db()
        if not db:
            return

        batch_doc = build_batch_document(events)
        db.collection(LOGS_COLLECTION).document(batch_doc["batch_id"]).set(batch_doc)

        self._update_stats(db, events)
        self._update_presence(db, events)

    def _update_stats(self, db: Any, events: List[Dict[str, Any]]) -> None:
        """Increments additive daily counters, grouped by each event's UTC date."""
        by_date: Dict[str, Dict[str, int]] = {}
        for event in events:
            date = event["ts"][:10]
            counters = by_date.setdefault(date, {
                "events": 0, "errors": 0, "requests": 0, "scans": 0,
                "llm_calls": 0, "llm_tokens": 0,
            })
            counters["events"] += 1
            if event["level"] in ("error", "fatal"):
                counters["errors"] += 1
            if event["category"] == "http":
                counters["requests"] += 1
            elif event["category"] == "scan":
                counters["scans"] += 1
            elif event["category"] == "llm":
                counters["llm_calls"] += 1
                counters["llm_tokens"] += (event.get("data") or {}).get("total_tokens", 0) or 0

        for date, counters in by_date.items():
            increments = {key: firestore.Increment(value) for key, value in counters.items() if value}
            if increments:
                db.collection(STATS_COLLECTION).document(date).set(increments, merge=True)

    def _update_presence(self, db: Any, events: List[Dict[str, Any]]) -> None:
        """Upserts one presence document per session, keeping only its latest event."""
        latest_by_session: Dict[str, Dict[str, Any]] = {}
        for event in events:
            session_id = event.get("session_id")
            if not session_id:
                continue
            current = latest_by_session.get(session_id)
            if current is None or event["ts"] > current["ts"]:
                latest_by_session[session_id] = event

        for session_id, event in latest_by_session.items():
            db.collection(PRESENCE_COLLECTION).document(session_id).set({
                "session_id": session_id,
                "uid": event.get("uid"),
                "last_seen": event["ts"],
            }, merge=True)
