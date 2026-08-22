"""Collapses raw events older than RAW_RETENTION_DAYS into hourly summary documents.

Raw `logs/{batch_id}` documents aren't deleted until Firestore's `expires_at` TTL fires at
TOTAL_RETENTION_DAYS -- rollup.py exists to give wide, historical queries (like
`query.get_llm_usage` over weeks of data) a much cheaper alternative to re-scanning every
raw batch in that range, once its events are old enough that day-to-day detail no longer
matters, only the aggregate.

Does **not** delete or modify raw batch documents -- that stays Firestore's TTL policy's job.
Safe to re-run at any time: a `logs_meta/rollup_checkpoint` document tracks the latest
`created_at` already processed, so a re-run only ever picks up batches after that point.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

try:
    from firebase_admin import firestore
except ImportError:
    firestore = None

from apps.backend.auth.firebase_client import get_db
from apps.backend.logstore.schema import (
    LOGS_COLLECTION,
    RAW_RETENTION_DAYS,
    ROLLUP_CHECKPOINT_DOC,
    ROLLUP_COLLECTION,
    ROLLUP_META_COLLECTION,
    rollup_doc_id,
)

logger = logging.getLogger(__name__)

_EPOCH_ISO = "1970-01-01T00:00:00+00:00"
_CHECKPOINT_FIELD = "last_processed_created_at"


def _empty_summary() -> Dict[str, Any]:
    return {"batches_processed": 0, "hours_written": 0, "checkpoint": None}


def run_rollup(now: Optional[datetime] = None) -> Dict[str, Any]:
    """Rolls up every not-yet-processed batch older than RAW_RETENTION_DAYS.

    Returns `{"batches_processed", "hours_written", "checkpoint"}` describing what this run
    did, for a caller or test to assert on. A no-op (zeroed summary) when Firestore isn't
    configured, or when there is nothing new to process.
    """
    db = get_db()
    if not db or not firestore:
        return _empty_summary()

    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=RAW_RETENTION_DAYS)

    checkpoint = _read_checkpoint(db)
    if checkpoint >= cutoff:
        return _empty_summary()

    query = (
        db.collection(LOGS_COLLECTION)
        .where("created_at", ">", checkpoint.isoformat())
        .where("created_at", "<=", cutoff.isoformat())
        .order_by("created_at")
    )
    batches = [doc.to_dict() for doc in query.stream()]
    if not batches:
        return _empty_summary()

    hourly = _aggregate(batches)
    for hour_key, bucket in hourly.items():
        _write_hour(db, hour_key, bucket)

    latest_created_at = max(batch["created_at"] for batch in batches)
    _write_checkpoint(db, latest_created_at)

    return {
        "batches_processed": len(batches),
        "hours_written": len(hourly),
        "checkpoint": latest_created_at,
    }


def _read_checkpoint(db: Any) -> datetime:
    doc = db.collection(ROLLUP_META_COLLECTION).document(ROLLUP_CHECKPOINT_DOC).get()
    value = (doc.to_dict() or {}).get(_CHECKPOINT_FIELD) if doc.exists else None
    return datetime.fromisoformat(value) if value else datetime.fromisoformat(_EPOCH_ISO)


def _write_checkpoint(db: Any, created_at_iso: str) -> None:
    db.collection(ROLLUP_META_COLLECTION).document(ROLLUP_CHECKPOINT_DOC).set(
        {_CHECKPOINT_FIELD: created_at_iso}, merge=True,
    )


def _new_bucket() -> Dict[str, Any]:
    return {
        "event_count": 0,
        "by_level": {"debug": 0, "info": 0, "warn": 0, "error": 0, "fatal": 0},
        "by_category": {},
        "llm": {"calls": 0, "prompt_tokens": 0, "response_tokens": 0, "total_tokens": 0, "cache_hits": 0},
        "http": {"count": 0, "duration_ms_sum": 0, "error_count": 0},
    }


def _aggregate(batches: list) -> Dict[str, Dict[str, Any]]:
    """Groups every event across `batches` into per-hour aggregate buckets."""
    hourly: Dict[str, Dict[str, Any]] = {}
    for batch in batches:
        for event in batch.get("events", []):
            hour_dt = datetime.fromisoformat(event["ts"]).replace(minute=0, second=0, microsecond=0)
            key = rollup_doc_id(hour_dt)
            bucket = hourly.setdefault(key, _new_bucket())

            bucket["event_count"] += 1
            level = event.get("level")
            if level in bucket["by_level"]:
                bucket["by_level"][level] += 1

            category = event.get("category", "unknown")
            bucket["by_category"][category] = bucket["by_category"].get(category, 0) + 1

            if category == "llm":
                data = event.get("data") or {}
                llm = bucket["llm"]
                llm["calls"] += 1
                llm["prompt_tokens"] += data.get("prompt_tokens", 0) or 0
                llm["response_tokens"] += data.get("response_tokens", 0) or 0
                llm["total_tokens"] += data.get("total_tokens", 0) or 0
                if data.get("cached"):
                    llm["cache_hits"] += 1
            elif category == "http":
                http = bucket["http"]
                http["count"] += 1
                http["duration_ms_sum"] += event.get("duration_ms", 0) or 0
                if level in ("error", "fatal"):
                    http["error_count"] += 1
    return hourly


def _write_hour(db: Any, hour_key: str, bucket: Dict[str, Any]) -> None:
    """Merges `bucket`'s counts into `logs_hourly/{hour_key}` via Increment, so re-running
    this rollup for an hour it already partially wrote (e.g. after a crash) only adds the
    delta rather than double-counting from scratch -- each event is only ever aggregated
    once per run, and the checkpoint ensures a run never revisits an hour's source batches.

    Uses nested maps (not dotted field-path strings) so Firestore's `set(..., merge=True)`
    deep-merges each leaf independently -- writing `by_level.debug` here never clobbers an
    existing `by_level.error` count from an earlier partial run of the same hour.
    """
    fields: Dict[str, Any] = {"event_count": firestore.Increment(bucket["event_count"])}

    by_level = {lvl: firestore.Increment(c) for lvl, c in bucket["by_level"].items() if c}
    if by_level:
        fields["by_level"] = by_level

    by_category = {cat: firestore.Increment(c) for cat, c in bucket["by_category"].items() if c}
    if by_category:
        fields["by_category"] = by_category

    llm = {key: firestore.Increment(value) for key, value in bucket["llm"].items() if value}
    if llm:
        fields["llm"] = llm

    http = {key: firestore.Increment(value) for key, value in bucket["http"].items() if value}
    if http:
        fields["http"] = http

    db.collection(ROLLUP_COLLECTION).document(hour_key).set(fields, merge=True)
