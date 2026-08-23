"""Firestore-backed sink backend.

Writes each batch to ``logs/{batch_id}``, increments ``stats/{date}`` counters, and
upserts ``presence/{session_id}``. Reuses the single Firestore client from
``apps.backend.auth.firebase_client`` rather than creating a second one, and degrades to
a no-op when Firestore isn't configured -- the same graceful-fallback pattern
``apps.backend.models.history_store`` already uses for local development.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

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

# Upper bound on the distinct session ids one instance remembers per date, so the
# de-duplication below can never grow without limit in memory. Past this the day's
# `unique_sessions` counter simply stops advancing -- an undercount on an absurd day is a
# far better failure than the unbounded growth this replaced (see _new_session_count).
_MAX_TRACKED_SESSIONS = 50_000

# How many dates' session sets to keep at once. Two covers the only case that matters: a
# batch straddling the UTC midnight boundary, where today's and yesterday's are both live.
_MAX_TRACKED_DATES = 2


class FirestoreSink:
    """Sink backend that persists batched events to Firestore."""

    def __init__(self) -> None:
        # date -> session ids already counted towards that date's `unique_sessions`.
        self._counted_sessions: Dict[str, Set[str]] = {}

    def write_batch(
        self, events: List[Dict[str, Any]], *, now: Optional[datetime] = None,
    ) -> None:
        """Writes one batch document and updates its derived stats/presence records.

        A no-op, not an error, when there are no events or Firestore isn't configured --
        callers (the sink thread) treat any exception as retryable, so this only ever
        raises for a genuine write failure.

        ``now`` is passed straight through to ``build_batch_document`` -- the live sink
        thread never sets it (real current time), while a historical-data producer like
        ``scripts/seed_fake_logs.py`` can backdate a batch's ``created_at``/``expires_at``.
        """
        if not events:
            return
        db = get_db()
        if not db:
            return

        batch_doc = build_batch_document(events, now=now)
        db.collection(LOGS_COLLECTION).document(batch_doc["batch_id"]).set(batch_doc)

        presence_writes = self._update_presence(db, events)
        # +1 for the batch doc above; the stats write(s) themselves are counted inside
        # _update_stats, since only it knows how many distinct dates this batch touches.
        self._update_stats(db, events, writes_so_far=1 + presence_writes)

    def _update_stats(
        self, db: Any, events: List[Dict[str, Any]], writes_so_far: int,
    ) -> None:
        """Increments additive daily counters, grouped by each event's UTC date.

        Also advances each date's `unique_sessions` counter (source for query.py's
        `get_daily_stats().unique_sessions`) by however many session ids this batch is the
        first to see for that date, and folds a `firestore_writes` counter into **today's** date entry -- the running
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
            new_sessions = self._new_session_count(date, sessions_by_date.get(date))
            if new_sessions:
                fields["unique_sessions"] = firestore.Increment(new_sessions)
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

    def _new_session_count(self, date: str, session_ids: Optional[Set[str]]) -> int:
        """How many of `session_ids` this instance has not already counted for `date`.

        Replaces an earlier design that unioned every session id of the day into a
        `session_ids` array on the stats document: that array had no upper bound, and once
        it pushed the document past Firestore's 1 MB ceiling *every* stats write for that
        date failed, which made the sink drop every batch until the next UTC midnight.

        De-duplication is per process, not global, so a restart can double-count a session
        that spans it. That is acceptable here: Render runs a single gunicorn worker
        (`render.yaml`, `--workers 1`), the number is a rough activity gauge rather than
        billing data, and the alternative -- an unbounded, self-destructing array -- was
        strictly worse.
        """
        if not session_ids:
            return 0

        counted = self._counted_sessions.setdefault(date, set())
        if len(counted) >= _MAX_TRACKED_SESSIONS:
            return 0

        new = session_ids - counted
        if not new:
            return 0

        room = _MAX_TRACKED_SESSIONS - len(counted)
        if len(new) > room:
            logger.warning(
                "logstore sink: %s reached the %d tracked-session cap; unique_sessions "
                "will undercount for the rest of the day", date, _MAX_TRACKED_SESSIONS,
            )
            new = set(sorted(new)[:room])

        counted.update(new)
        self._forget_stale_dates()
        return len(new)

    def _forget_stale_dates(self) -> None:
        """Keeps only the most recent `_MAX_TRACKED_DATES` dates' session sets in memory."""
        while len(self._counted_sessions) > _MAX_TRACKED_DATES:
            del self._counted_sessions[min(self._counted_sessions)]

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
