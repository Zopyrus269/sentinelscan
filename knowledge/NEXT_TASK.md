---
type: knowledge-vault-core
last_updated: 2026-08-14
updated_by: claude-code
---

# Next Task

This file is always **overwritten**, not appended -- it reflects the current handoff state only. Read this first in any new session, before analyzing code.

## What's next

**The UI redesign merge is done and live-verified.** `feature/ui-redesign-reactbits` was merged into `main` (merge commit `a510ac0`), pushed, Render auto-deployed it, and the live site (`https://sentinelscan-yd2u.onrender.com`) was checked and confirmed to be serving the merged UI work (landing page + documentation page both showed the redesign, not a stale build). Full detail in [[2026-08-14]] "Session 11".

**Not yet done, and not yet requested by the user this round:** repo cleanup so `main` is the only branch. `feature/ui-redesign-reactbits` still exists on `origin` and locally, now fully merged (safe to delete once the user asks) -- do not delete it unassisted, per the destructive-action confirmation policy. If the user asks for the cleanup next session:

1. Confirm `git log main..origin/feature/ui-redesign-reactbits` is empty (branch fully contained in `main`) before deleting anything.
2. `git push origin --delete feature/ui-redesign-reactbits`, then delete the local branch too.
3. Re-check `git branch -a` shows only `main` (plus `remotes/origin/HEAD -> origin/main`).

## Session 11 summary (2026-08-14) -- full detail in [[2026-08-14]] "Session 11"

Merged `feature/ui-redesign-reactbits` (23 commits, the full UI redesign workstream) into `main` (which had 2 independent security commits: SSRF/WAF/domain-verifier work, `6a3fc54`/`dfc1f12`). One real conflict in `apps/frontend/static/js/report.js` -- resolved by keeping the feature branch's removal of dead DOM-writer functions (`renderCvssScores`/`renderWorkerFindings`/`renderRecommendations`), since the new React `ReportCrawl` flow superseded them; main's one-line security fix inside the deleted `renderWorkerFindings` is moot for now (flagged as a follow-up if raw findings are ever re-surfaced in the new UI). `app.py`/`scan_routes.py` auto-merged cleanly despite both branches touching them. Verified `npm run build` succeeds post-merge. Pushed as `a510ac0`. Render auto-deployed (`render.yaml`: `branch: main`, `autoDeploy: true`); live site checked with the user's one-time Chrome authorization and confirmed current.

## Standing rules for this engagement (apply to all future sessions, not just this one)

- **Never spawn a subagent without asking the user first and stating the reason.** Codified globally in `C:\Users\ADMIN\.claude\CLAUDE.md`.
- **Never call the Claude-in-Chrome skill or any `mcp__claude-in-chrome__*` tool without the user's explicit approval first**, and re-ask for each new need even within the same session (approval doesn't carry over automatically). Codified globally. (Session 11's live-site check was one-time-authorized for that specific purpose -- doesn't carry forward to future sessions.)
- **Never write to `knowledge/` while implementation work is in progress** -- read-only during active work; writes only after everything for that unit of work is implemented, tested/reviewed, and committed.
- **Frontend delegation to Gemini remains suspended** for this workstream (was suspended 2026-08-11) -- now moot since the workstream is merged, but resumes as the default for any *new* frontend work unless the user says otherwise.
- **Always run the local dev server as `http://localhost:5000`** (Firebase authorized-domains covers `localhost` and the Render domain only). Two-step startup: `npm run build` in `apps/frontend/react-app`, then `python -m apps.backend.app` from repo root.
- **Never commit `scripts/oauth_client.json`** or any real secret-shaped file.
- **Render deploys must run a single gunicorn worker** (`scan_store.py`'s active-scan state is in-memory per-process).
- **Never hardcode a real token/JWT/secret-shaped literal in a committed file.**
- The landing page's scan-authorization consent modal is gone (removed session 8) -- no UI step confirms scan ownership/permission, never enforced server-side either.
- Real contact address is `sentinelscan@gmail.com` (Responsible Disclosure section, footer `mailto:` link) -- old `security@sentinelscan.example` placeholder fully replaced as of session 10.

## Known CLI/registry-access gotchas (React Bits / Skiper UI), reconfirmed across many sessions

- **React Bits registry (`@react-bits/*`):** `npx shadcn@latest add @react-bits/<name>` fails with `Unexpected token (1:0)` for most items -- fetch `https://reactbits.dev/r/<name>.json` directly and place files manually instead.
- **Skiper UI (`@skiper-ui/*`):** works via plain CLI for free items; numbered Pro items 401 with a license-key error. Cross-check `https://skiper-ui.com/registry/registry.json`'s item list before assuming a numbered item is free -- `skiper60`/`skiper70` confirmed Premium/paywalled.
- **21st.dev registry items are auth-gated** -- try `@aceternity/<slug>` first (same slug, usually zero-auth).
- **Aceternity registry (`@aceternity/*`)** -- works with zero auth via plain CLI.

## Other findings (not yet acted on, flagged for awareness)

- `.agents/` and `node_modules/` at the repo root remain untracked -- pre-existing, left alone, revisit only if asked.
- An unexplained uncommitted one-line `.gitignore` edit (adding `node_modules`) appeared during session 11's merge with no clear origin -- reverted rather than carried forward. If it reappears, worth tracking down where it's coming from (editor auto-save? a script?) rather than reverting blind every time.
- `apps/frontend/react-app/src/components/ui/button.jsx` -- unused default from `shadcn init`, harmless low-priority cleanup candidate.
- `SplashCursor.jsx` is a locally-modified fork, not vendor-verbatim -- re-running its own `shadcn add` command would silently clobber the modifications.
- `skiper106.jsx` and its `dialkit` transitive dependency are dead/unused code, safe to remove together if ever touched.
- `ShutterText.jsx`/`WarpText/` are vendored but unused (hero uses `SplitText.jsx` instead).
- `apps/frontend/templates/index.html` is dead/unused -- Flask serves `apps/frontend/index.html` directly, this copy is never rendered and still has stale content (the old consent modal).
- If raw per-finding evidence is ever re-surfaced in the React report UI, port main's dropped `finding.evidence || finding.raw_data` preference into that new display logic (see session 11 merge-conflict note).

## Links

- Latest daily log: [[2026-08-14]] (sessions 5-11, same day)
- Live site: `https://sentinelscan-yd2u.onrender.com` -- confirmed serving merged `main` as of session 11.
- Render service: `srv-d9rrj6n40ujc73c4efcg`
- `scripts/README.md` -- team secrets bootstrap setup/usage instructions.
- `render.yaml` -- Render deployment Blueprint (repo root); confirmed `branch: main`, `autoDeploy: true`.
- UI redesign workstream plan: [[ui-redesign-reactbits]] (`knowledge/frontend-plans/ui-redesign-reactbits.md`) -- approved 2026-08-11, feature-complete, **merged into `main` as of session 11**.
