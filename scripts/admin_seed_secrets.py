"""
Admin-only, one-off script: seeds the shared dev secrets into Firestore.

Copies the given keys out of the local .env (the admin's real, working
values) into the config/secrets Firestore document, so that allowlisted
teammates can fetch them later via GET /api/v1/dev/bootstrap-secrets
(see dev_routes.py) instead of manually re-typing them.

Requires secrets/firebase-service-account.json to already be present
(same file the running backend already uses for Firebase Admin access).

Usage:
    python scripts/admin_seed_secrets.py
"""
import os
import sys
from pathlib import Path
from typing import Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from apps.backend.auth.firebase_client import get_db

SHARED_SECRET_KEYS = [
    "GEMINI_API_KEY",
    "FLASK_SECRET_KEY",
    "DATABASE_URL",
    "BLOCKED_DOMAINS",
]


def collect_secrets(keys: list) -> Dict[str, str]:
    """Reads the given env var names, skipping any that are unset/empty."""
    values = {}
    for key in keys:
        value = os.environ.get(key)
        if value:
            values[key] = value
    return values


def main() -> None:
    db = get_db()
    if not db:
        print("ERROR: Firebase is not configured (secrets/firebase-service-account.json missing or invalid).")
        sys.exit(1)

    values = collect_secrets(SHARED_SECRET_KEYS)
    missing = [k for k in SHARED_SECRET_KEYS if k not in values]

    if not values:
        print("ERROR: None of the expected keys were found in .env. Nothing to seed.")
        sys.exit(1)

    db.collection("config").document("secrets").set(values)

    print(f"Seeded config/secrets with {len(values)} key(s): {', '.join(values.keys())}")
    if missing:
        print(f"Skipped (not set locally): {', '.join(missing)}")


if __name__ == "__main__":
    main()
