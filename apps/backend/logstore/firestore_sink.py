"""Firestore-backed sink backend.

Writes each batch to ``logs/{batch_id}``, increments ``stats/{date}`` counters, and
upserts ``presence/{session_id}``. Reuses the single Firestore client from
``apps.backend.auth.firebase_client`` rather than creating a second one, and degrades to
a no-op when Firestore isn't configured -- the same graceful-fallback pattern
``apps.backend.models.history_store`` already uses for local development.
"""
import logging
from datetime import datetime, timezone
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

        presence_writes = self._update_presence(db, events)
        # +1 for the batch doc above; the stats write(s) themselves are counted inside
        # _update_stats, since only it knows how many distinct dates this batch touches.
        self._update_stats(db, events, writes_so_far=1 + presence_writes)

    def _update_stats(
        self, db: Any, events: List[Dict[str, Any]], writes_so_far: int,
    ) -> None:
        """Increments additive daily counters, grouped by each event's UTC date.

        Also unions each date's distinct session ids into a `session_ids` array field
        (source for query.py's `get_daily_stats().unique_sessions`, read as `len(field)`),
        and folds a `firestore_writes` counter into **today's** date entry -- the running
        total of every Firestore write this flush performed (batch doc + presence upserts +
        this method's own per-date writes), used by the ingest endpoint's circuit breaker to
        gauge how close today is to the free-tier write cap. Folded into the same `.set()`
        call as today's other counters rather than a separate write, so this never adds an
        extra Firestore write of its own in the common case (today's events are almost always
        present, since a batch flushes within 5 seconds of its first event). Internal-only
        field, not part of `get_daily_stats`'s frozen return shape.
        """
        by_date: Dict[str, Dict[str, int]] = {}
        sessions_by_date: Dict[str, set] = {}
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

            session_id = event.get("session_id")
            if session_id:
                sessions_by_date.setdefault(date, set()).add(session_id)

        today = datetime.now(timezone.utc).date().isoformat()
        total_writes = writes_so_far + len(by_date)

        for date, counters in by_date.items():
            fields: Dict[str, Any] = {
                key: firestore.Increment(value) for key, value in counters.items() if value
            }
            session_ids = sessions_by_date.get(date)
            if session_ids:
                fields["session_ids"] = firestore.ArrayUnion(sorted(session_ids))
            if date == today:
                fields["firestore_writes"] = firestore.Increment(total_writes)
            if fields:
                db.collection(STATS_COLLECTION).document(date).set(fields, merge=True)

        if today not in by_date:
            # Rare: a flush whose events all carry a date other than today's real wall-clock
            # date (e.g. backfilled/late data). Falls back to one extra write of its own,
            # which this +1 accounts for.
            db.collection(STATS_COLLECTION).document(today).set(
                {"firestore_writes": firestore.Increment(total_writes + 1)}, merge=True,
            )

    def _update_presence(self, db: Any, events: List[Dict[str, Any]]) -> int:
        """Upserts one presence document per session, keeping only its latest event.

        Returns the number of Firestore writes performed.
        """
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
        return len(latest_by_session)
