"""
Seeds realistic, schema-conformant fake observability data into Firestore so
Workstream C's log site (and this repo's maintainer) can exercise every screen
against real reads without Workstreams A or B needing to be "live" in production.

Writes directly into the same collections apps/backend/logstore/query.py reads:
logs/, presence/, stats/, uptime/, and (via a real rollup.py run) logs_hourly/.
Reuses FirestoreSink.write_batch() for the logs/presence/stats document shapes --
no duplicated batch-document logic -- and calls rollup.run_rollup() for real after
seeding, so backdated batches older than RAW_RETENTION_DAYS get rolled up exactly
the way production does.

Every seeded event carries env="dev" so it stays visually distinguishable from
real "prod" telemetry once that exists in the same collections.

SAFETY: this machine's .env may hold real Firebase credentials, in which case
get_db() resolves to the live production Firestore project, not a sandbox. This
script always prints which project it's about to write to and how much data,
then requires --confirm (or an interactive y/N) before writing anything.

Usage:
    python scripts/seed_fake_logs.py --confirm
    python scripts/seed_fake_logs.py --days 7 --sessions-per-day 10 --confirm
    python scripts/seed_fake_logs.py --seed 42          # dry run: prints the plan, asks y/N
"""
import argparse
import hashlib
import random
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from apps.backend.auth.firebase_client import get_db
from apps.backend.logstore import rollup
from apps.backend.logstore.firestore_sink import FirestoreSink
from apps.backend.logstore.schema import BATCH_SIZE, RAW_RETENTION_DAYS, UPTIME_COLLECTION

DEFAULT_DAYS = 14
DEFAULT_SESSIONS_PER_DAY = 20

ENV = "dev"
RELEASE = "dev"

# Only the 11 workers the AI agent actually dispatches (docs/WORKERS.md); excludes
# apps/backend/workers/ddos_worker.py, which isn't part of that dispatchable set.
WORKERS = [
    ("reverse_dns", "apps.backend.workers.reverse_dns_worker"),
    ("dns_lookup", "apps.backend.workers.dns_worker"),
    ("whois_lookup", "apps.backend.workers.whois_worker"),
    ("port_scan", "apps.backend.workers.portscan_worker"),
    ("ssl_check", "apps.backend.workers.ssl_worker"),
    ("http_headers", "apps.backend.workers.headers_worker"),
    ("cookie_check", "apps.backend.workers.cookie_worker"),
    ("sitemap_check", "apps.backend.workers.sitemap_worker"),
    ("robots_check", "apps.backend.workers.robots_worker"),
    ("cvss_score", "apps.backend.workers.cvss_worker"),
    ("generate_report", "apps.backend.workers.report_worker"),
]

FAKE_TARGETS = [
    "example.com", "acme.com", "testsite.org", "demo-app.io", "sample-shop.net",
    "mycompany.dev", "blogplatform.com", "startup-x.io",
]

ERROR_MESSAGES = [
    ("TypeError", "TypeError: cannot read properties of undefined (reading 'score')"),
    ("NetworkError", "Failed to fetch: NetworkError when attempting to fetch resource"),
    ("TimeoutError", "Worker timed out after 10000ms"),
    ("ValueError", "ValueError: invalid target format"),
]

# How many of "today"'s sessions get shifted so their last event lands within the
# last few minutes -- otherwise every seeded session is backdated and
# query.count_active_users()'s 5-minute window shows zero the moment the demo opens.
NEAR_NOW_SESSIONS = 3


def _fingerprint(error_type: str) -> str:
    return hashlib.sha1(error_type.encode()).hexdigest()[:8]


def _raw_event(
    *, ts_dt: datetime, level: str, source: str, category: str, message: str,
    trace_id: Optional[str], session_id: Optional[str], uid: Optional[str],
    scan_id: Optional[str] = None, duration_ms: int = 0,
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """One event, every frozen schema field always present (null, never omitted)."""
    return {
        "event_id": str(uuid.uuid4()),
        "ts_dt": ts_dt,
        "level": level,
        "source": source,
        "category": category,
        "message": message,
        "trace_id": trace_id,
        "session_id": session_id,
        "uid": uid,
        "scan_id": scan_id,
        "duration_ms": int(duration_ms),
        "data": data if data is not None else {},
        "release": RELEASE,
        "env": ENV,
    }


def _finalize(raw: Dict[str, Any]) -> Dict[str, Any]:
    event = dict(raw)
    ts_dt = event.pop("ts_dt")
    event["ts"] = ts_dt.astimezone(timezone.utc).isoformat()
    return event


def _fake_uid(rng: random.Random) -> Optional[str]:
    if rng.random() < 0.35:
        return f"fakeuid-{rng.randrange(1000, 9999)}"
    return None


def _generate_scan_action(
    events: List[Dict[str, Any]], rng: random.Random, cursor: datetime,
    session_id: str, uid: Optional[str], *, with_error: bool,
) -> datetime:
    """Appends one "click Start Scan" action -- an http/scan/llm/agent/worker chain
    sharing one trace_id -- to `events`, matching the collapsed/expanded example in
    docs/workstreams/WORKSTREAM_C.md section 9.3. Returns the cursor advanced past it.
    """
    trace_id = str(uuid.uuid4())
    scan_id = str(uuid.uuid4())
    target = rng.choice(FAKE_TARGETS)

    events.append(_raw_event(
        ts_dt=cursor, level="info", source="frontend", category="ui",
        message='clicked "Start Scan"', trace_id=trace_id, session_id=session_id, uid=uid,
        data={"action": "click", "target": "start-scan-button", "label": "Start Scan", "route": "/dashboard"},
    ))
    cursor += timedelta(milliseconds=rng.uniform(50, 250))

    http_duration = rng.randint(120, 450)
    events.append(_raw_event(
        ts_dt=cursor, level="info", source="backend", category="http",
        message="POST /api/v1/scans -> 202", trace_id=trace_id, session_id=session_id, uid=uid,
        scan_id=scan_id, duration_ms=http_duration,
        data={
            "method": "POST", "path": "/api/v1/scans", "route": "/api/v1/scans", "status": 202,
            "ip_hash": hashlib.sha1(session_id.encode()).hexdigest()[:12],
            "ua": "Mozilla/5.0", "query_keys": [],
        },
    ))
    cursor += timedelta(milliseconds=http_duration)

    events.append(_raw_event(
        ts_dt=cursor, level="info", source="backend", category="scan",
        message=f"scan started: target={target}", trace_id=trace_id, session_id=session_id, uid=uid,
        scan_id=scan_id, data={"target": target, "status": "started"},
    ))
    cursor += timedelta(milliseconds=rng.uniform(200, 600))

    num_workers = rng.randint(2, 5)
    for i in range(num_workers):
        tool, worker_module = rng.choice(WORKERS)
        prompt_tokens = rng.randint(400, 1600)
        response_tokens = rng.randint(40, 300)
        llm_duration = rng.randint(400, 1800)
        events.append(_raw_event(
            ts_dt=cursor, level="info", source="agent", category="llm",
            message=f"gemini: {prompt_tokens} + {response_tokens} tokens",
            trace_id=trace_id, session_id=session_id, uid=uid, scan_id=scan_id,
            duration_ms=llm_duration,
            data={
                "model": "gemini-2.0-flash", "prompt_tokens": prompt_tokens,
                "response_tokens": response_tokens, "total_tokens": prompt_tokens + response_tokens,
                "cached": rng.random() < 0.2, "retries": 0,
            },
        ))
        cursor += timedelta(milliseconds=llm_duration)

        events.append(_raw_event(
            ts_dt=cursor, level="info", source="agent", category="agent",
            message=f"AI selected {tool}", trace_id=trace_id, session_id=session_id, uid=uid,
            scan_id=scan_id,
            data={
                "tool_name": tool, "phase": "dispatch", "iteration": i + 1,
                "reasoning": f"Running {tool} next builds on what we've already learned about {target}.",
                "action": "dispatch",
            },
        ))
        cursor += timedelta(milliseconds=rng.uniform(50, 200))

        worker_failed = rng.random() < 0.08
        worker_duration = rng.randint(200, 4000)
        outcome = rng.choice(["FAILED", "TIMEOUT"]) if worker_failed else "COMPLETED"
        events.append(_raw_event(
            ts_dt=cursor, level=("error" if worker_failed else "info"), source="worker", category="worker",
            message=f"{tool} {outcome}", trace_id=trace_id, session_id=session_id, uid=uid, scan_id=scan_id,
            duration_ms=worker_duration,
            data={"logger": worker_module, "func": "run", "line": rng.randint(10, 300)},
        ))
        cursor += timedelta(milliseconds=worker_duration)

    if with_error:
        error_type, message = rng.choice(ERROR_MESSAGES)
        events.append(_raw_event(
            ts_dt=cursor, level="error", source=rng.choice(["frontend", "backend"]), category="error",
            message=message, trace_id=trace_id, session_id=session_id, uid=uid, scan_id=scan_id,
            data={
                "type": error_type, "stack": f"{error_type} at report.js:412",
                "fingerprint": _fingerprint(error_type), "route": "/dashboard",
            },
        ))
        cursor += timedelta(milliseconds=rng.uniform(20, 100))

    return cursor


def _generate_session(
    rng: random.Random, day: date, day_end: datetime, *, near_now: bool,
) -> List[Dict[str, Any]]:
    """Builds one fake visit: a standalone nav event, then 2-4 "Start Scan"-style
    actions, each an http/scan/llm/agent/worker chain sharing one trace_id (~15-20%
    end in an error). `day_end` caps how late in `day` the session can start, so a
    "today" session's random start time never lands in the future relative to now.
    """
    session_id = str(uuid.uuid4())
    uid = _fake_uid(rng)

    day_start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    latest_start = min(day_end - timedelta(minutes=5), day_start + timedelta(hours=23, minutes=59))
    span_seconds = max(int((latest_start - day_start).total_seconds()), 1)
    session_start = day_start + timedelta(seconds=rng.randrange(0, span_seconds))

    raw_events: List[Dict[str, Any]] = []
    cursor = session_start

    nav_trace = str(uuid.uuid4())
    raw_events.append(_raw_event(
        ts_dt=cursor, level="info", source="frontend", category="ui",
        message="opened /dashboard", trace_id=nav_trace, session_id=session_id, uid=uid,
        data={"action": "nav", "target": "/dashboard", "label": None, "route": "/dashboard"},
    ))
    cursor += timedelta(seconds=rng.uniform(2, 8))

    num_actions = rng.randint(2, 4)
    error_on_action = rng.randrange(num_actions) if rng.random() < 0.18 else None
    for i in range(num_actions):
        cursor = _generate_scan_action(
            raw_events, rng, cursor, session_id, uid, with_error=(i == error_on_action),
        )

    if near_now:
        target_last = datetime.now(timezone.utc) - timedelta(seconds=rng.uniform(30, 180))
        shift = target_last - raw_events[-1]["ts_dt"]
        for raw in raw_events:
            raw["ts_dt"] += shift

    return [_finalize(raw) for raw in raw_events]


def _write_events(sink: FirestoreSink, events: List[Dict[str, Any]], *, now: Optional[datetime]) -> int:
    events.sort(key=lambda e: e["ts"])
    batches = 0
    for start in range(0, len(events), BATCH_SIZE):
        sink.write_batch(events[start:start + BATCH_SIZE], now=now)
        batches += 1
    return batches


def _seed_day(
    sink: FirestoreSink, rng: random.Random, day: date, sessions_per_day: int, *, is_today: bool,
) -> Dict[str, int]:
    """Seeds one day's sessions, writing "today"'s near-now sessions in their own
    batch with a real (unbackdated) `now`, so they fall inside get_health_snapshot()'s
    and count_active_users()'s narrow recent-time windows -- and everything else in a
    day-scoped batch stamped at noon that day.
    """
    day_end = datetime.now(timezone.utc) if is_today else datetime(
        day.year, day.month, day.day, 23, 59, 59, tzinfo=timezone.utc,
    )
    near_now_target = min(NEAR_NOW_SESSIONS, sessions_per_day) if is_today else 0

    regular_events: List[Dict[str, Any]] = []
    near_now_events: List[Dict[str, Any]] = []
    for i in range(sessions_per_day):
        near_now = i < near_now_target
        session_events = _generate_session(rng, day, day_end, near_now=near_now)
        (near_now_events if near_now else regular_events).extend(session_events)

    day_noon = datetime(day.year, day.month, day.day, 12, 0, tzinfo=timezone.utc)
    batches = _write_events(sink, regular_events, now=day_noon)
    if near_now_events:
        batches += _write_events(sink, near_now_events, now=None)

    return {
        "sessions": sessions_per_day,
        "events": len(regular_events) + len(near_now_events),
        "batches": batches,
    }


def _seed_uptime(db: Any, rng: random.Random, days: int) -> int:
    """Writes `uptime/{date}` directly (not via repeated record_uptime_probe() calls,
    which would cost one Firestore write per simulated 5-minute check -- hundreds per
    day for no benefit). Mostly-healthy days, an occasional day with a few failures.
    """
    today = datetime.now(timezone.utc).date()
    for offset in range(days):
        day = today - timedelta(days=offset)
        checks = rng.randint(260, 288)
        failures = rng.randint(1, 4) if rng.random() < 0.12 else 0
        db.collection(UPTIME_COLLECTION).document(day.isoformat()).set({
            "checks": checks, "failures": failures,
        })
    return days


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seeds realistic fake observability data into Firestore for Workstream C's log site.",
    )
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="How many days back to seed, including today.")
    parser.add_argument("--sessions-per-day", type=int, default=DEFAULT_SESSIONS_PER_DAY)
    parser.add_argument("--confirm", action="store_true", help="Actually write. Omit to preview and be asked y/N.")
    parser.add_argument("--seed", type=int, default=None, help="Random seed, for a reproducible run.")
    args = parser.parse_args()

    if args.days < 1 or args.sessions_per_day < 1:
        print("ERROR: --days and --sessions-per-day must each be at least 1.")
        sys.exit(1)

    db = get_db()
    if not db:
        print(
            "ERROR: Firebase is not configured (secrets/firebase-service-account.json missing or "
            "invalid, and FIREBASE_SERVICE_ACCOUNT_PATH not overriding it)."
        )
        sys.exit(1)

    total_sessions = args.days * args.sessions_per_day
    print(f"Target Firestore project: {db.project}")
    print(
        f"Plan: {args.days} day(s) back, ~{args.sessions_per_day} session(s)/day "
        f"(~{total_sessions} sessions total, each generating roughly 15-45 events), "
        f"plus {args.days} day(s) of uptime history."
    )
    if args.days > RAW_RETENTION_DAYS:
        print(
            f"This also runs rollup.run_rollup() afterward to summarize the portion older "
            f"than {RAW_RETENTION_DAYS} days."
        )

    if not args.confirm:
        answer = input("Proceed and write this to Firestore? [y/N] ").strip().lower()
        if answer != "y":
            print("Aborted -- nothing was written.")
            sys.exit(0)

    rng = random.Random(args.seed)
    sink = FirestoreSink()

    today = datetime.now(timezone.utc).date()
    totals = {"sessions": 0, "events": 0, "batches": 0}
    for offset in range(args.days - 1, -1, -1):
        day = today - timedelta(days=offset)
        day_counts = _seed_day(sink, rng, day, args.sessions_per_day, is_today=(offset == 0))
        for key in totals:
            totals[key] += day_counts[key]
        print(
            f"  {day.isoformat()}: {day_counts['sessions']} sessions, "
            f"{day_counts['events']} events, {day_counts['batches']} batch document(s)"
        )

    uptime_days = _seed_uptime(db, rng, args.days)
    print(f"Uptime: {uptime_days} day(s) written to '{UPTIME_COLLECTION}'.")

    rollup_summary = rollup.run_rollup()
    print(f"Rollup: {rollup_summary}")

    print(
        f"\nDone. {totals['sessions']} sessions, {totals['events']} events, "
        f"{totals['batches']} batch document(s), {uptime_days} uptime day(s) written."
    )


if __name__ == "__main__":
    main()
