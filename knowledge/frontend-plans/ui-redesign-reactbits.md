---
status: approved, not yet started
approved: 2026-08-11
implementer: Claude Code (direct — see suspension note below, not Gemini)
---

# UI Redesign — React Bits "Islands" Integration

> Self-contained handoff plan. A fresh Claude Code session with zero memory of the planning conversation should be able to read this file alone and execute it.

## Context

The SentinelScan site (`apps/frontend/`, plain HTML/CSS/JS served directly by Flask, deployed as a single Render service) is getting a visual redesign. The user sources polished, pre-built animated components from React Bits (reactbits.dev) one at a time via its shadcn-based MCP server, reviews each integration manually, and only merges to `main` once the whole redesign is approved — because `main` is the live, deployed branch (`https://sentinelscan-yd2u.onrender.com`, Render auto-deploys on push to `main`).

As of 2026-08-11, `apps/frontend/` has **no React/Tailwind/shadcn/build-step** — flat HTML pages (`index.html`, `dashboard.html`, `report.html`, `status.html`, `documentation.html`, `api-reference.html`, `privacy.html`, `terms.html`, `responsible-disclosure.html`) plus vanilla JS (`static/js/app.js`, `dashboard.js`, `auth.js`, `main.js`, `report.js`, `theme.js`) calling `/api/v1/...` directly, Flask-served (`templates/index.html` is the one Flask-rendered page). Deployed via `render.yaml`: `env: python`, `gunicorn apps.backend.app:app --workers 1` (single worker is required — `scan_store.py` holds active-scan state in an in-memory per-process dict; do not add workers without first moving that state to Firestore or another shared store, per existing `NEXT_TASK.md` standing rule).

React Bits components are genuine JSX requiring a build step, so introducing them is unavoidably a toolchain change. **Decision: don't rewrite the frontend.** Add React as an **islands layer** — a small Vite/React/Tailwind build that compiles just the chosen React Bits components and mounts each one into a placeholder container inside the *existing* HTML pages. Everything else (Flask templates, the four JS files above, the `/api/v1/...` contract, existing CSS) stays untouched. Matches the user's actual workflow (pick one component, integrate, review, repeat) far better than a big-bang SPA rewrite, and satisfies "don't affect the backend" by construction.

**Analogy the user gave and confirmed applies:** this is putting a new bottle cap on a water bottle — aesthetics change, the water (backend behavior, API calls, auth, data) never does.

## Ground rules for this workstream

- **Claude Code implements directly.** The project's standing rule ("all frontend work delegated to Gemini 3.1 Pro via in-chat prompt," see `knowledge/NEXT_TASK.md` standing rules and project memory `feedback_frontend_delegation_to_gemini`) is **temporarily suspended** for this workstream only, per explicit user instruction on 2026-08-11. It resumes the moment the user says so — don't assume it's permanently gone, and don't assume the suspension covers frontend work outside this specific plan.
- **No subagents without prior approval, every time** — ask what the agent would do and why, wait for explicit approval, before any `Agent` tool call. Applies to planning and implementation alike, no exceptions for a project workflow that would otherwise auto-spawn one.
- **React Bits / shadcn MCP tools are invoked only when the user explicitly shares a specific component/install command** — never browse or add components proactively. This is also a pre-existing global rule (`C:\Users\ADMIN\.claude\CLAUDE.md`, "MCP server restrictions") independent of this project.
- **`apps/backend/**` is never modified** for this work. If a component needs to trigger existing behavior, wire its event handlers to the *existing* frontend JS functions/API calls — never a new or changed backend contract.

## Architecture: islands, not a rewrite

- New Vite + React (+ Tailwind, **preflight disabled** to avoid clobbering the existing global `static/css/style.css`/`styles.css`) app lives in `apps/frontend/react-app/` — self-contained `package.json`, isolated from the repo-root `package.json` (which only holds the unrelated `@modelcontextprotocol/server-filesystem` dev dependency used by the `knowledge-vault` MCP server).
- Build output goes to a static path Flask already serves — **verify the exact static-folder config in `apps/backend/app.py` before wiring anything**; likely `apps/frontend/static/`, e.g. output to `apps/frontend/static/react-dist/`. Existing HTML pages get a `<script type="module" src="...">` tag added plus a placeholder `<div id="...">` at the mount point — the only edit to existing HTML per component.
- **Built assets are committed to the repo, not built on Render.** `render.yaml` defines `env: python` with no Node toolchain guaranteed. Build locally each session and commit the compiled `react-dist` output alongside source, so `render.yaml` and the deploy process stay completely unchanged. (If a later session confirms Node *is* available on Render, building there instead is a possible future optimization — not required, don't chase it unprompted.)
- `node_modules/` is gitignored; `package.json`/`package-lock.json`, React source, and built output are tracked.

## Branch strategy

- New branch off `main`: `feature/ui-redesign-react-islands` (rename if the user prefers). All redesign work happens here.
- `main` stays deployable/untouched throughout — Render only auto-deploys on push to `main`, so branch work has zero live-site risk until merge.
- Merge to `main` only after the user has reviewed and approved the full set of integrated components **and** confirmed existing functionality (scans, reports, auth) still works end-to-end on the branch.

## One-time bootstrap (do this first, before any component is added)

1. Create and check out `feature/ui-redesign-react-islands` from `main`.
2. Scaffold Vite + React in `apps/frontend/react-app/`; add Tailwind with preflight disabled. Default to plain JS/JSX (no TypeScript) to match the rest of the project's no-TS convention — only switch to TS if the user asks.
3. Run `npx shadcn@latest init` inside `apps/frontend/react-app/` to generate its `components.json`; add the React Bits registry:
   ```json
   { "registries": { "@react-bits": "https://reactbits.dev/r/{name}.json" } }
   ```
4. Run `npx shadcn@latest mcp init --client claude`. **Verify where it writes MCP config** — Claude Code reads `.mcp.json` from the repo root, which already has a `knowledge-vault` entry; if the shadcn init doesn't merge into the root file, merge it manually so both MCP servers are visible in the same session. Use `/mcp` in Claude Code to debug, per React Bits' own guidance (https://reactbits.dev/get-started/mcp).
5. Wire the build output path into Flask's static serving — confirm exact static-folder config in `apps/backend/app.py` first; no backend route/logic changes, just point the build there.
6. Confirm `npm run build` succeeds and the site is 100% visually/functionally identical to before (no components added yet) — this is the baseline check before any island is introduced.
7. Always run the local dev server at `http://localhost:5000` for testing (existing project standing rule — Firebase's authorized-domains list covers `localhost` and the production URL, not other host/port combos; Google Sign-In popups break otherwise).

## Per-component workflow (repeats for every component the user shares)

1. User shares a React Bits component page + its "copy install command."
2. Claude runs that install command via the shadcn MCP **only for that explicit request.**
3. Claude mounts the component into a placeholder container on the target page. Component is used **exactly as shipped** (styling, structure, animation) — any deviation requires asking the user first and getting approval.
4. If the component is interactive, wire its props/handlers to the **existing** JS functions in `app.js`/`dashboard.js`/`report.js`/`auth.js` — same fetch calls, same `/api/v1/...` contract, same auth flow. No backend changes, ever.
5. Build (`npm run build`), run the Flask app locally, and visually verify: the new component renders correctly, and the page's existing functionality (buttons, forms, API-backed behavior) is unchanged. Use the project's `run` skill / browser tools for this rather than claiming success untested.
6. Run `pytest tests/` as a zero-regression tripwire (backend is untouched so this should trivially pass — it's a safety net, not the primary verification for a frontend change).
7. User reviews the result live/in-browser. On approval, commit as one small atomic commit, e.g. `feat(frontend): integrate <ComponentName> from React Bits into dashboard`.
8. Repeat for the next component — no fixed page order; driven entirely by whatever the user shares next.

## Merge & deploy

- No `render.yaml` changes anticipated — same gunicorn/Flask process, just more static assets served.
- Once the user has approved the full set of integrated components on the branch, merge `feature/ui-redesign-react-islands` into `main`.
- Render auto-deploys on push to `main`. After deploy, confirm the live site: visual check of redesigned pages, plus confirm `/api/v1/...` endpoints (scans, reports, auth) still function — same verification as bootstrap step 6 / per-component step 5, against production.

## Security considerations

- Before installing each component, check its dependencies (e.g. three.js/gsap/framer-motion pulled in by animated React Bits components) and confirm it doesn't fetch remote assets/scripts at runtime (CSP/offline risk, supply-chain surface).
- No backend/business-logic exposure risk by construction — this workstream never touches `apps/backend/**`. CLAUDE.md §2 (no exploit code, authorized-use-only) isn't directly implicated by a UI-only change.

## Open items to verify during bootstrap (not blockers, just unresolved as of plan approval)

- Exact static-file serving path/config in `apps/backend/app.py`.
- Whether `shadcn mcp init` needs its output manually merged into the root `.mcp.json`.
- Confirm Render's Python environment has no Node available (justifying "commit built assets" over "build on Render").

## Verification / testing strategy summary

- Baseline check after bootstrap: site unchanged before any component is added.
- Per component: local build + local Flask run + manual browser check of both new visual and pre-existing functionality + `pytest tests/` as a backend-regression tripwire.
- Pre-merge: full pass over every redesigned page on the branch, confirming all existing user flows (scan start, report view, auth) still work.
- Post-deploy: same functional check against the live Render URL.
