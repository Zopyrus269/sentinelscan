"""Firestore collection layout and document shapes for the observability pipeline.

Defines what a "batch document" looks like -- the unit Workstream B actually writes.
Batching ~100 events into one document is what keeps Firestore's free-tier write quota
(20k writes/day) viable: a ~200-event, 10-minute user session costs roughly two writes,
not two hundred.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from uuid import uuid4

LOGS_COLLECTION = "logs"
PRESENCE_COLLECTION = "presence"
STATS_COLLECTION = "stats"
UPTIME_COLLECTION = "uptime"

# Phase 3 additions -- read layer (query.py) and rollup.py.
# Hourly aggregate summaries rollup.py writes once a batch's events are older than
# RAW_RETENTION_DAYS. Purely an internal storage/read-cost optimization: not part of the
# frozen contract Workstream C codes against, so its existence is invisible to that layer.
ROLLUP_COLLECTION = "logs_hourly"
# Where rollup.py records how far it has processed, so a re-run never double-counts a batch
# it already rolled up. Lives outside LOGS_COLLECTION so it never collides with a batch_id.
ROLLUP_META_COLLECTION = "logs_meta"
ROLLUP_CHECKPOINT_DOC = "rollup_checkpoint"

# How many events accumulate into one Firestore document.
BATCH_SIZE = 100

# Raw batch documents are collapsed into hourly summaries by rollup.py (Phase 3) after
# this many days; the documents themselves are deleted by Firestore's TTL policy after
# TOTAL_RETENTION_DAYS, giving rollup.py a window to have already run.
RAW_RETENTION_DAYS = 7
TOTAL_RETENTION_DAYS = 30


def rollup_doc_id(dt: datetime) -> str:
    """Doc id for one hourly rollup bucket, e.g. "2026-08-22T14" (UTC, hour-truncated)."""
    return dt.strftime("%Y-%m-%dT%H")


def build_batch_document(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Builds the document Workstream B writes to ``logs/{batch_id}``.

    Denormalizes the session_id/trace_id/scan_id present in this batch onto top-level
    array fields so a Firestore ``array_contains`` query can find a batch by one of
    those ids without loading and scanning every document in a time window. These
    three ids are the correlation keys the whole product is built around (see
    ``docs/workstreams/WORKSTREAM_C.md`` section 4: "the two id fields are the heart
    of the product").
    """
    now = datetime.now(timezone.utc)
    return {
        "batch_id": str(uuid4()),
        "created_at": now.isoformat(),
        "expires_at": now + timedelta(days=TOTAL_RETENTION_DAYS),
        "event_count": len(events),
        "events": events,
        "session_ids": _unique_ids(events, "session_id"),
        "trace_ids": _unique_ids(events, "trace_id"),
        "scan_ids": _unique_ids(events, "scan_id"),
    }


def _unique_ids(events: List[Dict[str, Any]], key: str) -> List[str]:
    """Returns the sorted, non-null, de-duplicated values of `key` across `events`."""
    return sorted({event[key] for event in events if event.get(key)})
