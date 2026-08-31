# Hosting handoff

Shreyas is stepping back from this project to continue independently under a new name
("Knox"), in a separate private repo. As of **2026-08-31**, the Render hosting that was running
under his account is being disconnected:

- Main app — was live at `https://sentinelscan-yd2u.onrender.com`
- Log site — was live at `https://sentinelscan-logs.onrender.com`

This repo itself is untouched and still has everything needed to redeploy both, on whatever
timeline works for you. Nothing here is urgent — the app still runs locally in the meantime
(`python -m backend.app` for the main app, `python -m apps.logsite.app` for the log site).

## Main app

Covered by the Blueprint already in this repo: `render.yaml`.

1. Connect your own Render account to this GitHub repo.
2. Render dashboard → **New → Blueprint** → select this repo/branch (`main`). It picks up
   `render.yaml` as-is — no changes needed.
3. Set the env vars it declares (Render will prompt for these since they're marked
   `sync: false`): `GEMINI_API_KEY`, `FLASK_SECRET_KEY`, `BLOCKED_DOMAINS`,
   `FIREBASE_SERVICE_ACCOUNT_PATH`, `SENTINELSCAN_TELEMETRY_ENABLED` (keep this at `"0"` unless
   you've verified the observability pipeline end-to-end — see `knowledge/DECISIONS.md`, 2026-08-30).

## Log site (`apps/logsite/`)

**Not covered by `render.yaml`** — the previous log site service was created by hand directly
in the Render dashboard rather than declared in the Blueprint, so a straight "reconnect" only
brings the main app back. You'll need to create a second Web Service yourself:

1. Render dashboard → **New → Web Service** → same repo, same `main` branch.
2. Build command: `pip install -r requirements.txt`
3. Start command: `gunicorn --workers 1 --bind 0.0.0.0:$PORT apps.logsite.app:app`
4. Health check path: `/healthz`
5. Env vars: `FIREBASE_SERVICE_ACCOUNT_PATH`, `LOGSITE_PROBE_TOKEN`, `MAIN_SITE_URL` (the main
   app's URL from the step above, once you have it).

Both services need `--workers 1` — active-scan/session state lives in-process, not in a shared
store, so a second worker would silently drop state. See `docs/ARCHITECTURE.md`.

## Getting actual secret values

`docs/SECRETS_SETUP.md` already documents the self-serve flow (`scripts/bootstrap_env.py`), but
it assumes an admin who can run `scripts/admin_seed_secrets.py` / `admin_add_developer.py` —
that was Shreyas. One of you should take over that role: run `admin_seed_secrets.py` from your
own populated `.env` once you've set the Render env vars above, so the rest of the team can keep
using the self-serve flow.

## Other loose ends once you have new URLs

- **Firebase console**: add both new Render URLs to the authorized-domains list (Google Sign-In
  will fail on an unlisted domain).
- **GitHub Actions**: `.github/workflows/uptime-probe.yml` reads `vars.MAIN_SITE_URL` /
  `vars.LOGSITE_URL` (repo → Settings → Secrets and variables → Actions → Variables) and
  `secrets.LOGSITE_PROBE_TOKEN`. Update all three to match your new deployment, or the probe
  will just report the old URLs as down.
- **Branch protection**: `main` currently requires PRs (0 required reviews, `enforce_admins`
  on — see `CLAUDE.md` §10 and `knowledge/DECISIONS.md`, 2026-08-20). That's yours to keep,
  loosen, or drop now that it's just the two of you.

No rush on any of this — reconnect whenever it's convenient for you.
