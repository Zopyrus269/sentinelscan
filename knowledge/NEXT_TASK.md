---
type: knowledge-vault-core
last_updated: 2026-08-14
updated_by: claude-code
---

# Next Task

This file is always **overwritten**, not appended -- it reflects the current handoff state only. Read this first in any new session, before analyzing code.

## What's next

**UI redesign workstream is in progress, on branch `feature/ui-redesign-reactbits`** (pushed to `origin/feature/ui-redesign-reactbits`, `main` untouched/deployable throughout). Plan: [[ui-redesign-reactbits]] (`knowledge/frontend-plans/ui-redesign-reactbits.md`).

**Session end state (2026-08-14, session 8): everything is committed and pushed, nothing pending or broken.** Ask what the user wants to work on next -- do not assume or guess at a next component.

- **Session 8 summary (full detail in [[2026-08-14]] "Session 8"):**
  1. Fixed a backend bug where `scan_routes.py`'s `on_progress()` never forwarded `summary` to `add_scan_event()`, so the dashboard terminal showed "no summary provided" for every worker on every scan. One-line fix. Commit `fc1c107`.
  2. Dashboard header/footer now match the hero page exactly (header markup, spacing, footer markup all identical). Note: a mid-task spacing change was tried and reverted at the user's request -- both pages currently sit at `mr-16 md:mr-20` for the profile-button wrapper, unchanged from before this session started.
  3. Dashboard's header and the site-wide nav-menu toggle now scroll away with the page (no longer sticky/fixed) -- scoped to the dashboard only via a `.ss-dashboard-page` body class + CSS override; every other page keeps the fixed toggle.
  4. Consolidated all dashboard edge-case UI (no scan ID, invalid/nonexistent scan_id, FAILED-scan error, fetch/backend failure) into one `SpecularButton`-driven notice (`#sentinelscan-dashboard-notice`, driven by a new `sentinelscan:dashboard-notice` CustomEvent bridge from `dashboard.js`), replacing the old separate plain-error-box + no-scan-notice.
  5. Removed the "Authorization Required" consent modal from the landing page entirely -- submitting a target now goes straight to `/api/v1/scans` then `/dashboard`. **Flagged to the user, not blocked on it:** this was the only UI step where a user affirmatively confirmed scan authorization; nothing server-side enforced it either, so nothing backend needed removing, but there is now no authorization-confirmation step anywhere in the flow.
  6. `ScanTerminal` no longer dumps output instantly -- lines are queued and typed word-by-word (currently 90ms/word) via a softened variant of the home page's caret spring (`placeholders-and-vanish-input.jsx` now exports `CARET_SPRING` for reuse). Auto-scroll now respects manual scroll-up (pinned-to-bottom tracking) and snaps `scrollTop` directly instead of stacking `scrollIntoView({behavior:'smooth'})` calls, which was the actual cause of a reported "rough/clicky" feel.
  - Commits: `fc1c107` (backend), `05ac225` (all frontend work, bundled in one commit -- see commit message for the itemized breakdown; not split further since the session's changes touched the same files repeatedly across several sequential asks).
- **After that:** resume the plan's per-component workflow (`knowledge/frontend-plans/ui-redesign-reactbits.md`, "Per-component workflow" section) for whatever component/change the user shares next.
- **Patterns established across all sessions so far, expected to recur -- don't re-litigate each time (but still flag+ask if a genuinely new situation comes up):**
  - If a new component is itself meant as a background/full-bleed element, its container pages likely need the same transparent-body treatment as FloatingLines got.
  - If a new component has pointer/hover/scroll interactivity and is used as a full-page backdrop, check first whether it listens on `window`/`document` directly (no bridge needed) or on its own element (needs a `dispatchEvent`/CustomEvent bridge in `main.jsx` -- established pattern now used for `sentinelscan:scan-update` feeding ScanTerminal and `sentinelscan:dashboard-notice` feeding DashboardNotice, both driven from the plain-script `dashboard.js` since it isn't an ES module).
  - If a new component needs to coexist with something else that must never be interrupted, mount it on its own independent `createRoot()` rather than as a sibling in a shared tree.
  - If a target component turns out to be paywalled/gated, stop and flag it to the user rather than assuming.
  - If a page-specific behavior is needed for a component that's mounted site-wide (e.g. StaggeredMenu), don't fork the component -- add a body class scoped to that page (`.ss-dashboard-page`, `.ss-menu-open`) and a scoped CSS override keyed off it. Established twice now (session 7's footer-menu fix, session 8's dashboard fixed-toggle opt-out).
  - **When a user gives two sequential-but-related asks in close succession ("push X closer" then, separately, "actually copy Y's exact spacing to Z"), don't conflate them into one inferred value** -- treat "copy the exact spacing" as literally copy the existing value, not a blend with an earlier looser request. Session 8 hit a revert-and-redo cycle over exactly this (the `mr-16 md:mr-20` back-and-forth) -- when unsure whether a new instruction supersedes or composes with the previous one, the literal/precise reading of "copy X exactly" wins.
  - **When a "reuse this animation/spring from page A" request doesn't visually work when applied literally to page B's different use case (e.g. a caret-snap spring applied to whole-word reveals reading as "clicky"), it's fine to keep the same spring *family*/feel but retune the actual stiffness/damping for the new context** -- flag that it's a tuned variant, not the literal same constant, so it doesn't look like a deviation from the instruction. Session 8, `WORD_REVEAL_SPRING` vs `CARET_SPRING`.
  - **Repeated `scrollIntoView({behavior:'smooth'})` calls on a fast interval (word-by-word, poll-tick, etc.) will stutter** -- each call restarts the browser's in-flight smooth-scroll animation. Prefer a direct `scrollTop = scrollHeight` snap for auto-follow behavior that fires frequently, and gate it on a "pinned to bottom" check (via an `onScroll` listener) so it doesn't fight manual scrolling.
  - If asked to replicate an existing ASCII-art/box-drawing banner's exact font for new text, don't hand-draw new glyphs -- identify the actual font (e.g. via `pyfiglet`) and regenerate programmatically.
  - **A user-reported size/layout regression is not always a real code regression** -- check `getComputedStyle`/`getBoundingClientRect` before assuming a fix requires undoing a recent change.
  - **A `max-width` increase on a page's shared content container does not meaningfully widen one specific element inside it** if that element was already `w-full` within that container -- give it its own breakout width instead.
  - **This codebase runs two separate Tailwind engines simultaneously** (sitewide Play CDN v3 + react-app's precompiled v4 bundle) -- `-translate-*`/`scale-*`/`rotate-*` utilities can double up since v3/v4 emit different CSS properties for the same class names. Fix via scoped `transform: none !important` on the affected element, not a global config change.
  - **`overflow-x-hidden` + `overflow-y-visible` does NOT give a genuinely visible y-axis** (the `visible` value gets silently promoted to `auto`). Use `overflow-x-clip` instead.
  - **When a user says "use it exactly as shipped," that means the animation/interaction mechanics, not necessarily every prop default or outer wrapper sizing.**
- **Known CLI/registry-access gotchas, four distinct cases:**
  - **React Bits registry (`@react-bits/*`):** `npx shadcn@latest add @react-bits/<name>` fails with `Unexpected token (1:0)` for most items -- try plain CLI first; if it fails, `curl`/fetch `https://reactbits.dev/r/<name>.json` directly and place files manually.
  - **21st.dev registry items are auth-gated** (`401`/`403`) -- try `npx shadcn@latest add @aceternity/<slug>` first (same kebab-case slug, usually zero-auth); otherwise ask the user to paste the source.
  - **Skiper UI (`@skiper-ui/*`)** -- works via plain CLI; some items are paywalled Pro components (`401 {"error":"Missing license key..."}`).
  - **Aceternity registry (`@aceternity/*`)** -- works with zero auth via plain CLI.
- **Claude-in-Chrome automation quirks worth knowing for future frontend verification work (subject to the approval gate below):**
  - **Approval is per-ask, not a standing session-wide grant** -- ask again if a Chrome tool call is denied even after an earlier explicit "yes" in the same session.
  - `requestAnimationFrame`-driven animations throttle when the automated tab is backgrounded. Prefer checks that don't depend on live rAF progress.
  - **Screenshot pixel dimensions do not reliably match real DOM `getBoundingClientRect()` values** -- verify sizing via `getComputedStyle`/`getBoundingClientRect`, not screenshot proportions.
  - A `javascript_tool` call whose returned string looks like a query string can get silently `[BLOCKED: Cookie/query string data]` -- rephrase the extraction to return a narrower string.
  - `resize_window` is useful for testing wide-viewport-only layout effects -- check `screen.availWidth`/`availHeight` first via `javascript_tool`.
  - **Session 8 used no Claude-in-Chrome calls at all** -- every change was verified by the user manually refreshing and reporting back live, including the two ScanTerminal follow-up fixes and the header-spacing revert-and-redo.

**One loose end from Pass 6 (2026-08-09), still unresolved:** `CLAUDE.md` §9 still lists hygiene items -- check whether it's stale before next `CLAUDE.md` edit (it may have been trimmed already; verify against actual `CLAUDE.md` content rather than trusting this note).

## Standing rules for this engagement (apply to all future sessions, not just this one)

- **Never spawn a subagent without asking the user first and stating the reason.** Applies to planning and implementation alike. Codified globally in `C:\Users\ADMIN\.claude\CLAUDE.md` ("Subagent usage restrictions").
- **Never call the Claude-in-Chrome skill or any `mcp__claude-in-chrome__*` tool without the user's explicit approval first.** Codified globally in `C:\Users\ADMIN\.claude\CLAUDE.md` ("Claude in Chrome / browser automation restrictions"). Default behavior: implement a change, report what changed and where, stop -- let the user manually refresh and verify themselves. Approval does not reliably carry across multiple separate Chrome tool needs in the same session -- treat each need as its own ask.
- **Never write to `knowledge/` while implementation work is in progress** -- read-only during active work; writes only after everything for that unit of work is implemented, tested/reviewed, and committed.
- **All frontend work (HTML/CSS/JS under `apps/frontend/`) is delegated to Gemini 3.1 Pro** via an in-chat prompt, normally -- **TEMPORARILY SUSPENDED as of 2026-08-11 for the React Bits UI redesign workstream only**; Claude Code implements that workstream's frontend directly instead. Resumes (for that workstream too) whenever the user says so; do not assume it's suspended for any other frontend work.
- **Always run the local dev server as `http://localhost:5000`.** Firebase's authorized-domains list covers `localhost` and `sentinelscan-yd2u.onrender.com` only.
- **"Start the website" means the Flask backend at `http://localhost:5000`, NOT `apps/frontend/react-app`'s own `npm run dev`.** Correct two-step startup:
  1. `cd apps/frontend/react-app && npm run build` -- rebuilds `main.js`/`main.css` into `apps/frontend/static/react-dist/` (skip only if nothing under `react-app/src` changed since the last build).
  2. `python -m apps.backend.app` from the repo root -- serves the full site at `http://localhost:5000`.
  Only use `npm run dev` inside `react-app/` for isolated HMR iteration -- never hand that URL to the user as "the website." (Flask runs in debug/auto-reload mode -- backend `.py` edits reload automatically without a manual restart, confirmed session 8.)
- **When creating any new Google Cloud OAuth client for this project, verify the project selector shows `sentinelscan-3f82d` (project number `60214574079`) before creating it.**
- **Restart the Flask dev server after any `.env` change** -- no hot-reload for env files.
- **Never commit `scripts/oauth_client.json`** (or any real secret-shaped file) -- already `.gitignore`'d.
- **Render deploys must run a single gunicorn worker** (`--workers 1`, already set in `render.yaml`) -- `scan_store.py`'s active-scan state is an in-memory per-process dict.
- **Render Secret Files gotcha, if this ever needs redoing:** paste the *exact* file content fresh (delete-and-recreate rather than edit-in-place).
- **`DATABASE_URL`/SQLite is confirmed dead config, fully removed from docs/scripts as of Pass 6.**
- **Never hardcode a real token/JWT/secret-shaped literal in a committed file**, even in a skipped test.
- **The landing page's scan-authorization consent modal is gone as of session 8** -- there is no longer any UI step confirming the user owns/has permission to scan a target before a scan starts (never enforced server-side either). Don't assume it still exists or re-add it without the user asking.

## Note: secrets bootstrap is not automatic on `git pull`, and is a developer-laptop tool only

A teammate must manually run `python scripts/bootstrap_env.py` after pulling -- no `post-merge` git hook wired up yet. Cannot run on the deployed server (needs a local browser for the installed-app OAuth flow) -- deployed server's secrets were set directly in Render's dashboard. Teammates can point it at the live URL: `python scripts/bootstrap_env.py --server-url https://sentinelscan-yd2u.onrender.com`.

## Blockers

None.

## Other findings (not yet acted on, flagged for awareness)

- `.agents/skills/` -- a design-guidance skills directory the user has locally. Still untracked in git; still not decided whether to commit it for teammates to use too. Ask before adding it.
- `node_modules/` at the repo root remains untracked in git (pre-existing, not created by any workstream session) -- left alone; revisit only if the user asks. Root `.gitignore` does not currently exclude it explicitly.
- `CLAUDE.md` §9 "Known Hygiene Notes" may be stale again -- verify against current content before next edit.
- Render free-tier spin-down (~15 min idle -> ~1 min cold start) is expected behavior, not a bug.
- `apps/frontend/react-app/src/components/ui/button.jsx` is an unused default from `shadcn init` -- harmless, low-priority cleanup candidate whenever the workstream wraps up.
- **`SplashCursor.jsx` is a locally-modified fork, not a vendor-verbatim copy** -- re-running `npx shadcn add @react-bits/SplashCursor-JS-CSS` would silently clobber the click-removal/intensity-scaling/brightness-boost changes.
- `apps/frontend/react-app/src/components/ui/skiper-ui/skiper106.jsx` exists but is never imported/used -- only its caret-smoothing logic was hand-extracted into `placeholders-and-vanish-input.jsx`'s `useSmoothCaret` hook. Harmless dead file.
- `dialkit` was added to `package.json`/`package-lock.json` as a transitive dependency of `skiper106.jsx`'s unused dev-tuning panel import -- not invoked at runtime. Candidate to remove alongside `skiper106.jsx` if that file is ever deleted.
- `ShutterText.jsx` and `WarpText/` (`.jsx`/`.css`) are vendored but unused -- the hero heading uses `SplitText.jsx` instead. Same harmless-dead-file treatment.
- Every other vendored component in this repo is still byte-for-byte as fetched, except where a session log explicitly says otherwise (`SplashCursor`, `Skiper40`'s `Link000`, the hand-extracted `useSmoothCaret`, `SpecularFrame` which is a deliberately-adapted variant of `SpecularButton`'s shader).
- **`apps/frontend/templates/index.html` is a dead/unused file** (confirmed session 8) -- Flask serves `apps/frontend/index.html` directly via `send_from_directory` in `app.py`; the `templates/` copy is never rendered. Left in place, not deleted, since removal wasn't asked for -- but don't edit it expecting it to affect the live site, and don't assume it mirrors `index.html`'s current content (it still has the old consent modal as of session 8).

## Links

- Latest daily log: [[2026-08-14]] (sessions 5-8, same day: theme removal/hero swap/footer redesign/fluid cursor; footer brand mark+social links/smooth caret/Google icon; dashboard live scan terminal + hero SplitText + footer-menu fix; worker-summary fix, dashboard/hero parity, consolidated notices, consent modal removed, terminal typing animation)
- Previous daily log: [[2026-08-13]] (sessions 1-4: bootstrap+FloatingLines, intro preloader, ShinyText+StaggeredMenu+header/footer chrome removal, StaggeredMenu polish + hero ShutterText)
- `scripts/README.md` -- team secrets bootstrap setup/usage instructions.
- `render.yaml` -- Render deployment Blueprint (repo root).
- Live site: `https://sentinelscan-yd2u.onrender.com`
- Render service: `srv-d9rrj6n40ujc73c4efcg`
- Active frontend workstream: [[ui-redesign-reactbits]] (`knowledge/frontend-plans/ui-redesign-reactbits.md`) -- approved 2026-08-11. Eight sessions in, all committed and pushed to `feature/ui-redesign-reactbits`, `main` untouched throughout.
