"""The read API Workstream C's log site codes against blind.

Ten function signatures are frozen (``docs/workstreams/WORKSTREAM_C.md`` section 5) --
Danny is building his five screens against these without seeing this code, so names,
parameters and return shapes here must match that document exactly. One additional,
non-frozen helper (``get_write_budget_status``) lives here too, for the ingest endpoint's
daily-write circuit breaker; it is internal to Workstream B only.

Events live nested inside ``logs/{batch_id}`` documents (~100 events per document -- this is
what keeps Firestore's free tier viable), not as one document per event. So most functions
here query ``logs`` by a coarse ``created_at`` range (optionally narrowed by an
``array_contains`` filter on the batch's denormalized ``session_ids``/``trace_ids``/
``scan_ids`` field), then filter and flatten the matched batches' nested ``events`` arrays in
Python against the caller's exact filters. ``created_at`` is when a batch was flushed, which
can lag an event's own ``ts`` by up to the sink's flush interval -- range queries widen by
``_CREATED_AT_SKEW`` to compensate, then filter precisely on ``ts`` in Python.
"""
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    from firebase_admin import firestore
except ImportError:
    firestore = None

from apps.backend.auth.firebase_client import get_db
from apps.backend.logstore.schema import (
    LOGS_COLLECTION,
    PRESENCE_COLLECTION,
    RAW_RETENTION_DAYS,
    ROLLUP_CHECKPOINT_DOC,
    ROLLUP_COLLECTION,
    ROLLUP_META_COLLECTION,
    STATS_COLLECTION,
    UPTIME_COLLECTION,
    rollup_doc_id,
)

logger = logging.getLogger(__name__)

DEFAULT_QUERY_LIMIT = 200
MAX_QUERY_LIMIT = 500

# Ceiling on how many batch documents a single read may pull back. Without one, a call with
# no time filter reads every batch ever written and discards most of them in Python -- on an
# auto-refreshing screen that exhausts Firestore's 50k reads/day free tier, which
# docs/workstreams/WORKSTREAM_C.md section 10 already names as the trap to avoid. At
# BATCH_SIZE events per document this still covers far more events than any one page needs.
_MAX_BATCH_SCAN = 50

# Applied by query_events when the caller gives neither a time bound nor a cursor -- i.e. a
# screen's very first load. Bounds the cold-start read without needing the caller to know to
# ask for it.
_DEFAULT_QUERY_WINDOW = timedelta(hours=24)

# Ceiling on the presence documents count_active_users will read. One document per session,
# so this is "how many concurrent sessions we are willing to count", not a data limit.
_MAX_ACTIVE_SESSIONS = 500

# How much a batch's `created_at` (when it was flushed) can lag its events' own `ts`
# (when they happened). Generous relative to the sink's 5s/100-event flush threshold, to
# absorb clock skew and retry backoff without ever missing an event at a range boundary.
_CREATED_AT_SKEW = timedelta(minutes=2)

# Daily Firestore write budget the circuit breaker gauges against. Conservative relative to
# the real 20,000/day free-tier cap, leaving headroom for the rest of the app (history,
# auth) to also write against the same project.
_DAILY_WRITE_BUDGET = 15_000
_WRITE_BUDGET_WARN_RATIO = 0.9

# get_write_budget_status is called from the ingest endpoint's request path (the circuit
# breaker check), potentially on every request -- caching briefly avoids turning a
# write-quota guard into its own significant read-quota cost. A near-cap decision up to
# this many seconds stale is an acceptable trade for a soft, best-effort breaker.
_WRITE_BUDGET_CACHE_SECONDS = 30.0
_write_budget_cache: Optional[Dict[str, Any]] = None
_write_budget_cache_at: float = 0.0


def _read_documents(db: Any, collection: str, doc_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Reads several documents of one collection, keyed by id, skipping ones that do not exist.

    Uses the client's `get_all` so this costs one round trip rather than one per document.
    The billed read count is the same either way -- what this removes is the latency of
    fetching, say, 90 uptime days or 550 rollup hours strictly one after another. Falls back
    to individual `get()` calls for any client that does not expose `get_all`.
    """
    refs = [db.collection(collection).document(doc_id) for doc_id in doc_ids]
    get_all = getattr(db, "get_all", None)
    if callable(get_all):
        return {snap.id: (snap.to_dict() or {}) for snap in get_all(refs) if snap.exists}

    documents = {}
    for doc_id, ref in zip(doc_ids, refs):
        snap = ref.get()
        if snap.exists:
            documents[doc_id] = snap.to_dict() or {}
    return documents


def _empty_events_result() -> Dict[str, Any]:
    return {"events": [], "next_cursor": None}


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _normalize_bound(value: Optional[str]) -> Optional[str]:
    """Canonicalises one caller-supplied timestamp for string comparison against `ts`.

    Returns None for an absent or unparseable value, which disables that bound rather than
    silently comparing garbage lexicographically.
    """
    parsed = _parse_ts(value)
    return _iso(parsed) if parsed else None


def _fetch_batches(
    db: Any,
    *,
    since: Optional[str] = None,
    until: Optional[str] = None,
    id_field: Optional[str] = None,
    id_value: Optional[str] = None,
    limit: int = _MAX_BATCH_SCAN,
    newest_first: bool = False,
) -> List[Dict[str, Any]]:
    """Reads `logs` batch documents, filtered by a widened `created_at` range and,
    optionally, one `array_contains` id filter. Returns raw batch dicts (still containing
    every event, unfiltered) for the caller to flatten/filter further in Python.

    Always bounded by `limit` on the Firestore side, never by filtering a full collection
    scan in Python. `newest_first` picks which end of the range that limit keeps: a screen's
    first load wants the newest batches, while a cursor-driven poll walks forward from where
    it left off. Either way the returned list is in ascending `created_at` order, since
    everything downstream assumes that.
    """
    query = db.collection(LOGS_COLLECTION)
    if id_field and id_value:
        query = query.where(id_field, "array_contains", id_value)

    since_dt = _parse_ts(since)
    until_dt = _parse_ts(until)
    if since_dt:
        query = query.where("created_at", ">=", _iso(since_dt - _CREATED_AT_SKEW))
    if until_dt:
        query = query.where("created_at", "<=", _iso(until_dt + _CREATED_AT_SKEW))

    if newest_first and firestore:
        query = query.order_by("created_at", direction=firestore.Query.DESCENDING)
    else:
        query = query.order_by("created_at")

    batches = [doc.to_dict() for doc in query.limit(limit).stream()]
    if newest_first:
        batches.reverse()
    return batches


def _flatten_events(
    batches: List[Dict[str, Any]],
    *,
    since: Optional[str] = None,
    until: Optional[str] = None,
    level: Optional[str] = None,
    source: Optional[str] = None,
    category: Optional[str] = None,
    session_id: Optional[str] = None,
    uid: Optional[str] = None,
    trace_id: Optional[str] = None,
    scan_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Flattens every batch's `events` array into one list, keeping only events that pass
    every given filter. `since`/`until` are precise here (unlike `_fetch_batches`'s coarse
    `created_at` range) since they compare directly against each event's own `ts`.

    Both are normalised to canonical UTC first, exactly as `_fetch_batches` already does.
    Without that step the comparison is a raw string compare, so `...T10:00:00Z` and
    `...T10:00:00+00:00` -- the same instant, spelled two equally-valid ways -- return
    different results, and any non-UTC offset returns nonsense. The log site is the caller
    and codes against this blind, so it has no way to notice.
    """
    since = _normalize_bound(since)
    until = _normalize_bound(until)

    events: List[Dict[str, Any]] = []
    for batch in batches:
        for event in batch.get("events", []):
            if since and event["ts"] < since:
                continue
            if until and event["ts"] > until:
                continue
            if level and event.get("level") != level:
                continue
            if source and event.get("source") != source:
                continue
            if category and event.get("category") != category:
                continue
            if session_id and event.get("session_id") != session_id:
                continue
            if uid and event.get("uid") != uid:
                continue
            if trace_id and event.get("trace_id") != trace_id:
                continue
            if scan_id and event.get("scan_id") != scan_id:
                continue
            events.append(event)
    events.sort(key=lambda e: (e["ts"], e["event_id"]))
    return events


def _paginate(
    events: List[Dict[str, Any]], cursor: Optional[str], limit: int,
) -> Dict[str, Any]:
    """Applies a `(ts, event_id)` cursor and limit to an already-sorted event list.

    The cursor is `"{ts}|{event_id}"` of the last event previously returned. ISO-8601 UTC
    timestamps sort lexicographically, so simple string comparison gives correct ordering;
    `event_id` breaks ties between same-timestamp events.

    With a cursor this walks forward from it. Without one it takes the *newest* `limit`
    events rather than the oldest, so a first load opens on current activity; the page is
    still in ascending order, so the cursor taken from its last event keeps polling forward.
    """
    if cursor:
        try:
            cursor_ts, cursor_id = cursor.split("|", 1)
        except ValueError:
            cursor_ts, cursor_id = cursor, ""
        events = [e for e in events if (e["ts"], e["event_id"]) > (cursor_ts, cursor_id)]
        page = events[:limit]
    else:
        page = events[-limit:]

    if page:
        last = page[-1]
        next_cursor = f"{last['ts']}|{last['event_id']}"
    else:
        # Nothing new this poll: hand the caller's own place back so it can poll again.
        next_cursor = cursor
    return {"events": page, "next_cursor": next_cursor}


def query_events(
    *,
    since: Optional[str] = None,
    until: Optional[str] = None,
    level: Optional[str] = None,
    source: Optional[str] = None,
    category: Optional[str] = None,
    session_id: Optional[str] = None,
    uid: Optional[str] = None,
    trace_id: Optional[str] = None,
    scan_id: Optional[str] = None,
    cursor: Optional[str] = None,
    limit: int = DEFAULT_QUERY_LIMIT,
) -> Dict[str, Any]:
    """Returns `{"events": [...], "next_cursor": str | None}` matching every given filter.

    Events within a page are ordered oldest-first by `ts`. Which events make up the page
    depends on whether a `cursor` was given:

    - **no cursor** (a screen's first load) -- the *newest* `limit` matching events. A live
      log view opening on the oldest events in the database is never what anyone wants.
    - **with a cursor** -- only what has arrived since that cursor, walking forward. This is
      the polling path described in `docs/workstreams/WORKSTREAM_C.md` section 10, and the
      ascending order within the page is what makes it work.

    `next_cursor` is returned whenever the page is non-empty, and echoes the caller's own
    cursor back when nothing new has arrived -- so a caller can always poll forward, even
    from a page shorter than `limit`. Without that a quiet minute would leave a screen with
    no cursor to poll from.
    """
    db = get_db()
    if not db:
        return _empty_events_result()

    limit = max(1, min(limit, MAX_QUERY_LIMIT))
    id_field, id_value = None, None
    if session_id:
        id_field, id_value = "session_ids", session_id
    elif trace_id:
        id_field, id_value = "trace_ids", trace_id
    elif scan_id:
        id_field, id_value = "scan_ids", scan_id

    since = _window_start(since, cursor)
    batches = _fetch_batches(
        db, since=since, until=until, id_field=id_field, id_value=id_value,
        newest_first=cursor is None,
    )
    events = _flatten_events(
        batches, since=since, until=until, level=level, source=source, category=category,
        session_id=session_id, uid=uid, trace_id=trace_id, scan_id=scan_id,
    )
    return _paginate(events, cursor, limit)


def _window_start(since: Optional[str], cursor: Optional[str]) -> Optional[str]:
    """The `since` bound query_events should actually read with.

    An explicit `since` always wins. Failing that, a cursor implies one: a poll only wants
    what arrived after it, so reading from the cursor's own timestamp (widened by the
    flush-lag skew) turns each poll into the "zero to three documents" read
    `WORKSTREAM_C.md` section 10 assumes, instead of re-reading the whole window every time.
    With neither, fall back to a default window so a first load is bounded.
    """
    if since:
        return since

    if cursor:
        cursor_ts = _parse_ts(cursor.split("|", 1)[0])
        if cursor_ts:
            return _iso(cursor_ts - _CREATED_AT_SKEW)

    return _iso(datetime.now(timezone.utc) - _DEFAULT_QUERY_WINDOW)


def get_trace(trace_id: str) -> Dict[str, Any]:
    """Returns `{"trace_id", "events": [...]}` -- everything sharing one user action."""
    db = get_db()
    if not db:
        return {"trace_id": trace_id, "events": []}

    batches = _fetch_batches(db, id_field="trace_ids", id_value=trace_id)
    events = _flatten_events(batches, trace_id=trace_id)
    return {"trace_id": trace_id, "events": events}


def get_session_timeline(session_id: str) -> Dict[str, Any]:
    """Returns `{"session_id", "uid", "started_at", "last_seen", "events": [...]}`."""
    db = get_db()
    if not db:
        return {
            "session_id": session_id, "uid": None,
            "started_at": None, "last_seen": None, "events": [],
        }

    batches = _fetch_batches(db, id_field="session_ids", id_value=session_id)
    events = _flatten_events(batches, session_id=session_id)

    uid = next((e.get("uid") for e in events if e.get("uid")), None)
    return {
        "session_id": session_id,
        "uid": uid,
        "started_at": events[0]["ts"] if events else None,
        "last_seen": events[-1]["ts"] if events else None,
        "events": events,
    }


def list_sessions(*, since: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Returns recent sessions from `presence/` -- one doc per session, already keyed by
    its latest-seen event, which is exactly the summary this needs (no raw-event scan).

    `email` is left `None`: presence documents don't carry it (only `uid`), and resolving
    uid -> email would mean an extra Firebase Admin lookup per session on every call, which
    doesn't fit this function's "cheap list" role. The log site can resolve it itself if
    needed.
    """
    db = get_db()
    if not db:
        return []

    query = db.collection(PRESENCE_COLLECTION)
    since_dt = _parse_ts(since)
    if since_dt:
        query = query.where("last_seen", ">=", _iso(since_dt))
    query = query.order_by("last_seen", direction=firestore.Query.DESCENDING).limit(limit)

    sessions = []
    for doc in query.stream():
        data = doc.to_dict()
        sessions.append({
            "session_id": data.get("session_id"),
            "uid": data.get("uid"),
            "email": None,
            "started_at": data.get("last_seen"),
            "last_seen": data.get("last_seen"),
            "event_count": None,
            "error_count": None,
            "routes": [],
        })
    return sessions


def count_active_users(window_minutes: int = 5) -> Dict[str, Any]:
    """Returns `{"count": int, "sessions": [{"session_id", "uid", "last_seen"}, ...]}` for
    sessions seen within the last `window_minutes`, read from `presence/`.

    Bounded at `_MAX_ACTIVE_SESSIONS` most-recent sessions, so an unbounded collection scan
    cannot run on a screen that auto-refreshes. `count` therefore saturates rather than
    growing without limit -- a warning is logged if that ever happens, since at that point
    the number shown is a floor, not the truth. The cap sits far above any plausible
    concurrent load for this app; if it is ever reached in earnest, this wants a Firestore
    `count()` aggregation for the number and the limit kept only for the listed sessions.
    """
    db = get_db()
    if not db:
        return {"count": 0, "sessions": []}

    cutoff = _iso(datetime.now(timezone.utc) - timedelta(minutes=window_minutes))
    query = (
        db.collection(PRESENCE_COLLECTION)
        .where("last_seen", ">=", cutoff)
        .order_by("last_seen", direction=firestore.Query.DESCENDING)
        .limit(_MAX_ACTIVE_SESSIONS)
    )

    sessions = [
        {
            "session_id": data.get("session_id"),
            "uid": data.get("uid"),
            "last_seen": data.get("last_seen"),
        }
        for data in (doc.to_dict() for doc in query.stream())
    ]
    if len(sessions) >= _MAX_ACTIVE_SESSIONS:
        logger.warning(
            "count_active_users hit the %d-session cap; the reported count is a floor",
            _MAX_ACTIVE_SESSIONS,
        )
    return {"count": len(sessions), "sessions": sessions}


def get_daily_stats(date: str) -> Dict[str, Any]:
    """Returns one day's aggregate counters from `stats/{date}` -- a single document read.

    `unique_sessions` comes from that document's counter of the same name, advanced at
    write time by `firestore_sink.py`, not a separate scan. Documents written before that
    counter existed instead carry a `session_ids` array; those are still read correctly via
    the fallback below, so historical days keep reporting a real number.
    """
    empty = {
        "date": date, "events": 0, "errors": 0, "requests": 0, "scans": 0,
        "llm_calls": 0, "llm_tokens": 0, "unique_sessions": 0,
    }
    db = get_db()
    if not db:
        return empty

    doc = db.collection(STATS_COLLECTION).document(date).get()
    if not doc.exists:
        return empty
    data = doc.to_dict() or {}
    return {
        "date": date,
        "events": data.get("events", 0),
        "errors": data.get("errors", 0),
        "requests": data.get("requests", 0),
        "scans": data.get("scans", 0),
        "llm_calls": data.get("llm_calls", 0),
        "llm_tokens": data.get("llm_tokens", 0),
        "unique_sessions": data.get(
            "unique_sessions", len(data.get("session_ids", [])),
        ),
    }


def get_write_budget_status(date: Optional[str] = None) -> Dict[str, Any]:
    """Internal helper (not part of the frozen 10) for the ingest endpoint's daily-write
    circuit breaker. Reads the same `stats/{date}` document `get_daily_stats` does, plus its
    `firestore_writes` field, and reports how close today is to `_DAILY_WRITE_BUDGET`.

    The no-`date`, "today" call (the hot path -- the ingest endpoint calls this on every
    request) is cached in-process for `_WRITE_BUDGET_CACHE_SECONDS`, so this circuit breaker
    doesn't itself become a meaningful source of Firestore reads. An explicit `date` always
    reads fresh, since that's only ever a one-off historical lookup.
    """
    global _write_budget_cache, _write_budget_cache_at

    use_cache = date is None
    if use_cache and _write_budget_cache is not None:
        if time.monotonic() - _write_budget_cache_at < _WRITE_BUDGET_CACHE_SECONDS:
            return _write_budget_cache

    resolved_date = date or datetime.now(timezone.utc).date().isoformat()
    db = get_db()
    if not db:
        result = {
            "date": resolved_date, "writes_today": 0,
            "budget": _DAILY_WRITE_BUDGET, "near_cap": False,
        }
    else:
        doc = db.collection(STATS_COLLECTION).document(resolved_date).get()
        writes_today = (doc.to_dict() or {}).get("firestore_writes", 0) if doc.exists else 0
        result = {
            "date": resolved_date,
            "writes_today": writes_today,
            "budget": _DAILY_WRITE_BUDGET,
            "near_cap": writes_today >= _DAILY_WRITE_BUDGET * _WRITE_BUDGET_WARN_RATIO,
        }

    if use_cache:
        _write_budget_cache = result
        _write_budget_cache_at = time.monotonic()
    return result


def get_llm_usage(
    *,
    since: Optional[str] = None,
    until: Optional[str] = None,
    group_by: str = "day",
) -> Dict[str, Any]:
    """Returns Gemini usage totals and per-bucket breakdown over `[since, until]`.

    The range is split at the point where rollup data can actually be trusted, so every
    part of it is counted exactly once:

    - hours fully covered by `logs_hourly` rollups are read from those (far cheaper than
      re-scanning every raw batch in the window);
    - everything else -- the newer end, plus any partial hour at the older end that a
      whole-hour rollup bucket would over-count -- is read from raw `logs` batches, which
      remain available for the full `TOTAL_RETENTION_DAYS` TTL window, not just
      `RAW_RETENTION_DAYS`.

    The split point comes from rollup's own checkpoint, not an assumed cutoff: rollup runs
    on its own schedule, so the hours between "whenever it last ran" and "now" have no
    rollup documents at all and must come from the raw scan.
    """
    db = get_db()
    empty = {
        "total_tokens": 0, "prompt_tokens": 0, "response_tokens": 0, "calls": 0,
        "cache_hits": 0, "buckets": [],
    }
    if not db:
        return empty

    now = datetime.now(timezone.utc)
    since_dt = _parse_ts(since) or (now - timedelta(days=RAW_RETENTION_DAYS))
    until_dt = _parse_ts(until) or now
    if since_dt > until_dt:
        return empty

    buckets: Dict[str, Dict[str, int]] = {}
    totals = {"total_tokens": 0, "prompt_tokens": 0, "response_tokens": 0, "calls": 0, "cache_hits": 0}

    def _accumulate(
        key: str, *, prompt: int, response: int, total: int, calls: int, cache_hits: int,
    ) -> None:
        """The single place bucket and total arithmetic happens, for both branches below."""
        bucket = buckets.setdefault(key, {"tokens": 0, "calls": 0})
        bucket["tokens"] += total
        bucket["calls"] += calls
        totals["prompt_tokens"] += prompt
        totals["response_tokens"] += response
        totals["total_tokens"] += total
        totals["calls"] += calls
        totals["cache_hits"] += cache_hits

    def _bucket_key(ts: str) -> str:
        return ts[:10] if group_by == "day" else ts[:13]

    rollup_start, rollup_end = _rollup_span(db, now, since_dt, until_dt)

    for segment_since, segment_until in _raw_segments(since_dt, until_dt, rollup_start, rollup_end):
        segment_since_iso, segment_until_iso = _iso(segment_since), _iso(segment_until)
        batches = _fetch_batches(db, since=segment_since_iso, until=segment_until_iso)
        for event in _flatten_events(
            batches, since=segment_since_iso, until=segment_until_iso, category="llm",
        ):
            data = event.get("data") or {}
            prompt = data.get("prompt_tokens", 0) or 0
            response = data.get("response_tokens", 0) or 0
            _accumulate(
                _bucket_key(event["ts"]),
                prompt=prompt, response=response, total=prompt + response,
                calls=1, cache_hits=1 if data.get("cached") else 0,
            )

    # Each rollup document covers one hour, so `group_by="day"` sums 24 of them into a day.
    hour_keys = list(_hour_keys(rollup_start, rollup_end))
    for hour_key, data in _read_documents(db, ROLLUP_COLLECTION, hour_keys).items():
        llm = data.get("llm", {})
        _accumulate(
            hour_key[:10] if group_by == "day" else hour_key,
            prompt=llm.get("prompt_tokens", 0),
            response=llm.get("response_tokens", 0),
            total=llm.get("total_tokens", 0),
            calls=llm.get("calls", 0),
            cache_hits=llm.get("cache_hits", 0),
        )

    return {
        **totals,
        "buckets": [
            {"bucket": key, "tokens": v["tokens"], "calls": v["calls"]}
            for key, v in sorted(buckets.items())
        ],
    }


def _floor_hour(dt: datetime) -> datetime:
    return dt.replace(minute=0, second=0, microsecond=0)


def _ceil_hour(dt: datetime) -> datetime:
    floored = _floor_hour(dt)
    return floored if floored == dt else floored + timedelta(hours=1)


def _read_rollup_checkpoint(db: Any) -> Optional[datetime]:
    """How far `rollup.py` has actually processed, or None if it has never run."""
    doc = db.collection(ROLLUP_META_COLLECTION).document(ROLLUP_CHECKPOINT_DOC).get()
    if not doc.exists:
        return None
    return _parse_ts((doc.to_dict() or {}).get("last_processed_created_at"))


def _rollup_span(
    db: Any, now: datetime, since_dt: datetime, until_dt: datetime,
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """The `[start, end)` hour-aligned window that should be served from rollup documents.

    Both ends are hour boundaries so a whole-hour bucket is never used to answer a
    part-hour question: `since` at 14:30 must not pull in 14:00-14:30 as well. Returns
    `(None, None)` when there is no usable rollup window, which is the common case -- any
    range inside the raw-retention window, or a deployment where rollup has never run.
    """
    checkpoint = _read_rollup_checkpoint(db)
    if checkpoint is None:
        return None, None

    # Rollup only guarantees an hour once it has processed every batch up to it, and only
    # writes hours older than RAW_RETENTION_DAYS at all -- so trust it strictly before the
    # earlier of the two.
    trusted_until = _floor_hour(min(checkpoint, now - timedelta(days=RAW_RETENTION_DAYS)))

    # Leading edge rounds up, so a mid-hour `since` never drags in the earlier part of its
    # hour -- the raw scan covers that remainder exactly. Trailing edge rounds up too, so
    # the hour `until` falls inside is served rather than dropped; the cost is at most the
    # sliver between `until` and the top of that hour, which is far better than silently
    # losing the last hour of every historical range.
    start = _ceil_hour(since_dt)
    end = min(trusted_until, _ceil_hour(until_dt))
    if end <= start:
        return None, None
    return start, end


def _raw_segments(
    since_dt: datetime,
    until_dt: datetime,
    rollup_start: Optional[datetime],
    rollup_end: Optional[datetime],
) -> List[Tuple[datetime, datetime]]:
    """The inclusive `[since, until]` ranges that must be read from raw batches.

    One segment covering the whole range when no rollup window applies; otherwise the
    partial hour before the rollup window (if `since` fell mid-hour) and everything from
    the rollup window's end onwards.
    """
    if rollup_start is None or rollup_end is None:
        return [(since_dt, until_dt)]

    segments: List[Tuple[datetime, datetime]] = []
    if since_dt < rollup_start:
        segments.append((since_dt, rollup_start - timedelta(microseconds=1)))
    if rollup_end <= until_dt:
        segments.append((rollup_end, until_dt))
    return segments


def _hour_keys(start: Optional[datetime], end: Optional[datetime]):
    """Rollup document ids for every whole hour in `[start, end)`."""
    if start is None or end is None:
        return
    current = start
    while current < end:
        yield rollup_doc_id(current)
        current += timedelta(hours=1)


_PERCENTILE_50 = 0.50
_PERCENTILE_95 = 0.95


def _percentile(values: List[int], pct: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * pct))
    return ordered[index]


def get_health_snapshot() -> Dict[str, Any]:
    """Returns overall health derived from the last hour of raw `logs` events -- always a
    recent, narrow window, so this never reads rollup data (only `get_llm_usage` does, for
    wider historical ranges).

    Per-worker success/failure: `level in {"error", "fatal"}` counts as a failure for that
    worker invocation, matching how `error_rate`/`llm_failure_rate` below are computed --
    simple and consistent, even though a handful of legitimate `warn`-level findings (e.g.
    a worker treating a timeout as a valid security result) will correctly read as
    successes under this rule.
    """
    db = get_db()
    empty = {
        "error_rate": 0.0, "p50_ms": 0, "p95_ms": 0, "requests_1h": 0,
        "workers": [], "llm_failure_rate": 0.0,
    }
    if not db:
        return empty

    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=1)
    batches = _fetch_batches(db, since=_iso(since), until=_iso(now))
    events = _flatten_events(batches, since=_iso(since), until=_iso(now))

    total = len(events)
    error_count = sum(1 for e in events if e.get("level") in ("error", "fatal"))
    error_rate = (error_count / total) if total else 0.0

    http_events = [e for e in events if e.get("category") == "http"]
    durations = [e.get("duration_ms", 0) for e in http_events]

    llm_events = [e for e in events if e.get("category") == "llm"]
    llm_failures = sum(1 for e in llm_events if e.get("level") in ("error", "fatal"))
    llm_failure_rate = (llm_failures / len(llm_events)) if llm_events else 0.0

    worker_events = [e for e in events if e.get("category") == "worker"]
    workers: Dict[str, Dict[str, int]] = {}
    for event in worker_events:
        name = (event.get("data") or {}).get("logger", "unknown").rsplit(".", 1)[-1]
        stats = workers.setdefault(name, {"ok": 0, "failed": 0})
        if event.get("level") in ("error", "fatal"):
            stats["failed"] += 1
        else:
            stats["ok"] += 1

    return {
        "error_rate": error_rate,
        "p50_ms": _percentile(durations, _PERCENTILE_50),
        "p95_ms": _percentile(durations, _PERCENTILE_95),
        "requests_1h": len(http_events),
        "workers": [
            {
                "name": name,
                "ok": stats["ok"],
                "failed": stats["failed"],
                "success_rate": stats["ok"] / (stats["ok"] + stats["failed"]),
            }
            for name, stats in sorted(workers.items())
        ],
        "llm_failure_rate": llm_failure_rate,
    }


def record_uptime_probe(result: Dict[str, Any]) -> None:
    """Increments `uptime/{date}` counters from one probe result (`{"ok": bool, ...}`).

    The only write this module performs, and only ever called from Workstream C's probe
    endpoint. A no-op when Firestore isn't configured, matching every other function here.
    """
    db = get_db()
    if not db or not firestore:
        return

    date = datetime.now(timezone.utc).date().isoformat()
    fields = {"checks": firestore.Increment(1)}
    if not result.get("ok", True):
        fields["failures"] = firestore.Increment(1)
    db.collection(UPTIME_COLLECTION).document(date).set(fields, merge=True)


def get_uptime_history(days: int = 90) -> List[Dict[str, Any]]:
    """Returns `[{"date", "uptime_pct", "checks", "failures"}, ...]` for the last `days`
    days, newest last. Days with no document are still present, with zeroed counts and a
    null percentage, so the caller always gets exactly `days` entries.
    """
    db = get_db()
    if not db:
        return []

    today = datetime.now(timezone.utc).date()
    dates = [(today - timedelta(days=offset)).isoformat() for offset in range(days - 1, -1, -1)]
    documents = _read_documents(db, UPTIME_COLLECTION, dates)

    history = []
    for date in dates:
        data = documents.get(date, {})
        checks = data.get("checks", 0)
        failures = data.get("failures", 0)
        uptime_pct = ((checks - failures) / checks * 100) if checks else None
        history.append({
            "date": date, "uptime_pct": uptime_pct, "checks": checks, "failures": failures,
        })
    return history
