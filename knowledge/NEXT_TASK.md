---
type: knowledge-vault-core
last_updated: 2026-08-20
updated_by: claude-code
---

# Next Task

This file is always **overwritten**, not appended -- it reflects the current handoff state only. Read this first in any new session, before analyzing code.

## What's next

**One PR awaiting merge: PR #4** (session 15, Graphify code-structure graph integration) --
https://github.com/Zopyrus269/sentinelscan/pull/4, branch `feat/graphify-setup`. Committed, pushed,
tested (graph scope verified, real query smoke-tested), not yet merged -- per the standing
PR-required-for-main rule, that's for the user to read and merge (Squash and merge recommended, per
session 14's convention), then delete the branch. Full detail in [[2026-08-20]] (session 15).

Once merged: treat `graphify query <question>`, `graphify path <A> <B>`, `graphify explain <concept>` as
the first tool for any structural "what calls X / where is Y / how do these connect" question in this
repo -- `graphify-out/graph.json` will exist on `main` at that point. See `CLAUDE.md` section 11 for the
read-anytime/write-at-session-end policy and the corrected regen command
(`graphify extract . --code-only --force`, never `update`).

Otherwise, nothing else is pending. Both PRs from session 14 are merged into `main` (PR #1 `c585671`,
PR #2 `6eee4b4`), every side branch from that session was deleted. Full test suite re-run on merged
`main` (pre-session-15): 139 passed, 1 skipped, same 5 pre-existing unrelated failures as before (see
"Other findings" below) -- nothing broken by the merge. Do not assume anything below is "next up"
without the user actually asking.

**The PR-required-for-main rule (CLAUDE.md section 10) is now live in `main` itself**, not just on a
branch. From this point on, *every* future session must open a short-lived branch + PR for any work
reaching `main` -- including a routine knowledge-vault-only update -- then delete that branch once
merged, to keep `main` as the repo's only permanent branch, per explicit user instruction. GitHub branch
protection backs this up server-side (`enforce_admins: true`, direct pushes to `main` are rejected).

## Session 15 summary (2026-08-20) -- full detail in [[2026-08-20]]

Copied the user's already-working Graphify integration from their other project (Clyro) into this repo:
`.claude/skills/graphify/`, a repo-scoped `.graphifyignore`, and a new `CLAUDE.md` section 11 -- all
copied/written by hand, never via `graphify install` (which Clyro's notes document as auto-installing an
unwanted `PreToolUse` hook + CLAUDE.md text). Built the initial graph (`graphify extract . --code-only`,
`cluster-only --no-label`, `label --backend=claude-cli`). Caught and fixed a real issue mid-build: a
minified Vite bundle (`apps/frontend/static/react-dist/main.js`) was 57% of the first build's nodes,
pure noise -- excluded it and rebuilt to a clean **1050 nodes / 1747 edges / 86 communities**. Verified
scope (zero nodes from excluded paths) and smoke-tested with a real query. Opened as PR #4, not yet
merged.

## Session 14 summary (2026-08-20) -- full detail in [[2026-08-20]]

Repo cleanup: deleted `feature/ui-redesign-reactbits` (fully merged already). Reviewed
`origin/dhanush-changes`, found and fixed a real bug (`ssrf_validator.py` `NameError` that would break
every scan submission), added missing test coverage, opened it as PR #1 rather than merging directly.
Adopted a new permanent project rule: every merge to `main` requires a PR, no exceptions -- codified in
CLAUDE.md section 10 and enforced server-side via GitHub branch protection on `main`
(`required_approving_review_count: 0` -- corrected same day from an initial `1`, since GitHub can never
let a PR author approve their own PR and these PRs are opened under the repo owner's own account; see
DECISIONS.md's 2026-08-20 correction entry -- `enforce_admins: true`, no force-push/deletion, still in
effect). Opened as PR #2. User merged both PRs on GitHub using Squash and merge. This session then
verified the merge (content + full test suite on `main`) and deleted every branch except `main` --
`chore/pr-required-for-main`, `fix/dhanush-security-changes`, and `origin/dhanush-changes` are all gone,
local and remote. Repo now has exactly one branch.

## Standing rules for this engagement (apply to all future sessions, not just this one)

- **New as of session 14: every merge to `main` requires a GitHub PR to exist (no direct pushes), no
  exceptions** -- see CLAUDE.md section 10 and DECISIONS.md's two 2026-08-20 entries (original decision
  + same-day correction). Applies to Claude Code, the repo owner, and every other collaborator equally;
  enforced both as a documented rule and via GitHub branch protection (`enforce_admins` on). Required
  approving reviews are set to **0**, not 1 -- GitHub blocks a PR author from approving their own PR,
  and these PRs are opened under the repo owner's own account, so requiring an approval would make them
  permanently unmergeable. The owner opens the PR, reads the diff, and merges it themselves -- that's
  the actual control, not a second person's sign-off. Never `git push` directly to `main` or
  `git merge` into a locally checked-out `main` and push that -- always branch -> commit -> push branch
  -> open PR -> read the diff -> merge via GitHub (**Squash and merge** is the recommended method --
  keeps `main` to one clean commit per PR, matches the "small, atomic commits" convention, and GitHub
  still credits co-authors via a `Co-authored-by:` trailer even when commits get folded together).
- **User wants only `main` to exist in this repo, permanently** -- confirmed explicitly in session 14
  after the cleanup. Delete every branch (local + remote) as soon as its PR is merged; don't leave
  merged branches sitting around "just in case." This includes short-lived branches created purely for
  a knowledge-vault update.
- **Never spawn a subagent without asking the user first and stating the reason.** Codified globally in
  `C:\Users\ADMIN\.claude\CLAUDE.md`.
- **New as of session 15: `graphify-out/graph.json` exists once PR #4 merges -- reach for `graphify
  query`/`path`/`explain` first on any structural question** ("what calls X", "where is Y defined",
  "how do these connect") before a grep-and-read sweep. Codified globally (applies to every project) in
  `~/.claude/CLAUDE.md`, with repo-specific scope/policy detail in this project's `CLAUDE.md` section 11.
  Regenerate only at session-end, batched with the knowledge-vault write, using
  `graphify extract . --code-only --force` -- never `graphify update .` (has no `--code-only` flag, can
  silently reintroduce excluded paths). See [[DECISIONS]]'s 2026-08-20 Graphify entry for full
  rationale.
- **Never call the Claude-in-Chrome skill or any `mcp__claude-in-chrome__*` tool without the user's
  explicit approval first**, and re-ask for each new need even within the same session (approval
  doesn't carry over automatically) -- *except* continuing to use it within a single already-authorized
  task.
- **Never write to `knowledge/` while implementation work is in progress** -- read-only during active
  work; writes only after everything for that unit of work is implemented, tested/reviewed, and
  committed (now: committed *and on a PR branch*, per the new rule above -- not pushed to `main`
  directly even for vault-only changes).
- **Frontend delegation to Gemini remains suspended** for the UI redesign workstream (moot, that
  workstream is closed) -- resumes as the default for any *new* frontend work unless the user says
  otherwise.
- **Always run the local dev server as `http://localhost:5000`** (Firebase authorized-domains covers
  `localhost` and the Render domain only). Two-step startup: `npm run build` in
  `apps/frontend/react-app`, then `python -m apps.backend.app` from repo root.
- **Never commit `scripts/oauth_client.json`** or any real secret-shaped file.
- **Render deploys must run a single gunicorn worker** (`scan_store.py`'s active-scan state is in-memory
  per-process).
- **Never hardcode a real token/JWT/secret-shaped literal in a committed file.** (This exact class of
  issue was found and fixed in `.env.example` as part of PR #1 -- a generated-looking FLASK_SECRET_KEY
  was committed there; replaced with a placeholder.)
- **When CSP changes touch auth or third-party embeds, verify live end-to-end (not just headers).**
- The landing page's scan-authorization consent modal is gone (removed session 8) -- no UI step
  confirms scan ownership/permission, never enforced server-side either.
- Real contact address is `sentinelscan@gmail.com` -- old placeholder fully replaced as of session 10.
- The GitHub MCP server's token does not have PR-creation scope (`create_pull_request` 403'd with
  "Resource not accessible by personal access token") -- use `gh pr create`/`gh pr edit` via Bash
  instead. No MCP tool exposes branch-protection settings either; use `gh api -X PUT
  repos/{owner}/{repo}/branches/{branch}/protection`.

## Known CLI/registry-access gotchas (React Bits / Skiper UI), reconfirmed across many sessions

- **React Bits registry (`@react-bits/*`):** `npx shadcn@latest add @react-bits/<name>` fails with
  `Unexpected token (1:0)` for most items -- fetch `https://reactbits.dev/r/<name>.json` directly and
  place files manually instead.
- **Skiper UI (`@skiper-ui/*`):** works via plain CLI for free items; numbered Pro items 401 with a
  license-key error.
- **21st.dev registry items are auth-gated** -- try `@aceternity/<slug>` first (same slug, usually
  zero-auth).
- **Aceternity registry (`@aceternity/*`)** -- works with zero auth via plain CLI.

## Other findings (not yet acted on, flagged for awareness)

- `.agents/` and `node_modules/` at the repo root remain untracked -- pre-existing, left alone, revisit
  only if asked.
- `apps/frontend/react-app/src/components/ui/button.jsx` -- unused default from `shadcn init`, harmless
  low-priority cleanup candidate.
- `SplashCursor.jsx` is a locally-modified fork, not vendor-verbatim -- re-running its own `shadcn add`
  command would silently clobber the modifications.
- `skiper106.jsx` and its `dialkit` transitive dependency are dead/unused code, safe to remove together
  if ever touched.
- `ShutterText.jsx`/`WarpText/` are vendored but unused (hero uses `SplitText.jsx` instead).
- `apps/frontend/templates/index.html` is dead/unused -- Flask serves `apps/frontend/index.html`
  directly, this copy is never rendered and still has stale content (the old consent modal).
- If raw per-finding evidence is ever re-surfaced in the React report UI, port main's dropped
  `finding.evidence || finding.raw_data` preference into that new display logic.
- 5 pre-existing test failures unrelated to any current work, confirmed present on unmodified `main`:
  `test_cookie_worker::test_cookies_worker_connection_error`,
  `test_headers_worker::test_headers_worker_timeout_exception`,
  `test_sitemap_worker::test_connection_error`, `test_sitemap_worker::test_timeout_error`,
  `test_ssl_worker::test_socket_timeout` -- all look like Playwright-fallback/timeout-handling drift,
  not touched this session, worth a dedicated look sometime.
- Local dev venv was missing `flask_limiter`/`playwright` despite being in `requirements.txt` -- fixed
  locally this session via `pip install -r requirements.txt`; if a fresh clone hits the same gap, that's
  the fix.

## Links

- Latest daily log: [[2026-08-20]] (sessions 14-15)
- Open PR: [#4](https://github.com/Zopyrus269/sentinelscan/pull/4) (Graphify integration, session 15,
  awaiting merge)
- Merged PRs: [#1](https://github.com/Zopyrus269/sentinelscan/pull/1) (dhanush-changes security
  hardening + SSRF fix), [#2](https://github.com/Zopyrus269/sentinelscan/pull/2) (PR-required rule)
- Live site: `https://sentinelscan-yd2u.onrender.com` -- Google sign-in confirmed working end-to-end as
  of session 13.
- Render service: `srv-d9rrj6n40ujc73c4efcg`
- `scripts/README.md` -- team secrets bootstrap setup/usage instructions.
- `render.yaml` -- Render deployment Blueprint (repo root); confirmed `branch: main`, `autoDeploy: true`.
- Repo collaborators (via GitHub API, session 14): `Zopyrus269` (admin), `Dannyo6`, `sbsai25`,
  `bhuvan-sk`.
