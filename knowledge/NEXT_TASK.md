---
type: knowledge-vault-core
last_updated: 2026-08-15
updated_by: claude-code
---

# Next Task

This file is always **overwritten**, not appended -- it reflects the current handoff state only. Read this first in any new session, before analyzing code.

## What's next

**Nothing is pending.** Google sign-in is now fully working end-to-end on the live site (session 13, commits `ad20337` + `392e466`) -- verified live with the user's one-time Chrome authorization: clicked the icon, saw the real popup-driven sign-in complete, confirmed the account in the dropdown, signed back out. Do not assume anything below is "next up" without the user actually asking.

## Session 13 summary (2026-08-15) -- full detail in [[2026-08-15]]

Fixed Google sign-in (click did nothing / `auth/internal-error`). Root cause was CSP, in two parts:
1. Missing `frame-src` entirely (fell back to `default-src 'self'`), blocking the Firebase auth-relay iframe at `sentinelscan-3f82d.firebaseapp.com/__/auth/iframe`.
2. `script-src` missing `https://apis.google.com`, blocking gapi's `api.js` loader (also used by the popup relay).

Both were needed together -- fixing only #1 still left `auth/internal-error`. Diagnosed #2 by inspecting live network requests after deploying fix #1 and re-testing. Final CSP is in `apps/backend/app.py`'s `add_security_headers`; see [[2026-08-15]] for the full policy string. Both commits pushed straight to `main` per explicit user authorization in-session (including live-site verification via Chrome). Render auto-deployed both (~13 min build time each on the free tier -- expect that lag when polling after any push).

## Standing rules for this engagement (apply to all future sessions, not just this one)

- **Never spawn a subagent without asking the user first and stating the reason.** Codified globally in `C:\Users\ADMIN\.claude\CLAUDE.md`.
- **Never call the Claude-in-Chrome skill or any `mcp__claude-in-chrome__*` tool without the user's explicit approval first**, and re-ask for each new need even within the same session (approval doesn't carry over automatically) -- *except* continuing to use it within a single already-authorized task, as in session 13 where the user authorized fixing the sign-in bug end-to-end via Chrome and that covered the follow-up verification/second-fix cycle within the same task.
- **Never write to `knowledge/` while implementation work is in progress** -- read-only during active work; writes only after everything for that unit of work is implemented, tested/reviewed, and committed.
- **Frontend delegation to Gemini remains suspended** for the UI redesign workstream (moot, that workstream is closed) -- resumes as the default for any *new* frontend work unless the user says otherwise.
- **Always run the local dev server as `http://localhost:5000`** (Firebase authorized-domains covers `localhost` and the Render domain only). Two-step startup: `npm run build` in `apps/frontend/react-app`, then `python -m apps.backend.app` from repo root.
- **Never commit `scripts/oauth_client.json`** or any real secret-shaped file.
- **Render deploys must run a single gunicorn worker** (`scan_store.py`'s active-scan state is in-memory per-process).
- **Never hardcode a real token/JWT/secret-shaped literal in a committed file.**
- **When CSP changes touch auth or third-party embeds, verify live end-to-end (not just headers)** -- a CSP block on a relay script/iframe produces a generic SDK error (`auth/internal-error`) with no CSP violation surfaced in the app's own error handling; the only way to see the real cause is inspecting network requests for blocked/failed loads after reproducing the click live.
- The landing page's scan-authorization consent modal is gone (removed session 8) -- no UI step confirms scan ownership/permission, never enforced server-side either.
- Real contact address is `sentinelscan@gmail.com` (Responsible Disclosure section, footer `mailto:` link) -- old `security@sentinelscan.example` placeholder fully replaced as of session 10.

## Known CLI/registry-access gotchas (React Bits / Skiper UI), reconfirmed across many sessions

- **React Bits registry (`@react-bits/*`):** `npx shadcn@latest add @react-bits/<name>` fails with `Unexpected token (1:0)` for most items -- fetch `https://reactbits.dev/r/<name>.json` directly and place files manually instead.
- **Skiper UI (`@skiper-ui/*`):** works via plain CLI for free items; numbered Pro items 401 with a license-key error. Cross-check `https://skiper-ui.com/registry/registry.json`'s item list before assuming a numbered item is free -- `skiper60`/`skiper70` confirmed Premium/paywalled.
- **21st.dev registry items are auth-gated** -- try `@aceternity/<slug>` first (same slug, usually zero-auth).
- **Aceternity registry (`@aceternity/*`)** -- works with zero auth via plain CLI.

## Other findings (not yet acted on, flagged for awareness)

- `.agents/` and `node_modules/` at the repo root remain untracked -- pre-existing, left alone, revisit only if asked.
- `apps/frontend/react-app/src/components/ui/button.jsx` -- unused default from `shadcn init`, harmless low-priority cleanup candidate.
- `SplashCursor.jsx` is a locally-modified fork, not vendor-verbatim -- re-running its own `shadcn add` command would silently clobber the modifications.
- `skiper106.jsx` and its `dialkit` transitive dependency are dead/unused code, safe to remove together if ever touched.
- `ShutterText.jsx`/`WarpText/` are vendored but unused (hero uses `SplitText.jsx` instead).
- `apps/frontend/templates/index.html` is dead/unused -- Flask serves `apps/frontend/index.html` directly, this copy is never rendered and still has stale content (the old consent modal).
- If raw per-finding evidence is ever re-surfaced in the React report UI, port main's dropped `finding.evidence || finding.raw_data` preference into that new display logic (see session 11 merge-conflict note, `knowledge/daily-logs/2026-08-14.md`).
- Repo cleanup so `main` is the only branch is still sitting there unrequested (`feature/ui-redesign-reactbits` fully merged, safe to delete whenever asked -- see `knowledge/daily-logs/2026-08-14.md` for the exact steps, do not delete unassisted).

## Links

- Latest daily log: [[2026-08-15]] (session 13)
- Live site: `https://sentinelscan-yd2u.onrender.com` -- Google sign-in confirmed working end-to-end as of session 13.
- Render service: `srv-d9rrj6n40ujc73c4efcg`
- `scripts/README.md` -- team secrets bootstrap setup/usage instructions.
- `render.yaml` -- Render deployment Blueprint (repo root); confirmed `branch: main`, `autoDeploy: true`.
- UI redesign workstream plan: [[ui-redesign-reactbits]] (`knowledge/frontend-plans/ui-redesign-reactbits.md`) -- fully complete and closed out as of session 12.
