# SentinelScan — Getting your API keys/secrets (team setup)

You no longer need to manually ask around for `GEMINI_API_KEY` and other `.env` values. Instead, you fetch them yourself, securely, using the same Google account you already sign into the site with.

## Before you start

- You must have signed into the SentinelScan site at least once with your Google account (so Firebase has a record of you).
- Tell the project admin your Google email so they can allowlist you (see below — this is a one-time step per person, admin-only).
- You need the repo cloned/pulled to latest main, with the Python virtual environment set up as usual.
- Ask the admin (me) for `scripts/oauth_client.json` and place it in your local `scripts/` folder — it's not in git, you'll get it directly (Slack/secure channel).

## One-time setup on your machine

```bash
pip install -r scripts/requirements.txt
```

## Getting your .env secrets

Make sure the backend is running (locally at http://localhost:5000, or whatever URL an admin gives you once the site is deployed), then run:

```bash
python scripts/bootstrap_env.py
```

### What happens:
1. A browser tab opens asking you to sign in with Google — use the same account you use for the site.
2. The script exchanges that sign-in for a secure token and fetches the shared secrets from the backend.
3. It writes them straight into your local `.env` file (any other lines you already have in there are left untouched).

You'll see output like:
```text
Wrote 2 key(s) to .env: GEMINI_API_KEY, DATABASE_URL
```

**Important** — this is not automatic. Pulling from main does not refresh your `.env` by itself. Run `scripts/bootstrap_env.py` again any time:
- You're setting up for the first time.
- An admin tells you a secret was rotated/changed.
- You start getting auth errors that look like a stale/wrong key.

## If something goes wrong

- **"This account is not on the developer allowlist"** — the admin hasn't run the allowlist step for your email yet. Ping them.
- **"config/secrets has not been seeded yet"** — the admin hasn't set up the shared secrets yet. Ping them.
- **A browser/sign-in error mentioning INVALID_IDP_RESPONSE** — this is an admin-side setup issue (wrong Google Cloud project), not something you can fix — flag it to the admin.

## For the admin only (not for regular teammates)

Adding a new teammate, once they've signed into the site at least once with Google:

```bash
python scripts/admin_add_developer.py --email teammate@gmail.com
```

If shared secrets ever change, re-seed them (reads your own local `.env`):

```bash
python scripts/admin_seed_secrets.py
```

Full details: `scripts/README.md` in the repo.
