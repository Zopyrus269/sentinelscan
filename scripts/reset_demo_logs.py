"""
Deletes demo observability data from Firestore and reseeds it fresh, in one operation.

Session 22 seeded ~14 days of fake observability data (scripts/seed_fake_logs.py) directly into
the live Firestore project so Workstream C could build the log site against real reads before
Workstreams A and B existed. Some of that data carried a bug (finding C3) that made it invisible
to time-range queries; the fix landed in seed_fake_logs.py, but that doesn't repair rows already
written. This script clears everything seed_fake_logs.py could have written and reseeds it
correctly, so there's never a window where the database sits half-cleared or double-counted.

Delete-then-reseed, never reseed-on-top: stats/{date} counters are additive
(firestore.Increment), so reseeding without clearing them first would roughly double every
number. logs/, presence/, logs_hourly/ and logs_meta/ are safe to wipe entirely -- every write to
them is gated behind SENTINELSCAN_TELEMETRY_ENABLED (apps/backend/logstore/pipeline.py's
is_enabled()), which is still off in production, so everything currently in them is demo data.

uptime/ is different: real uptime-probe writes (query.py's record_uptime_probe(), run
independently of the telemetry flag by a separate GitHub Actions workflow) land in the same
date-keyed documents seed_fake_logs.py's _seed_uptime() overwrites outright, with no field
distinguishing real from fake -- so this collection may already mix the two from the original
seeding run. Wiping and reseeding it anyway is a deliberate choice (confirmed with the user) to
make the displayed history clean and demo-realistic again, not a claim that any real historical
numbers survive.

SAFETY: same pattern as seed_fake_logs.py -- prints the target project and exactly what it's
about to touch, and always does a read-only count first. Requires --confirm (or an interactive
y/N) before deleting or writing anything.

Usage:
    python scripts/reset_demo_logs.py --confirm
    python scripts/reset_demo_logs.py --days 7 --sessions-per-day 10 --confirm
    python scripts/reset_demo_logs.py --seed 42          # dry run: prints the plan, asks y/N
"""
import argparse
import importlib.util
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from apps.backend.auth.firebase_client import get_db
from apps.backend.logstore import rollup
from apps.backend.logstore.firestore_sink import FirestoreSink
from apps.backend.logstore.schema import (
    LOGS_COLLECTION,
    PRESENCE_COLLECTION,
    ROLLUP_COLLECTION,
    ROLLUP_META_COLLECTION,
    STATS_COLLECTION,
    UPTIME_COLLECTION,
)

# scripts/ is not a package -- load seed_fake_logs.py by path (same approach
# tests/test_seed_fake_logs.py already uses) so this always reseeds with the exact seeding
# logic that script ships, rather than a second copy that could drift out of sync.
_SEED_SCRIPT = PROJECT_ROOT / "scripts" / "seed_fake_logs.py"


def _load_seed_module():
    spec = importlib.util.spec_from_file_location("seed_fake_logs", _SEED_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


seed_fake_logs = _load_seed_module()

# Collections wiped in full -- see module docstring for why each is safe (or, for uptime/, a
# deliberate choice rather than a safety claim).
_FULL_WIPE_COLLECTIONS = [
    LOGS_COLLECTION, PRESENCE_COLLECTION, ROLLUP_COLLECTION, ROLLUP_META_COLLECTION, UPTIME_COLLECTION,
]


def _count_collection(db: Any, name: str) -> int:
    return sum(1 for _ in db.collection(name).stream())


def _delete_collection(db: Any, name: str) -> int:
    n = 0
    for doc in list(db.collection(name).stream()):
        db.collection(name).document(doc.id).delete()
        n += 1
    return n


def _stats_dates(days: int) -> list:
    today = datetime.now(timezone.utc).date()
    return [(today - timedelta(days=offset)).isoformat() for offset in range(days)]


def _delete_stats_range(db: Any, days: int) -> int:
    """Deletes stats/{date} only for the dates about to be reseeded.

    Unlike the collections in _FULL_WIPE_COLLECTIONS, stats/ isn't purely demo-gated by
    construction in the same unambiguous way (see module docstring) -- scoping the delete to
    exactly the reseeded range is the minimum needed to keep the reseed's Increment-based
    counters correct, without touching any stats/{date} document outside that range.
    """
    n = 0
    for date_str in _stats_dates(days):
        doc = db.collection(STATS_COLLECTION).document(date_str)
        if doc.get().exists:
            doc.delete()
            n += 1
    return n


def _reseed(db: Any, days: int, sessions_per_day: int, seed: int) -> dict:
    """Mirrors seed_fake_logs.py's own main() loop, calling its seeding helpers directly."""
    rng = random.Random(seed)
    sink = FirestoreSink()

    today = datetime.now(timezone.utc).date()
    totals = {"sessions": 0, "events": 0, "batches": 0}
    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        day_counts = seed_fake_logs._seed_day(
            sink, rng, day, sessions_per_day, is_today=(offset == 0),
        )
        for key in totals:
            totals[key] += day_counts[key]

    uptime_days = seed_fake_logs._seed_uptime(db, rng, days)
    rollup_summary = rollup.run_rollup()

    return {**totals, "uptime_days": uptime_days, "rollup": rollup_summary}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deletes demo observability data from Firestore, then reseeds it fresh, in one operation.",
    )
    parser.add_argument("--days", type=int, default=seed_fake_logs.DEFAULT_DAYS, help="How many days back to reset and reseed, including today.")
    parser.add_argument("--sessions-per-day", type=int, default=seed_fake_logs.DEFAULT_SESSIONS_PER_DAY)
    parser.add_argument("--confirm", action="store_true", help="Actually delete and reseed. Omit to preview and be asked y/N.")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for the reseed, for a reproducible run.")
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

    print(f"Target Firestore project: {db.project}")
    print("Read-only count, before anything is touched:")
    counts = {name: _count_collection(db, name) for name in _FULL_WIPE_COLLECTIONS}
    counts[STATS_COLLECTION] = len(_stats_dates(args.days))
    for name in _FULL_WIPE_COLLECTIONS:
        print(f"  {name}: {counts[name]} document(s) -- will be fully deleted")
    print(
        f"  {STATS_COLLECTION}: up to {counts[STATS_COLLECTION]} document(s) in the "
        f"{args.days}-day range about to be reseeded -- only those will be deleted"
    )
    print(
        f"\nThen reseeds: {args.days} day(s) back, ~{args.sessions_per_day} session(s)/day, "
        f"plus {args.days} day(s) of uptime history -- same as scripts/seed_fake_logs.py."
    )

    if not args.confirm:
        answer = input("Proceed and delete-then-reseed this data in Firestore? [y/N] ").strip().lower()
        if answer != "y":
            print("Aborted -- nothing was touched.")
            sys.exit(0)

    print("\nDeleting...")
    deleted = {}
    for name in _FULL_WIPE_COLLECTIONS:
        deleted[name] = _delete_collection(db, name)
        print(f"  {name}: deleted {deleted[name]} document(s)")
    deleted[STATS_COLLECTION] = _delete_stats_range(db, args.days)
    print(f"  {STATS_COLLECTION}: deleted {deleted[STATS_COLLECTION]} document(s)")

    print("\nReseeding...")
    result = _reseed(db, args.days, args.sessions_per_day, args.seed)
    print(
        f"  {result['sessions']} sessions, {result['events']} events, "
        f"{result['batches']} batch document(s), {result['uptime_days']} uptime day(s)"
    )
    print(f"  Rollup: {result['rollup']}")

    print("\nDone.")


if __name__ == "__main__":
    main()
