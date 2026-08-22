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
from typing import Any, Dict, List, Optional

try:
    from firebase_admin import firestore
except ImportError:
    firestore = None

from apps.backend.auth.firebase_client import get_db
from apps.backend.logstore.schema import (
    LOGS_COLLECTION,
    PRESENCE_COLLECTION,
    ROLLUP_COLLECTION,
    STATS_COLLECTION,
    UPTIME_COLLECTION,
    rollup_doc_id,
)

logger = logging.getLogger(__name__)

DEFAULT_QUERY_LIMIT = 200
MAX_QUERY_LIMIT = 500

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


def _fetch_batches(
    db: Any,
    *,
    since: Optional[str] = None,
    until: Optional[str] = None,
    id_field: Optional[str] = None,
    id_value: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Reads `logs` batch documents, filtered by a widened `created_at` range and,
    optionally, one `array_contains` id filter. Returns raw batch dicts (still containing
    every event, unfiltered) for the caller to flatten/filter further in Python.
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

    query = query.order_by("created_at")
    return [doc.to_dict() for doc in query.stream()]


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
    """
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
    """
    if cursor:
        try:
            cursor_ts, cursor_id = cursor.split("|", 1)
        except ValueError:
            cursor_ts, cursor_id = cursor, ""
        events = [e for e in events if (e["ts"], e["event_id"]) > (cursor_ts, cursor_id)]

    page = events[:limit]
    next_cursor = None
    if len(events) > limit:
        last = page[-1]
        next_cursor = f"{last['ts']}|{last['event_id']}"
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
    """Returns `{"events": [...], "next_cursor": str | None}` matching every given filter,
    newest-filterable-first via cursor pagination (ascending `ts` order; a `next_cursor` is
    given whenever more events exist past `limit`).
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

    batches = _fetch_batches(db, since=since, until=until, id_field=id_field, id_value=id_value)
    events = _flatten_events(
        batches, since=since, until=until, level=level, source=source, category=category,
        session_id=session_id, uid=uid, trace_id=trace_id, scan_id=scan_id,
    )
    return _paginate(events, cursor, limit)


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
    """
    db = get_db()
    if not db:
        return {"count": 0, "sessions": []}

    cutoff = _iso(datetime.now(timezone.utc) - timedelta(minutes=window_minutes))
    query = db.collection(PRESENCE_COLLECTION).where("last_seen", ">=", cutoff)

    sessions = [
        {
            "session_id": data.get("session_id"),
            "uid": data.get("uid"),
            "last_seen": data.get("last_seen"),
        }
        for data in (doc.to_dict() for doc in query.stream())
    ]
    return {"count": len(sessions), "sessions": sessions}


def get_daily_stats(date: str) -> Dict[str, Any]:
    """Returns one day's aggregate counters from `stats/{date}` -- a single document read.

    `unique_sessions` comes from that document's `session_ids` array field (unioned at
    write time by `firestore_sink.py`), not a separate scan.
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
        "unique_sessions": len(data.get("session_ids", [])),
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


def _daterange(since_dt: datetime, until_dt: datetime):
    day = since_dt.date()
    end = until_dt.date()
    while day <= end:
        yield day.isoformat()
        day += timedelta(days=1)


def get_llm_usage(
    *,
    since: Optional[str] = None,
    until: Optional[str] = None,
    group_by: str = "day",
) -> Dict[str, Any]:
    """Returns Gemini usage totals and per-bucket breakdown over `[since, until]`.

    Reads raw `logs` batches directly (filtered to `category="llm"`) -- correct for the
    whole 30-day retention window, since raw batches aren't deleted until Firestore's TTL
    fires. For a range that's mostly older than `RAW_RETENTION_DAYS`, prefer `logs_hourly`
    rollup buckets where `rollup.py` has already produced them, since they're far cheaper to
    read than re-scanning every raw batch in that window; falls back to the raw scan for any
    bucket a rollup doesn't (yet) cover.
    """
    db = get_db()
    empty = {
        "total_tokens": 0, "prompt_tokens": 0, "response_tokens": 0, "calls": 0,
        "cache_hits": 0, "buckets": [],
    }
    if not db:
        return empty

    now = datetime.now(timezone.utc)
    since_dt = _parse_ts(since) or (now - timedelta(days=7))
    until_dt = _parse_ts(until) or now
    raw_cutoff = now - timedelta(days=7)

    buckets: Dict[str, Dict[str, int]] = {}
    totals = {"total_tokens": 0, "prompt_tokens": 0, "response_tokens": 0, "calls": 0, "cache_hits": 0}

    def _bucket_key(ts: str) -> str:
        return ts[:10] if group_by == "day" else ts[:13]

    def _accumulate(key: str, prompt: int, response: int, cached: bool) -> None:
        bucket = buckets.setdefault(key, {"tokens": 0, "calls": 0})
        bucket["tokens"] += prompt + response
        bucket["calls"] += 1
        totals["prompt_tokens"] += prompt
        totals["response_tokens"] += response
        totals["total_tokens"] += prompt + response
        totals["calls"] += 1
        if cached:
            totals["cache_hits"] += 1

    # Recent window: always scan raw batches (rollup may not have caught up yet).
    recent_since = max(since_dt, raw_cutoff)
    if recent_since <= until_dt:
        batches = _fetch_batches(db, since=_iso(recent_since), until=_iso(until_dt))
        for event in _flatten_events(
            batches, since=_iso(recent_since), until=_iso(until_dt), category="llm",
        ):
            data = event.get("data") or {}
            _accumulate(
                _bucket_key(event["ts"]),
                data.get("prompt_tokens", 0) or 0,
                data.get("response_tokens", 0) or 0,
                bool(data.get("cached")),
            )

    # Older window: prefer rollup docs; each covers one hour, so `group_by="day"` sums 24
    # of them into that day's bucket.
    if since_dt < raw_cutoff:
        for hour_key in _hour_range(since_dt, min(until_dt, raw_cutoff)):
            doc = db.collection(ROLLUP_COLLECTION).document(hour_key).get()
            if not doc.exists:
                continue
            data = doc.to_dict() or {}
            llm = data.get("llm", {})
            key = hour_key[:10] if group_by == "day" else hour_key
            bucket = buckets.setdefault(key, {"tokens": 0, "calls": 0})
            bucket["tokens"] += llm.get("total_tokens", 0)
            bucket["calls"] += llm.get("calls", 0)
            totals["prompt_tokens"] += llm.get("prompt_tokens", 0)
            totals["response_tokens"] += llm.get("response_tokens", 0)
            totals["total_tokens"] += llm.get("total_tokens", 0)
            totals["calls"] += llm.get("calls", 0)
            totals["cache_hits"] += llm.get("cache_hits", 0)

    return {
        **totals,
        "buckets": [
            {"bucket": key, "tokens": v["tokens"], "calls": v["calls"]}
            for key, v in sorted(buckets.items())
        ],
    }


def _hour_range(start: datetime, end: datetime):
    current = start.replace(minute=0, second=0, microsecond=0)
    while current <= end:
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
    days, newest last, reading one small `uptime/{date}` document per day.
    """
    db = get_db()
    if not db:
        return []

    today = datetime.now(timezone.utc).date()
    history = []
    for offset in range(days - 1, -1, -1):
        date = (today - timedelta(days=offset)).isoformat()
        doc = db.collection(UPTIME_COLLECTION).document(date).get()
        data = doc.to_dict() if doc.exists else None
        checks = (data or {}).get("checks", 0)
        failures = (data or {}).get("failures", 0)
        uptime_pct = ((checks - failures) / checks * 100) if checks else None
        history.append({
            "date": date, "uptime_pct": uptime_pct, "checks": checks, "failures": failures,
        })
    return history
