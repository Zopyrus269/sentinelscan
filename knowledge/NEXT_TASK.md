---
type: knowledge-vault-core
last_updated: 2026-08-14
updated_by: claude-code
---

# Next Task

This file is always **overwritten**, not appended — it reflects the current handoff state only. Read this first in any new session, before analyzing code.

## What's next

**UI redesign workstream is in progress, on branch `feature/ui-redesign-reactbits`** (pushed to `origin/feature/ui-redesign-reactbits`, `main` untouched/deployable throughout). Plan: [[ui-redesign-reactbits]] (`knowledge/frontend-plans/ui-redesign-reactbits.md`).

- **Bootstrap is done.** `apps/frontend/react-app/` (Vite + React + Tailwind v4, preflight disabled, shadcn `init` with the `@react-bits` registry, plus `@aceternity` added session 5) builds cleanly to `apps/frontend/static/react-dist/{main.js,main.css}`, wired into all 9 existing HTML pages.
- **Pieces integrated and committed so far (chronological):**
  1. FloatingLines — site-wide animated background, cursor-reactive. Commit `d71e70a`.
  2. First-visit intro preloader (hand-built "double stairs" reveal). Commit `9b60780`.
  3. ShinyText — header brand text. StaggeredMenu — site-wide slide-out nav. Header/footer box removal. Commit `869dd4c`.
  4. Hero heading → ShutterText (hand-built extraction, not a raw vendor paste), gated on intro-reveal timing. StaggeredMenu polish. Commit `e8544e3`.
  5. **(2026-08-14, session 5 — see [[2026-08-14]] for full detail):**
     - Theme toggle removed entirely (deleted `theme.js`, its CSS, all 9 pages' script tags); every page statically locked to `class="dark"`. Account icon nudged closer to nav.
     - Hero URL input → `PlaceholdersAndVanishInput` (Aceternity), bridged to the existing `app.js` consent-modal flow via a hidden `#targetInput`/`#openConsentButton` pair — `app.js` itself untouched.
     - Hero subtitle → `TextType` (React Bits), gated on the same intro-reveal event as the ShutterText heading, `loop={false}` so it types once and holds.
     - "How SentinelScan Works" 3-card section: **emptied out, nothing renders there currently** — two replacement attempts (`ScrambledText`, then `TextGenerateEffect`) were both tried and abandoned/rejected. Don't assume a summary component belongs there; ask first.
     - Footer split into two `flex justify-between` blocks pinned to the true left/right page edges (not a centered max-width grid). `body` given a sitewide `flex flex-column` layout (`main` grows, `footer` stays pinned) so a short page no longer strands the footer mid-viewport.
     - Site-wide `SplashCursor` fluid cursor effect added, then **locally modified** (no longer a byte-for-byte vendor copy): click-triggered splats removed (only real cursor motion triggers a splat), splat brightness now scales continuously with per-event movement distance (dim floor for tiny nudges, full/boosted brightness only at genuine full-speed motion via new `MOVE_FULL_INTENSITY_DISTANCE`/`MOVE_MIN_INTENSITY`/`MOVE_FULL_INTENSITY_BOOST` props), color forced to white/non-rainbow.
     - Rejected experiment, fully cleaned up, no trace left: `LiquidEther` background tried in an isolated git worktree + second Flask instance, user didn't like it, worktree/branch deleted.
     - Commit `ab5b3db` — `feat(frontend): swap hero UI to React Bits components, restyle footer, add fluid cursor`. Pushed.
- **Session end state: everything is committed and pushed, nothing pending or broken.** Ask what the user wants to work on next — do not assume or guess at a next component.
- **After that:** resume the plan's per-component workflow (`knowledge/frontend-plans/ui-redesign-reactbits.md`, "Per-component workflow" section) for whatever component/change the user shares next.
- **Patterns established across all sessions so far, expected to recur — don't re-litigate each time (but still flag+ask if a genuinely new situation comes up):**
  - If a new component is itself meant as a background/full-bleed element, its container pages likely need the same transparent-body treatment as FloatingLines got.
  - If a new component has pointer/hover/scroll interactivity and is used as a full-page backdrop, check first whether it listens on `window`/`document` directly (no bridge needed, e.g. `SplashCursor`, `LiquidEther`) or on its own element (needs the `dispatchEvent` bridge pattern in `main.jsx`, e.g. `FloatingLines`) — never modify the shipped component file either way.
  - If a new component needs to coexist with something else that must never be interrupted (another persistent background, a global timer, a site-wide nav overlay), mount it on its own independent `createRoot()` rather than as a sibling in a shared tree — established pattern for every site-wide mount (background, splash cursor, intro, nav menu all do this).
  - If a target component turns out to be paywalled/gated (checked by hitting its registry JSON endpoint directly, e.g. `curl` — a `401`/license-key error means it's paid), stop and ask the user how they want to proceed rather than assuming.
  - **CSS conflicts between a shipped component and this site's existing global styles are a recurring category of bug.** Root-cause with `getBoundingClientRect()`/`getComputedStyle()`/`elementFromPoint()` via `javascript_tool`, never by guessing from the visual symptom. Fix via scoped CSS overrides (using the component's `className`/element selector as the scope hook) in either the react-app's own `index.css` or the site's `static/css/styles.css`, never by editing shipped component files.
  - **This codebase runs two separate Tailwind engines simultaneously** — the sitewide Tailwind Play CDN (v3, JIT-scans the whole live DOM) and the react-app's own precompiled Tailwind v4 bundle. Both generate rules for any Tailwind class name appearing anywhere in the DOM, including inside React-rendered markup. For most utilities this is harmless (same computed value from either engine), but **v3 and v4 emit `transform: translate/scale/rotate(...)` vs. separate standalone `translate`/`scale`/`rotate` CSS properties respectively for the same class names** — since those are different properties, the browser *composes* them instead of one overriding the other, silently doubling the visual effect. Hit this with the vanish-input's submit-button centering (`top-1/2 -translate-y-1/2`) in session 5. **Any future component using `-translate-*`, `scale-*`, or `rotate-*` utilities for positioning/sizing should be visually double-checked against its expected position** — if it's off by what looks like exactly double the intended transform, this is almost certainly why. Fix pattern: scoped `transform: none !important` (or similar) targeting just that element, not a global Tailwind config change.
  - **A component sized/positioned in `em` units relative to its own font-size will silently break once that font-size is overridden smaller** — re-check every rule implicitly sized relative to a font-size you change (padding, absolute-position offsets, sibling gutters).
  - **`overflow-x-hidden` + `overflow-y-visible` does NOT give a genuinely visible y-axis** (the `visible` value gets silently promoted to `auto`, still clips). Use `overflow-x-clip` instead when one axis needs to stay genuinely visible. Verify with `getComputedStyle(el).overflowY`.
  - **When a user says "use it exactly as shipped," that means the animation/interaction *mechanics*, not necessarily every prop default or every scrap of demo scaffolding** — confirmed again in session 5 (`TextType`'s `loop` default was reasonably overridden via a documented prop once the user said they didn't want the rewind behavior; this isn't a violation of "as shipped," it's using the component's own configuration surface). If a fix requires editing the vendored file's *internals* rather than just how it's invoked, that's a bigger step — flag it, like session 5's `SplashCursor` click-removal did, rather than silently forking silently.
  - **For "only when X" requests about a continuous physical quantity (speed, distance, time), default to a continuous scale/curve, not a binary on/off cutoff** — a hard threshold was tried first for `SplashCursor`'s "only splat during full motion" request and was immediately rejected as "not what I want"; the corrected version (continuous intensity scaling with a dim floor) was accepted. Binary cutoffs read as broken/jarring for anything the user describes in relative terms ("a little", "barely", "a lot").
- **Known CLI/registry-access gotchas, now three distinct cases:**
  - **React Bits registry (`@react-bits/*`):** `npx shadcn@latest add @react-bits/<name>` has failed with `Unexpected token (1:0)` for every item tried in sessions 1-4, **but worked on the first try for `SplashCursor` in session 5** — don't assume the bug still reproduces for a given item without trying the plain CLI command first. If it does fail: `curl`/fetch `https://reactbits.dev/r/<name>.json` directly (public, valid JSON) and place the files manually, then `npm install` any listed `dependencies`.
  - **21st.dev registry items are auth-gated** (`401`/`403` on both the CLI and a plain `curl`/`fetch`). **New in session 5: try `npx shadcn@latest add @aceternity/<slug>` first** (the component's own Aceternity registry, not the 21st.dev mirror URL the user may paste) — this works with zero auth via the plain CLI, confirmed for `placeholders-and-vanish-input` and `text-generate-effect`. The slug is usually the same kebab-case name as the 21st.dev URL's last path segment. Only fall back to reading the rendered 21st.dev page directly (`get_page_text`, if the user's browser session is signed in) if no matching `@aceternity/<slug>` exists.
  - **Skiper UI (`@skiper-ui/*`)** — some items are paywalled Pro components (confirmed for `skiper10`, session 2). Check for a `401 {"error":"Missing license key..."}` before assuming a fix is possible without a purchase.
- **Claude-in-Chrome automation quirks worth knowing for future frontend verification work:**
  - `requestAnimationFrame`-driven animations throttle to near-zero when the automated tab is backgrounded/unfocused between tool calls. Click into the tab immediately before checking, ideally in the same batched call. `document.hidden` has flapped unpredictably across sessions even with this workaround — prefer checks that don't depend on live rAF progress (event-listener wiring, computed style/DOM values) over catching one specific live animation frame.
  - Screenshot pixel dimensions do not reliably match `window.innerWidth`/`innerHeight` call-to-call. Prefer `find` (element-reference-based) over manual pixel-coordinate math when confirming a specific small element.
  - A `javascript_tool` call whose returned string happens to look like a query string (e.g. raw `outerHTML` containing `?`/`&`-shaped content) can get silently blocked with `[BLOCKED: Cookie/query string data]` — a false positive, not a real security issue. Rephrase the extraction to return a narrower/different-shaped string (e.g. just the specific attribute or property you need) rather than dumping full markup.

**Note:** this plan temporarily suspends the "frontend work goes to Gemini" standing rule below, for this workstream only — see that bullet.

**One loose end from Pass 6 (2026-08-09), still unresolved:** `CLAUDE.md` §9 still lists hygiene items — check whether it's stale before next `CLAUDE.md` edit (it may have been trimmed already; verify against actual `CLAUDE.md` content rather than trusting this note).

## Standing rules for this engagement (apply to all future sessions, not just this one)

- **Never spawn a subagent without asking the user first and stating the reason.** Applies to planning and implementation alike, including a project workflow (e.g. plan-mode's default Explore/Plan agent steps) that would otherwise auto-spawn one — ask first regardless. Now also codified globally in `C:\Users\ADMIN\.claude\CLAUDE.md` ("Subagent usage restrictions"), not just for this project.
- **Never write to `knowledge/` while implementation work is in progress** — read-only during active work; writes only after everything for that unit of work is implemented, tested, and committed.
- **All frontend work (HTML/CSS/JS under `apps/frontend/`) is delegated to Gemini 3.1 Pro** via an in-chat prompt (not a `knowledge/frontend-plans/` handoff file) — write a self-contained prompt, output it in chat, wait for the user's heads-up, then review and integrate. **TEMPORARILY SUSPENDED as of 2026-08-11 for the React Bits UI redesign workstream only** — see [[ui-redesign-reactbits]]; Claude Code implements that workstream's frontend directly instead. Resumes (for that workstream too) whenever the user says so; do not assume it's suspended for any other frontend work.
- **Always run the local dev server as `http://localhost:5000`.** Firebase's authorized-domains list now covers both `localhost` and `sentinelscan-yd2u.onrender.com` — a different host/port than either still breaks Google Sign-In popups unless deliberately added to Firebase first.
- **"Start the website" means the Flask backend at `http://localhost:5000`, NOT `apps/frontend/react-app`'s own `npm run dev`.** Correct two-step startup:
  1. `cd apps/frontend/react-app && npm run build` — rebuilds `main.js`/`main.css` into `apps/frontend/static/react-dist/` (skip only if nothing under `react-app/src` changed since the last build).
  2. `python -m apps.backend.app` from the repo root — serves the full site at `http://localhost:5000`.
  Only use `npm run dev` inside `react-app/` for isolated HMR iteration — never hand that URL to the user as "the website."
- **When creating any new Google Cloud OAuth client for this project, verify the project selector shows `sentinelscan-3f82d` (project number `60214574079`) before creating it.**
- **Restart the Flask dev server after any `.env` change** — no hot-reload for env files.
- **Never commit `scripts/oauth_client.json`** (or any real secret-shaped file) — already `.gitignore`'d.
- **Render deploys must run a single gunicorn worker** (`--workers 1`, already set in `render.yaml`) — `scan_store.py`'s active-scan state is an in-memory per-process dict.
- **Render Secret Files gotcha, if this ever needs redoing:** paste the *exact* file content fresh (delete-and-recreate rather than edit-in-place).
- **`DATABASE_URL`/SQLite is confirmed dead config, fully removed from docs/scripts as of Pass 6.**
- **Never hardcode a real token/JWT/secret-shaped literal in a committed file**, even in a skipped test.

## Note: secrets bootstrap is not automatic on `git pull`, and is a developer-laptop tool only

A teammate must manually run `python scripts/bootstrap_env.py` after pulling — no `post-merge` git hook wired up yet. Cannot run on the deployed server (needs a local browser for the installed-app OAuth flow) — deployed server's secrets were set directly in Render's dashboard. Teammates can point it at the live URL: `python scripts/bootstrap_env.py --server-url https://sentinelscan-yd2u.onrender.com`.

## Blockers

None.

## Other findings (not yet acted on, flagged for awareness)

- `.agents/skills/` — a design-guidance skills directory the user has locally. Still untracked in git; still not decided whether to commit it for teammates to use too. Ask before adding it.
- `node_modules/` at the repo root remains untracked in git (pre-existing, not created by any workstream session, confirmed again in session 5) — left alone; revisit only if the user asks. Root `.gitignore` does not currently exclude it explicitly — has been fine so far since it's simply never `git add`ed, but a stray `git add -A` by a future session would pick it up. Consider adding a root-level `node_modules/` ignore entry next time `.gitignore` is touched for any other reason.
- `CLAUDE.md` §9 "Known Hygiene Notes" may be stale again — verify against current content before next edit.
- Render free-tier spin-down (~15 min idle → ~1 min cold start) is expected behavior, not a bug.
- `apps/frontend/react-app/src/components/ui/button.jsx` is an unused default from `shadcn init` — harmless, low-priority cleanup candidate whenever the workstream wraps up.
- **`SplashCursor.jsx` is a locally-modified fork, not a vendor-verbatim copy** (see session 5 §6 in [[2026-08-14]]) — re-running `npx shadcn add @react-bits/SplashCursor-JS-CSS` would silently clobber the click-removal/intensity-scaling/brightness-boost changes. Every other vendored component in this repo is still byte-for-byte as fetched.

## Links

- Latest daily log: [[2026-08-14]] (session 5: theme removal, hero input/subtitle swap, footer edge-pin redesign, site-wide fluid cursor with iterative tuning)
- Previous daily log: [[2026-08-13]] (sessions 1-4: bootstrap+FloatingLines, intro preloader, ShinyText+StaggeredMenu+header/footer chrome removal, StaggeredMenu polish + hero ShutterText)
- `scripts/README.md` — team secrets bootstrap setup/usage instructions.
- `render.yaml` — Render deployment Blueprint (repo root).
- Live site: `https://sentinelscan-yd2u.onrender.com`
- Render service: `srv-d9rrj6n40ujc73c4efcg`
- Active frontend workstream: [[ui-redesign-reactbits]] (`knowledge/frontend-plans/ui-redesign-reactbits.md`) — approved 2026-08-11. Five sessions in, all committed and pushed to `feature/ui-redesign-reactbits`, `main` untouched throughout.
