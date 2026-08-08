---
type: knowledge-vault-core
last_updated: 2026-08-09
updated_by: claude-code
---

# Next Task

This file is always **overwritten**, not appended — it reflects the current handoff state only. Read this first in any new session, before analyzing code.

## What's next

**Deployment is done.** SentinelScan is live at `https://sentinelscan-yd2u.onrender.com`, on Render's free tier, auto-deploying on every push to `main`. Fully verified end-to-end by the user: Google Sign-In on the new domain, a complete live scan with PDF/JSON report generation, auto-deploy firing on a real push with no manual dashboard step, and `scripts/bootstrap_env.py` run for real against the live URL (existing Desktop OAuth client, no new/production client needed). See [[2026-08-09]] Pass 4 (prep) and Pass 5 (live rollout + verification) for full detail.

**No forced next task.** This was the last item from this engagement's original scope. Remaining items below are flagged/optional, not blocking anything.

## Standing rules for this engagement (apply to all future sessions, not just this one)

- **Never spawn a subagent without asking the user first and stating the reason.**
- **Never write to `knowledge/` while implementation work is in progress** — read-only during active work; writes only after everything for that unit of work is implemented, tested, and committed.
- **All frontend work (HTML/CSS/JS under `apps/frontend/`) is delegated to Gemini 3.1 Pro** via an in-chat prompt (not a `knowledge/frontend-plans/` handoff file) — write a self-contained prompt, output it in chat, wait for the user's heads-up, then review and integrate.
- **Always run the local dev server as `http://localhost:5000`.** Firebase's authorized-domains list now covers both `localhost` and `sentinelscan-yd2u.onrender.com` — a different host/port than either still breaks Google Sign-In popups (both normal site login and the secrets-bootstrap OAuth exchange) unless deliberately added to Firebase first.
- **When creating any new Google Cloud OAuth client for this project, verify the project selector shows `sentinelscan-3f82d` (project number `60214574079`) before creating it.** GCP will silently let you create credentials in an unrelated project, and Firebase will reject tokens from the wrong one with `INVALID_IDP_RESPONSE` — this happened once already during the bootstrap system's setup, see [[2026-08-09]].
- **Restart the Flask dev server after any `.env` change** — `load_dotenv()` only runs at process startup, there's no hot-reload for env files.
- **Never commit `scripts/oauth_client.json`** (or any real secret-shaped file) even if it seems technically non-confidential — GitHub's push protection flags it categorically regardless, and it was already designed for out-of-band admin distribution, not git. Now `.gitignore`'d. See [[2026-08-09]] Pass 4 for the full incident (committed once, caught before reaching `origin`, rebased out).
- **Render deploys must run a single gunicorn worker** (`--workers 1`, already set in `render.yaml`) — `scan_store.py`'s active-scan state is an in-memory per-process dict; more than one worker breaks scan-progress polling. Don't "optimize" this without first moving scan state to Firestore or another shared store.
- **Render Secret Files gotcha, if this ever needs redoing:** paste the *exact* file content fresh (delete-and-recreate rather than edit-in-place) — a stale/duplicated entry produced a "missing 'type' field" error from `firebase_admin` even though the JSON parsed. `Get-Content <path> -Raw | Set-Clipboard` in PowerShell is the reliable way to get exact contents onto the clipboard (use an absolute path, not relative to whatever directory the terminal happens to be in).

## Note: secrets bootstrap is not automatic on `git pull`, and is a developer-laptop tool only

A teammate must manually run `python scripts/bootstrap_env.py` after pulling — there is no `post-merge` git hook wired up yet to trigger it automatically. It cannot and does not run on the deployed server itself — the installed-app OAuth flow opens a local browser, which has no headless/server equivalent — so the deployed server's own secrets were set directly in Render's dashboard (Environment tab + Secret Files), not fetched via this tool. Teammates can point it at the live URL: `python scripts/bootstrap_env.py --server-url https://sentinelscan-yd2u.onrender.com` — confirmed working. If the user asks for pull-triggered automation later, add a `post-merge` hook following the same pattern as the existing `.claude/hooks/post_commit_vault_reminder.py`.

## Architectural finding not yet folded into static docs

`docs/ARCHITECTURE.md` and `.env.example` describe SQLite-backed scan storage; the actual code does not use SQLite for scan data at all — `apps/backend/models/scan_store.py` is in-memory (active scans, per-process), `apps/backend/models/history_store.py` writes completed scans to Firestore. `DATABASE_URL` is dead config, not read anywhere except `scripts/admin_seed_secrets.py` (which just copies `.env` values into Firestore, doesn't open a DB connection with it) — it's still deliberately **not** set on Render for this reason. Worth a `docs/ARCHITECTURE.md` correction at some point; out of scope this session.

## Blockers

None.

## Other findings (not yet acted on, flagged for awareness)

- `.agents/skills/ui-ux-pro-max/` — a design-guidance skill the user installed locally, used successfully for the dark-mode fix. Still untracked in git; still not decided whether to commit it for teammates to use too. Ask before adding it.
- Carried over from 2026-08-07, still untouched: `headless_auth_test.py` hardcoded test JWT, empty untracked `LICENSE.md`, README's stale test-count claim.
- `config/secrets` in Firestore (the teammate-bootstrap doc, separate from Render's own directly-set env vars) currently only has `GEMINI_API_KEY` and `DATABASE_URL` — `FLASK_SECRET_KEY` and `BLOCKED_DOMAINS` aren't set there since the admin's local `.env` didn't have them at seed time. Doesn't block anything (Render has its own correct values set directly), but worth completing for teammate-bootstrap parity at some point.
- `docs/ARCHITECTURE.md` SQLite description is stale — see "Architectural finding" above.
- Render free-tier spin-down (~15 min idle → ~1 min cold start on next request) is expected behavior, not a bug, if a first request after idle time feels slow.

## Links

- Latest daily log: [[2026-08-09]] (Pass 4: deployment prep and code; Pass 5: live rollout and full verification)
- Previous daily log: [[2026-08-07]]
- `scripts/README.md` — team secrets bootstrap setup/usage instructions.
- `render.yaml` — Render deployment Blueprint (repo root).
- Live site: `https://sentinelscan-yd2u.onrender.com`
- Render service: `srv-d9rrj6n40ujc73c4efcg`
- Open frontend handoff plans: none (in-chat Gemini-prompt workflow used instead).
