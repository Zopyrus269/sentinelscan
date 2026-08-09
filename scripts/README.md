# Dev tooling: team secrets bootstrap

Lets teammates fetch the shared dev secrets (`GEMINI_API_KEY`, `FLASK_SECRET_KEY`, etc.) from Firestore after cloning/pulling, instead of manually re-typing them, without putting real secrets in the public repo. Only allowlisted developers can fetch them. See `apps/backend/routes/dev_routes.py` and `apps/backend/auth/auth_utils.py` (`require_developer`) for the backend side.

These scripts are dev tooling only -- never run as part of the deployed app. Install their extra dependency once:

```
pip install -r scripts/requirements.txt
```

## One-time project setup (admin only)

1. Create a Google OAuth **Desktop app** client in Google Cloud Console for this Firebase project (`sentinelscan-3f82d`), download its JSON, and save it as `scripts/oauth_client.json`.
2. With your own working `.env` in place, run:
   ```
   python scripts/admin_seed_secrets.py
   ```
   This copies `GEMINI_API_KEY`, `FLASK_SECRET_KEY`, and `BLOCKED_DOMAINS` from your local `.env` into the `config/secrets` Firestore document.

## Adding a teammate (admin only, per person)

The teammate must have signed into the site with Google at least once already (so a Firebase user record exists for them). Then:

```
python scripts/admin_add_developer.py --email teammate@gmail.com
```

## Fetching secrets (teammate)

Make sure the backend is running (locally at `http://localhost:5000`, or point `--server-url` at wherever it's deployed), then:

```
python scripts/bootstrap_env.py
```

This opens a browser for a one-time Google sign-in, then writes the fetched secrets into your local `.env` (existing unrelated lines are preserved). Re-run it any time secrets rotate.
