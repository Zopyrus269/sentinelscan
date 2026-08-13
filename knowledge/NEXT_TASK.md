---
type: knowledge-vault-core
last_updated: 2026-08-13
updated_by: claude-code
---

# Next Task

This file is always **overwritten**, not appended — it reflects the current handoff state only. Read this first in any new session, before analyzing code.

## What's next

**UI redesign workstream is in progress, on branch `feature/ui-redesign-reactbits`** (pushed to `origin/feature/ui-redesign-reactbits`, `main` untouched/deployable throughout). Plan: [[ui-redesign-reactbits]] (`knowledge/frontend-plans/ui-redesign-reactbits.md`).

- **Bootstrap is done.** `apps/frontend/react-app/` (Vite + React + Tailwind v4, preflight disabled, shadcn `init` with the `@react-bits` registry) is set up and building cleanly to `apps/frontend/static/react-dist/{main.js,main.css}`, which is wired into all 9 existing HTML pages.
- **Five pieces integrated and committed so far:**
  1. FloatingLines (`@react-bits/FloatingLines-JS-CSS`) — site-wide animated background, cursor-reactive. Commit `d71e70a`. Detail: [[2026-08-13]] (session 1).
  2. First-visit intro preloader (hand-built "double stairs" reveal, inspired by Skiper UI's paid `skiper10` component which this project has no license for) — text reveal → fade to black → 8-column staggered stairs uncover the site, once per tab via `sessionStorage`. Commit `9b60780`. Detail: [[2026-08-13]] (session 2).
  3. ShinyText (`@react-bits/ShinyText-JS-CSS`) — replaced the static blue "SentinelScan" header brand text on all 9 pages, font size/position unified across pages (fixed two pre-existing per-page design-token bugs along the way). Commit `869dd4c`.
  4. StaggeredMenu (`@react-bits/StaggeredMenu-JS-CSS`) — replaced the old header nav links + "New Scan" button with a site-wide slide-out menu wired to `/dashboard`, `/report`, `/documentation`; account icon repositioned to clear space for it. Commit `869dd4c`.
  5. Header/footer box removal — stripped the `bg-surface`/`bg-background` + border styling from `<header>`/`<footer>` on all 9 pages so `FloatingLines` shows through unbroken; removed a now-redundant `html.dark header, html.dark footer` override in `static/css/styles.css`. Commit `869dd4c`.
- **Session end state: everything is committed and pushed, nothing pending or broken.** The user ended the session with "a few more changes to be done" but did not specify what — the very first thing to do next session is ask what they want to work on. Do not assume or guess at a next component.
- **After that:** resume the plan's per-component workflow (`knowledge/frontend-plans/ui-redesign-reactbits.md`, "Per-component workflow" section) for whatever component/change the user shares next.
- **Patterns established across all sessions so far, expected to recur — don't re-litigate each time (but still flag+ask if a genuinely new situation comes up):**
  - If a new component is itself meant as a background/full-bleed element, its container pages likely need the same transparent-body treatment as FloatingLines got.
  - If a new component has pointer/hover/scroll interactivity and is used as a full-page backdrop, it likely needs the same real-event-forwarding bridge pattern in `main.jsx` (never modify shipped component files themselves for this).
  - If a new component needs to coexist with something else that must never be interrupted (e.g. another persistent background, a global timer, a site-wide nav overlay), mount it on its own independent `createRoot()` rather than as a sibling in a shared tree — this is now the established pattern for every site-wide mount (background, intro, nav menu all do this).
  - If a target component turns out to be paywalled/gated (checked by hitting its registry JSON endpoint directly, e.g. `curl` — a `401`/license-key error means it's paid), stop and ask the user how they want to proceed (buy license / hand-build a lookalike / pick a free alternative) rather than assuming.
  - **CSS conflicts between a shipped component and this site's existing global styles are now a recurring category of bug** (hit 3 more this session — flex-layout collapse from `display:none`, a sitewide `html.dark header/footer` rule painting over a component's internal `<header>` tag, a z-index conflict with the site's own sticky header). Root-cause with `getBoundingClientRect()`/`getComputedStyle()`/`elementFromPoint()` via `javascript_tool`, not by guessing from the visual symptom — "element not appearing on screen" has repeatedly turned out to mean "correctly rendered but covered/mispositioned," not "failed to render." Fix via scoped CSS overrides in the react-app's own `index.css` (using the component's `className` prop as the scope hook), never by editing shipped component files.
- **Known CLI gotcha (React Bits registry specifically):** `npx shadcn@latest add @react-bits/<name>` currently fails with `Unexpected token (1:0)` for react-bits registry items specifically (reproduced across CLI versions and across FloatingLines/ShinyText/StaggeredMenu; plain shadcn/ui components work fine, and this did NOT reproduce for the Skiper UI registry — that one failed differently, with an actual license-gate 401). **Workaround, now the default path — don't re-attempt the CLI first:** `curl`/fetch `https://reactbits.dev/r/<name>.json` directly (public, valid JSON) and place the files manually exactly as the CLI would, then `npm install` any listed `dependencies`.
- **Claude-in-Chrome automation quirks worth knowing for future frontend verification work:**
  - `requestAnimationFrame`-driven animations (framer-motion, raw rAF loops, etc.) throttle to near-zero when the automated tab is backgrounded/unfocused (`document.hidden === true`), which happens naturally between separate tool calls. A mid-animation screenshot taken this way can look "frozen" even though the code is correct. Workaround: click into the tab (`computer` `left_click`) immediately before checking, ideally in the same batched call.
  - **Screenshot pixel dimensions do not reliably match `window.innerWidth`/`innerHeight` call-to-call** (observed 1398/1425/1538/1568px-wide screenshots of the same actual browser window across consecutive calls in one session) — manually converting a `getBoundingClientRect()` value into zoom-region pixel coordinates by ratio is unreliable and wastes time. **Prefer `find` (element-reference-based) over manual pixel-coordinate math** when confirming a specific small element is present/clickable; `computer` actions against a `ref_N` are exact regardless of any screenshot/CSS-pixel scale mismatch.
  - Console-log instrumentation + `getComputedStyle`/`getBoundingClientRect` checks are more reliable than screenshot timing for verifying component *logic* (vs. purely visual polish).

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
- `node_modules/` at the repo root and `.agents/` remain untracked in git (pre-existing, not created by this workstream) — left alone across all sessions; revisit only if the user asks.
- The `.staggered-menu-panel`'s numbering/list styling (`sm-panel-item`, `sm-panel-itemLabel`) is used with shipped defaults (`displayItemNumbering` on, white panel background per the component's own CSS) — not yet asked whether the user wants this reskinned to match the site's dark theme instead of the component's own light panel. Flag if they mention it looking inconsistent.

## Links

- Latest daily log: [[2026-08-13]] (session 1: React Bits islands bootstrap + FloatingLines background; session 2: first-visit intro preloader with double-stairs reveal; session 3: ShinyText header brand, StaggeredMenu nav, header/footer box removal)
- Previous daily log: [[2026-08-09]] (Pass 4: deployment prep and code; Pass 5: live rollout and full verification; Pass 6: hygiene cleanup)
- `scripts/README.md` — team secrets bootstrap setup/usage instructions.
- `render.yaml` — Render deployment Blueprint (repo root).
- Live site: `https://sentinelscan-yd2u.onrender.com`
- Render service: `srv-d9rrj6n40ujc73c4efcg`
- Active frontend workstream: [[ui-redesign-reactbits]] (`knowledge/frontend-plans/ui-redesign-reactbits.md`) — approved 2026-08-11, bootstrap + FloatingLines done 2026-08-13 (session 1), intro preloader done 2026-08-13 (session 2), ShinyText brand + StaggeredMenu nav + header/footer box removal done 2026-08-13 (session 3), in progress on `feature/ui-redesign-reactbits`.
