---
type: knowledge-vault-core
last_updated: 2026-08-09
updated_by: claude-code
---

# Next Task

This file is always **overwritten**, not appended — it reflects the current handoff state only. Read this first in any new session, before analyzing code.

## What's next

The `origin/main` sync and the 3 bugs found during the user's first round of manual testing (dark-mode borders, Gemini 401, dead footer links) are all fixed, verified, and committed. See [[2026-08-09]] for full detail. The app is running locally on `localhost:5000` and was confirmed working by the user.

Two explicitly deferred items, in the order the user is expected to want them (confirm before starting either):

1. **Team secrets bootstrap system.** The user asked for teammates to automatically get the correct shared API keys/secrets after pulling `main`, instead of manually re-entering them, and for production secrets to live server-side (not in the public repo). Design already scoped and approved in spirit but explicitly put on hold by the user pending this round's verification (now done) — needs an explicit "go" before building:
   - New Firestore doc `config/secrets` (shared dev values), new `developers/{uid}` allowlist collection, a `require_developer` decorator layered on the existing `require_auth` (`apps/backend/auth/auth_utils.py`), a new protected endpoint (`GET /api/v1/dev/bootstrap-secrets`), and a `scripts/bootstrap_env.py` a teammate runs to fetch and write their local `.env`.
   - Deliberately reuses the existing Firebase Admin SDK / `require_auth` pattern already in the codebase rather than inventing a new auth mechanism.
   - Fully useful only once the app is deployed (the bootstrap script calls a live backend URL) — ties directly into item 2.
2. **Deployment.** User wants a free hosting platform with auto-deploy on `git push` to `main`, so the team can add features/fix bugs while the site stays live. Candidates identified but not yet scoped in detail: Render or Railway (both support GitHub auto-deploy on a free tier). Needs its own plan once started: build/start commands, env var provisioning (or wiring in item 1's bootstrap instead of manual dashboard env vars), whether SQLite persistence survives redeploys, secrets handling for the Firebase service account.

## Standing rules for this engagement (apply to all future sessions, not just this one)

- **Never spawn a subagent without asking the user first and stating the reason** — overrides the general cost-aware sub-agent policy in `CLAUDE.md` §8; approval must come first regardless of task size.
- **Never write to `knowledge/` while implementation work is in progress** — read-only during active work; writes (this file, daily-logs, ARCHITECTURE.md deltas) only happen after everything for that unit of work is implemented, tested, and committed.
- **All frontend work (HTML/CSS/JS under `apps/frontend/`) is delegated to Gemini 3.1 Pro**, not implemented directly — write a self-contained prompt, output it in chat for the user to run through Gemini (which has folder access), wait for their heads-up, then review and integrate the diff before continuing. This supersedes the `CLAUDE.md` §7 "write a plan file to `knowledge/frontend-plans/`" workflow for this engagement — the user wants the actual prompt pasted in chat, not a handoff file.

## Blockers

None currently. Both deferred items above are waiting on the user's go-ahead, not on any technical blocker.

## Other findings (not yet acted on, flagged for awareness)

- `.agents/skills/ui-ux-pro-max/` — a design-guidance skill the user installed locally, used successfully for the dark-mode fix. Currently untracked in git; not yet decided whether it should be committed to the repo for teammates to use too, or is a personal local tool. Ask before adding it.
- Carried over from 2026-08-07, still untouched: `headless_auth_test.py` hardcoded test JWT, empty untracked `LICENSE.md`, README's stale "123 tests" claim (actual count keeps shifting as tests are added upstream — don't trust the README number, run `pytest` for the real one).

## Links

- Latest daily log: [[2026-08-09]]
- Previous daily log: [[2026-08-07]]
- Open frontend handoff plans: none (this engagement uses the in-chat Gemini-prompt workflow instead, see standing rules above).
