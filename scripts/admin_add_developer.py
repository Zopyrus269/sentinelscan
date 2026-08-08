"""
Admin-only script: allowlists a teammate for the secrets bootstrap system.

Looks up an existing Firebase Auth user by email (they must have signed
into the site with Google at least once already, so a Firebase user
record exists) and creates a developers/{uid} Firestore document. That
document's existence is what GET /api/v1/dev/bootstrap-secrets checks
via the require_developer decorator (see apps/backend/auth/auth_utils.py).

Usage:
    python scripts/admin_add_developer.py --email teammate@gmail.com
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from firebase_admin import auth as firebase_auth

from apps.backend.auth.firebase_client import get_db


def main() -> None:
    parser = argparse.ArgumentParser(description="Allowlist a teammate for the secrets bootstrap system.")
    parser.add_argument("--email", required=True, help="The teammate's Google account email.")
    args = parser.parse_args()

    db = get_db()
    if not db:
        print("ERROR: Firebase is not configured (secrets/firebase-service-account.json missing or invalid).")
        sys.exit(1)

    try:
        user = firebase_auth.get_user_by_email(args.email)
    except firebase_auth.UserNotFoundError:
        print(
            f"ERROR: No Firebase user found for '{args.email}'. "
            "They need to sign in to the site with Google at least once first."
        )
        sys.exit(1)

    db.collection("developers").document(user.uid).set({
        "email": args.email,
        "added_at": datetime.now(timezone.utc).isoformat(),
    })

    print(f"Allowlisted {args.email} (uid: {user.uid}) as a developer.")


if __name__ == "__main__":
    main()
