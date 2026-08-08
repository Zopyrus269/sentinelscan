---
type: knowledge-vault-core
last_updated: 2026-08-09
updated_by: claude-code
---

# Next Task

This file is always **overwritten**, not appended — it reflects the current handoff state only. Read this first in any new session, before analyzing code.

## What's next

**Deployment is in progress, code side done, manual dashboard steps remain.** See [[2026-08-09]] Pass 4 for full detail.

Done, tested, committed locally as `009c388` (not yet pushed):
- `gunicorn` added to `requirements.txt`.
- `render.yaml` Blueprint added (Render host, chosen over Railway — Railway is no longer meaningfully free as of this check; see Pass 4 for the comparison). Single worker only (`--workers 1`) — required, not optional: `apps/backend/models/scan_store.py` is an in-memory per-process dict for active scans, so more than one worker breaks progress polling.
- Verified locally: app object imports cleanly, serves correctly under `waitress` (gunicorn itself can't run on this Windows dev machine — POSIX-only, no `fcntl`), full `pytest tests/` still 137 passed/1 skipped.

Remaining steps (in order — see `knowledge/daily-logs/2026-08-09.md` Pass 4 "Manual provisioning steps" for the full checklist):
1. Push commit `009c388` to `origin/main` (paused here — ask the user first, this is a shared/visible action).
2. Render dashboard: new Web Service, connect the GitHub repo, branch `main` (Render will detect `render.yaml`).
3. Set secrets in Render's Environment tab: `GEMINI_API_KEY` (existing working key), `FLASK_SECRET_KEY` (generate a **fresh** production value — do not reuse the dev one), `BLOCKED_DOMAINS`. Do **not** set `DATABASE_URL` — confirmed dead/unused config (see below).
4. Upload `secrets/firebase-service-account.json` via Render's Secret Files UI; set `FIREBASE_SERVICE_ACCOUNT_PATH=/etc/secrets/firebase-service-account.json`.
5. First deploy, get the `https://<service>.onrender.com` URL.
6. Add that URL to Firebase Console → Authentication → Settings → Authorized domains (standing constraint below still applies — without this, Google Sign-In breaks on the new domain).
7. End-to-end verification: `/health`, a full live scan through the UI, Google Sign-In on the new domain, and a teammate running `bootstrap_env.py --server-url https://<service>.onrender.com` to confirm the bootstrap flow still works pointed at prod.
8. Push a trivial follow-up commit to confirm Render's auto-deploy-on-push actually fires.

## Architectural finding not yet folded into static docs

`docs/ARCHITECTURE.md` and `.env.example` describe SQLite-backed scan storage; the actual code does not use SQLite for scan data at all — `scan_store.py` is in-memory (active scans, per-process), `history_store.py` writes completed scans to Firestore. `DATABASE_URL` is dead config, read nowhere except `scripts/admin_seed_secrets.py` (which just copies `.env` values into Firestore, doesn't open a DB connection with it). Worth a doc correction at some point; not done this session, out of scope for the deployment task.

## Standing rules for this engagement (apply to all future sessions, not just this one)

- **Never spawn a subagent without asking the user first and stating the reason.**
- **Never write to `knowledge/` while implementation work is in progress** — read-only during active work; writes only after everything for that unit of work is implemented, tested, and committed.
- **All frontend work (HTML/CSS/JS under `apps/frontend/`) is delegated to Gemini 3.1 Pro** via an in-chat prompt (not a `knowledge/frontend-plans/` handoff file) — write a self-contained prompt, output it in chat, wait for the user's heads-up, then review and integrate.
- **Always run the local dev server as `http://localhost:5000`.** Firebase's authorized-domains whitelist for this project only covers `localhost` (and, pending step 6 above, the new Render domain) — a different host/port breaks Google Sign-In popups (both normal site login and the secrets-bootstrap OAuth exchange) unless that origin is deliberately added to Firebase first.
- **When creating any new Google Cloud OAuth client for this project, verify the project selector shows `sentinelscan-3f82d` (project number `60214574079`) before creating it.** GCP will silently let you create credentials in an unrelated project, and Firebase will reject tokens from the wrong one with `INVALID_IDP_RESPONSE` — this happened once already during the bootstrap system's setup, see [[2026-08-09]].
- **Restart the Flask dev server after any `.env` change** — `load_dotenv()` only runs at process startup, there's no hot-reload for env files.
- **Never commit `scripts/oauth_client.json`** (or any real secret-shaped file) even if it seems technically non-confidential — GitHub's push protection flags it categorically regardless, and it was already designed for out-of-band admin distribution, not git. Now `.gitignore`'d. See [[2026-08-09]] Pass 4 for the full incident (it was committed once, caught before reaching `origin`, and rebased out).

## Note: secrets bootstrap is not automatic on `git pull`, and is a developer-laptop tool only

A teammate must manually run `python scripts/bootstrap_env.py` after pulling — there is no `post-merge` git hook wired up yet to trigger it automatically. It also cannot run on the deployed server itself — the installed-app OAuth flow opens a local browser, which has no headless/server equivalent — so the deployed server's own secrets are set directly in Render's dashboard (steps 3–4 above), not fetched via this tool. If the user asks for pull-triggered automation later, add a `post-merge` hook following the same pattern as the existing `.claude/hooks/post_commit_vault_reminder.py`.

## Blockers

None technical. Push to `origin/main` (step 1) needs the user's go-ahead before I do it, since it's a shared/visible action. The Render dashboard steps (2–7) need the user directly — I don't have Render or Firebase Console access.

## Other findings (not yet acted on, flagged for awareness)

- `.agents/skills/ui-ux-pro-max/` — a design-guidance skill the user installed locally, used successfully for the dark-mode fix. Still untracked in git; still not decided whether to commit it for teammates to use too. Ask before adding it.
- Carried over from 2026-08-07, still untouched: `headless_auth_test.py` hardcoded test JWT, empty untracked `LICENSE.md`, README's stale test-count claim.
- `config/secrets` in Firestore currently only has `GEMINI_API_KEY` and `DATABASE_URL` — `FLASK_SECRET_KEY` and `BLOCKED_DOMAINS` aren't set in the admin's local `.env` so they were skipped during seeding. Not blocking Render deployment (that gets its own directly-set `FLASK_SECRET_KEY`, see step 3), but worth setting properly in the teammate-bootstrap Firestore doc too at some point.
- `docs/ARCHITECTURE.md` SQLite description is stale — see "Architectural finding not yet folded into static docs" above.

## Links

- Latest daily log: [[2026-08-09]] (Pass 4 has the full deployment-prep detail)
- Previous daily log: [[2026-08-07]]
- `scripts/README.md` — team secrets bootstrap setup/usage instructions.
- `render.yaml` — Render deployment Blueprint (repo root).
- Open frontend handoff plans: none (in-chat Gemini-prompt workflow used instead).
