---
type: knowledge-vault-core
last_updated: 2026-08-09
updated_by: claude-code
---

# Next Task

This file is always **overwritten**, not appended — it reflects the current handoff state only. Read this first in any new session, before analyzing code.

## What's next

Three things are now done, verified, and committed (see [[2026-08-09]] for full detail):
1. Synced local `main` with upstream (4 commits it had missed).
2. Fixed the first round of user-reported bugs (dark-mode CSS, Gemini 401, dead footer links).
3. Built and fully verified the team secrets bootstrap system — teammates can now run `python scripts/bootstrap_env.py` to fetch shared dev secrets from Firestore instead of manually re-typing them, gated to allowlisted developers via their own Google Sign-In (no shared password, reuses the site's existing auth). See `scripts/README.md` for the full setup/usage flow.

**Only remaining deferred item: Deployment.** User wants a free hosting platform with auto-deploy on `git push` to `main`, so the team can add features/fix bugs while the site stays live. Not yet scoped in detail. Candidates identified but not evaluated in depth: Render or Railway (both support GitHub auto-deploy on a free tier). Needs its own plan once started — this is a new feature/infra change, so enter plan mode first per `CLAUDE.md` §6. Things that plan will need to cover:
- Build/start commands for a Flask app that also serves static frontend files.
- Env var provisioning on the host — decide whether to wire in the new secrets-bootstrap system (item 3 above) so the deployed server pulls its own secrets from Firestore at boot, vs. just setting them manually in the host's dashboard once. The bootstrap system's `bootstrap_env.py` script only really becomes useful for *teammates* once a live URL exists to point `--server-url` at, so deployment and item 3 are linked.
- Whether SQLite (`DATABASE_URL=sqlite:///...`) persistence survives redeploys on the chosen host, or whether a hosted Postgres is needed (see `docs/ARCHITECTURE.md`'s note that SQLite was always intended to be swappable).
- Secrets handling for `secrets/firebase-service-account.json` — this is the one credential that can't come from the bootstrap system itself (it's what makes the bootstrap system work), so it needs to be set directly as a host secret/env var.
- **Whatever origin the deployed site ends up on must be added to Firebase's authorized domains list**, or Google Sign-In (both normal site login and the bootstrap OAuth exchange) will break there — see the standing constraint below.
- A production-appropriate OAuth client may be needed alongside (or instead of) the current Desktop-app one used for local bootstrap testing, if the deployed environment changes how teammates would run the bootstrap script (e.g. still locally, pointed at the prod URL — Desktop app flow still works fine for that case, likely no change needed, but worth double-checking during deployment planning).

## Standing rules for this engagement (apply to all future sessions, not just this one)

- **Never spawn a subagent without asking the user first and stating the reason.**
- **Never write to `knowledge/` while implementation work is in progress** — read-only during active work; writes only after everything for that unit of work is implemented, tested, and committed.
- **All frontend work (HTML/CSS/JS under `apps/frontend/`) is delegated to Gemini 3.1 Pro** via an in-chat prompt (not a `knowledge/frontend-plans/` handoff file) — write a self-contained prompt, output it in chat, wait for the user's heads-up, then review and integrate.
- **Always run the local dev server as `http://localhost:5000`.** Firebase's authorized-domains whitelist for this project only covers `localhost` — a different host/port breaks Google Sign-In popups (both normal site login and the secrets-bootstrap OAuth exchange) unless that origin is deliberately added to Firebase first.
- **When creating any new Google Cloud OAuth client for this project, verify the project selector shows `sentinelscan-3f82d` (project number `60214574079`) before creating it.** GCP will silently let you create credentials in an unrelated project, and Firebase will reject tokens from the wrong one with `INVALID_IDP_RESPONSE` — this happened once already during the bootstrap system's setup, see [[2026-08-09]].
- **Restart the Flask dev server after any `.env` change** — `load_dotenv()` only runs at process startup, there's no hot-reload for env files.

## Blockers

None. Deployment is waiting on the user to start that conversation, not on any technical blocker.

## Other findings (not yet acted on, flagged for awareness)

- `.agents/skills/ui-ux-pro-max/` — a design-guidance skill the user installed locally, used successfully for the dark-mode fix. Still untracked in git; still not decided whether to commit it for teammates to use too. Ask before adding it.
- Carried over from 2026-08-07, still untouched: `headless_auth_test.py` hardcoded test JWT, empty untracked `LICENSE.md`, README's stale test-count claim.
- `config/secrets` in Firestore currently only has `GEMINI_API_KEY` and `DATABASE_URL` — `FLASK_SECRET_KEY` and `BLOCKED_DOMAINS` aren't set in the admin's local `.env` so they were skipped during seeding. Not blocking anything today (the app falls back to a dev default for `FLASK_SECRET_KEY`), but worth setting properly before deployment — a production deployment should not run on the `"dev-secret-key"` fallback.

## Links

- Latest daily log: [[2026-08-09]]
- Previous daily log: [[2026-08-07]]
- `scripts/README.md` — team secrets bootstrap setup/usage instructions.
- Open frontend handoff plans: none (in-chat Gemini-prompt workflow used instead).
