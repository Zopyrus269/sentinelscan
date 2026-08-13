---
type: knowledge-vault-core
last_updated: 2026-08-13
updated_by: claude-code
---

# Next Task

This file is always **overwritten**, not appended — it reflects the current handoff state only. Read this first in any new session, before analyzing code.

## What's next

**UI redesign workstream is in progress, on branch `feature/ui-redesign-reactbits`** (pushed to `origin/feature/ui-redesign-reactbits`, `main` untouched/deployable throughout). Plan: [[ui-redesign-reactbits]] (`knowledge/frontend-plans/ui-redesign-reactbits.md`).

- **Bootstrap is done.** `apps/frontend/react-app/` (Vite + React + Tailwind v4, preflight disabled, shadcn `init` with the `@react-bits` registry) is set up and building cleanly to `apps/frontend/static/react-dist/{main.js,main.css}`, which is wired into all 9 existing HTML pages via one `<link>`/`<script>` pair each.
- **First component integrated and committed:** FloatingLines (`@react-bits/FloatingLines-JS-CSS`) as a site-wide animated background, cursor-reactive (bend + parallax), on every page. Commit `d71e70a`. Full detail, including two non-obvious bugs fixed (shadcn CLI resolution failure, cursor events not reaching a `z-index:-1` background canvas) and two deliberate deviations from "component as shipped" (transparent body/footer backgrounds so it's actually visible; a `main.jsx`-level event bridge for interactivity) — see [[2026-08-13]].
- **Immediate next step, session start:** the user has not yet done their own manual visual/interactive review of FloatingLines in-browser — that's what this session ended on. Start the local dev server (`http://localhost:5000` — see standing rule below) and let them look before doing anything else.
- **After that:** resume the plan's per-component workflow (`knowledge/frontend-plans/ui-redesign-reactbits.md`, "Per-component workflow" section) for whatever component the user shares next from reactbits.dev. Two patterns established last session are expected to recur and don't need re-litigating each time (though still flag+ask if a genuinely new situation comes up): (a) if the new component is itself meant as a background/full-bleed element, its container page backgrounds likely need the same transparent-body treatment; (b) if the new component has pointer/hover/scroll interactivity, it likely needs the same real-event-forwarding bridge pattern in `main.jsx` (never modify the shipped component files themselves to add this — bridge lives in our own mounting code).
- **Known CLI gotcha:** `npx shadcn@latest add @react-bits/<name>` currently fails with `Unexpected token (1:0)` for react-bits registry items specifically (reproduced across CLI versions; plain shadcn/ui components work fine). Workaround: `curl`/fetch `https://reactbits.dev/r/<name>.json` directly (public, valid JSON) and place the files manually exactly as the CLI would, then `npm install` any listed `dependencies`. Don't re-attempt the CLI blind — check with `--dry-run` first if retrying it.

**Note:** this plan temporarily suspends the "frontend work goes to Gemini" standing rule below, for this workstream only — see that bullet.

**One loose end from Pass 6 (2026-08-09), still unresolved:** `CLAUDE.md` §9 still lists hygiene items — check whether it's stale before next `CLAUDE.md` edit (it may have been trimmed already; verify against actual `CLAUDE.md` content rather than trusting this note).

## Standing rules for this engagement (apply to all future sessions, not just this one)

- **Never spawn a subagent without asking the user first and stating the reason.** Applies to planning and implementation alike, including a project workflow (e.g. plan-mode's default Explore/Plan agent steps) that would otherwise auto-spawn one — ask first regardless. Now also codified globally in `C:\Users\ADMIN\.claude\CLAUDE.md` ("Subagent usage restrictions"), not just for this project.
- **Never write to `knowledge/` while implementation work is in progress** — read-only during active work; writes only after everything for that unit of work is implemented, tested, and committed.
- **All frontend work (HTML/CSS/JS under `apps/frontend/`) is delegated to Gemini 3.1 Pro** via an in-chat prompt (not a `knowledge/frontend-plans/` handoff file) — write a self-contained prompt, output it in chat, wait for the user's heads-up, then review and integrate. **TEMPORARILY SUSPENDED as of 2026-08-11 for the React Bits UI redesign workstream only** — see [[ui-redesign-reactbits]]; Claude Code implements that workstream's frontend directly instead. Resumes (for that workstream too) whenever the user says so; do not assume it's suspended for any other frontend work.
- **Always run the local dev server as `http://localhost:5000`.** Firebase's authorized-domains list now covers both `localhost` and `sentinelscan-yd2u.onrender.com` — a different host/port than either still breaks Google Sign-In popups (both normal site login and the secrets-bootstrap OAuth exchange) unless deliberately added to Firebase first. Start it with `python -m apps.backend.app` (must run as a module from the repo root — `python apps/backend/app.py` directly fails with `ModuleNotFoundError: No module named 'apps'`).
- **When creating any new Google Cloud OAuth client for this project, verify the project selector shows `sentinelscan-3f82d` (project number `60214574079`) before creating it.** GCP will silently let you create credentials in an unrelated project, and Firebase will reject tokens from the wrong one with `INVALID_IDP_RESPONSE` — this happened once already during the bootstrap system's setup, see [[2026-08-09]].
- **Restart the Flask dev server after any `.env` change** — `load_dotenv()` only runs at process startup, there's no hot-reload for env files.
- **Never commit `scripts/oauth_client.json`** (or any real secret-shaped file) even if it seems technically non-confidential — GitHub's push protection flags it categorically regardless, and it was already designed for out-of-band admin distribution, not git. Now `.gitignore`'d. See [[2026-08-09]] Pass 4 for the full incident (committed once, caught before reaching `origin`, rebased out).
- **Render deploys must run a single gunicorn worker** (`--workers 1`, already set in `render.yaml`) — `scan_store.py`'s active-scan state is an in-memory per-process dict; more than one worker breaks scan-progress polling. Don't "optimize" this without first moving scan state to Firestore or another shared store.
- **Render Secret Files gotcha, if this ever needs redoing:** paste the *exact* file content fresh (delete-and-recreate rather than edit-in-place) — a stale/duplicated entry produced a "missing 'type' field" error from `firebase_admin` even though the JSON parsed. `Get-Content <path> -Raw | Set-Clipboard` in PowerShell is the reliable way to get exact contents onto the clipboard (use an absolute path, not relative to whatever directory the terminal happens to be in).
- **`DATABASE_URL`/SQLite is confirmed dead config, fully removed from docs/scripts as of Pass 6** (`docs/ARCHITECTURE.md`, `.env.example`, `scripts/README.md`, `admin_seed_secrets.py`'s `SHARED_SECRET_KEYS`). Don't reintroduce it without an actual SQLite integration to back it.
- **Never hardcode a real token/JWT/secret-shaped literal in a committed file**, even in a skipped test — `headless_auth_test.py` did this once (Pass 6 fix: now reads `HEADLESS_TEST_TOKEN` from the environment instead).

## Note: secrets bootstrap is not automatic on `git pull`, and is a developer-laptop tool only

A teammate must manually run `python scripts/bootstrap_env.py` after pulling — there is no `post-merge` git hook wired up yet to trigger it automatically. It cannot and does not run on the deployed server itself — the installed-app OAuth flow opens a local browser, which has no headless/server equivalent — so the deployed server's own secrets were set directly in Render's dashboard (Environment tab + Secret Files), not fetched via this tool. Teammates can point it at the live URL: `python scripts/bootstrap_env.py --server-url https://sentinelscan-yd2u.onrender.com` — confirmed working. `config/secrets` in Firestore now has all three current keys (`GEMINI_API_KEY`, `FLASK_SECRET_KEY`, `BLOCKED_DOMAINS`) as of Pass 6 — teammate-bootstrap parity is complete, no more missing keys. If the user asks for pull-triggered automation later, add a `post-merge` hook following the same pattern as the existing `.claude/hooks/post_commit_vault_reminder.py`.

## Blockers

None.

## Other findings (not yet acted on, flagged for awareness)

- `.agents/skills/ui-ux-pro-max/` — a design-guidance skill the user installed locally, used successfully for the dark-mode fix. Still untracked in git; still not decided whether to commit it for teammates to use too. Ask before adding it.
- `CLAUDE.md` §9 "Known Hygiene Notes" may be stale again — verify against current content before next edit rather than trusting older notes about it.
- Render free-tier spin-down (~15 min idle → ~1 min cold start on next request) is expected behavior, not a bug, if a first request after idle time feels slow.
- `apps/frontend/react-app/src/components/ui/button.jsx` is an unused default from `shadcn init` (no page mounts it) — harmless, low-priority cleanup candidate whenever the workstream wraps up.

## Links

- Latest daily log: [[2026-08-13]] (React Bits islands bootstrap + first component, FloatingLines, integrated as site-wide interactive background)
- Previous daily log: [[2026-08-09]] (Pass 4: deployment prep and code; Pass 5: live rollout and full verification; Pass 6: hygiene cleanup)
- `scripts/README.md` — team secrets bootstrap setup/usage instructions.
- `render.yaml` — Render deployment Blueprint (repo root).
- Live site: `https://sentinelscan-yd2u.onrender.com`
- Render service: `srv-d9rrj6n40ujc73c4efcg`
- Active frontend workstream: [[ui-redesign-reactbits]] (`knowledge/frontend-plans/ui-redesign-reactbits.md`) — approved 2026-08-11, bootstrap + first component done 2026-08-13, in progress on `feature/ui-redesign-reactbits`.
