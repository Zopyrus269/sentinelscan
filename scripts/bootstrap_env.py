"""
Teammate-facing script: fetches the shared dev secrets and writes them
into a local .env file.

Signs in with the developer's own Google account (an installed-app OAuth
flow -- a browser tab opens once), exchanges that for a Firebase ID
token, then calls GET /api/v1/dev/bootstrap-secrets on the running
backend. The caller must already be allowlisted by an admin via
scripts/admin_add_developer.py.

Usage:
    python scripts/bootstrap_env.py
    python scripts/bootstrap_env.py --server-url http://localhost:5000
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Dict

import requests
from google_auth_oauthlib.flow import InstalledAppFlow

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OAUTH_CLIENT_CONFIG = Path(__file__).resolve().parent / "oauth_client.json"
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
DEFAULT_SERVER_URL = "http://localhost:5000"

# Firebase Web API key for this project -- not a secret; it's the same
# public identifier already committed in apps/frontend/static/js/auth.js.
FIREBASE_WEB_API_KEY = "AIzaSyBvWgaqLbG9la-77P__L5WACBQ4t3kkCFU"
FIREBASE_SIGN_IN_WITH_IDP_URL = (
    f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key={FIREBASE_WEB_API_KEY}"
)

OAUTH_SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email"]


def get_google_id_token(oauth_client_config_path: Path) -> str:
    """Runs the installed-app OAuth flow, opening a browser once, and
    returns the resulting Google ID token."""
    if not oauth_client_config_path.exists():
        print(f"ERROR: OAuth client config not found at {oauth_client_config_path}.")
        print("Ask an admin for scripts/oauth_client.json.")
        sys.exit(1)

    with open(oauth_client_config_path, "r", encoding="utf-8") as f:
        client_config = json.load(f)

    flow = InstalledAppFlow.from_client_config(client_config, scopes=OAUTH_SCOPES)
    flow.run_local_server(port=0, prompt="select_account")

    id_token = flow.credentials.id_token
    if not id_token:
        print("ERROR: Google did not return an ID token. Try again.")
        sys.exit(1)
    return id_token


def exchange_for_firebase_token(google_id_token: str) -> str:
    """Exchanges a Google ID token for a Firebase ID token via the
    Firebase Auth REST API, matching the UID the website's own Google
    Sign-In flow would produce for the same account."""
    response = requests.post(
        FIREBASE_SIGN_IN_WITH_IDP_URL,
        json={
            "postBody": f"id_token={google_id_token}&providerId=google.com",
            "requestUri": "http://localhost",
            "returnSecureToken": True,
        },
        timeout=15,
    )
    if response.status_code != 200:
        print(f"ERROR: Firebase sign-in exchange failed ({response.status_code}): {response.text}")
        sys.exit(1)
    return response.json()["idToken"]


def fetch_secrets(server_url: str, firebase_id_token: str) -> Dict[str, str]:
    """Calls the backend's bootstrap-secrets endpoint with the Firebase
    ID token and returns the secrets dict."""
    response = requests.get(
        f"{server_url.rstrip('/')}/api/v1/dev/bootstrap-secrets",
        headers={"Authorization": f"Bearer {firebase_id_token}"},
        timeout=15,
    )
    if response.status_code == 403:
        print("ERROR: This account is not on the developer allowlist. Ask an admin to run scripts/admin_add_developer.py for your email.")
        sys.exit(1)
    if response.status_code == 404:
        print("ERROR: config/secrets has not been seeded yet. Ask an admin to run scripts/admin_seed_secrets.py.")
        sys.exit(1)
    if response.status_code != 200:
        print(f"ERROR: Unexpected response ({response.status_code}): {response.text}")
        sys.exit(1)
    return response.json()


def write_env_file(env_file_path: Path, secrets: Dict[str, str]) -> None:
    """Merges the given key/value pairs into the .env file, preserving
    any existing unrelated lines and updating in place where a key
    already exists."""
    existing_lines = []
    if env_file_path.exists():
        existing_lines = env_file_path.read_text(encoding="utf-8").splitlines()

    remaining = dict(secrets)
    updated_lines = []
    for line in existing_lines:
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                updated_lines.append(f"{key}={remaining.pop(key)}")
                continue
        updated_lines.append(line)

    for key, value in remaining.items():
        updated_lines.append(f"{key}={value}")

    env_file_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch shared dev secrets into a local .env file.")
    parser.add_argument("--server-url", default=DEFAULT_SERVER_URL, help=f"Backend URL (default: {DEFAULT_SERVER_URL})")
    parser.add_argument("--oauth-client-config", default=str(DEFAULT_OAUTH_CLIENT_CONFIG))
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    args = parser.parse_args()

    print("Opening a browser to sign in with your Google account...")
    google_id_token = get_google_id_token(Path(args.oauth_client_config))

    firebase_id_token = exchange_for_firebase_token(google_id_token)

    print(f"Fetching secrets from {args.server_url} ...")
    secrets = fetch_secrets(args.server_url, firebase_id_token)

    write_env_file(Path(args.env_file), secrets)
    print(f"Wrote {len(secrets)} key(s) to {args.env_file}: {', '.join(secrets.keys())}")


if __name__ == "__main__":
    main()
