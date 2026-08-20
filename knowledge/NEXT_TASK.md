---
type: knowledge-vault-core
last_updated: 2026-08-21
updated_by: claude-code
---

# Next Task

This file is always **overwritten**, not appended -- it reflects the current handoff state only. Read this first in any new session, before analyzing code.

## What's next

**Nothing is pending.** PR #6 (session 16, frontend dead-code cleanup + fixed the 5 pre-existing
test failures) is merged into `main` as `2b7fe76`. Repo has exactly one branch, `main`, both
locally and on `origin`. Full test suite on merged `main`: **144 passed, 1 skipped**, zero failures
(up from 139 passed/1 skipped/5 failed as of session 15) -- the 5 pre-existing failures flagged in
the last session's "Other findings" are now actually fixed, not just documented. Frontend build
(`npm run build`) clean.

`graphify-out/graph.json` regenerated this session (`apps/frontend/` and `tests/` both changed):
**1030 nodes, 1722 edges, 80 communities** (was 1050/1747/86 as of session 15 -- the decrease
matches the deleted frontend files). Verified clean scope (zero nodes from excluded paths, none
`.md`). Treat `graphify query <question>`, `graphify affected <symbol>`, `graphify path <A> <B>`,
`graphify explain <concept>` as the first tool for structural questions in this repo -- see
`CLAUDE.md` section 11. One practical refinement from this session: `graphify affected` (reverse
traversal, "what depends on X") has proven reliable and precise; `graphify query`'s forward BFS
("is X referenced anywhere") has been noisy/imprecise in practice (same-community nodes rather
than precise import edges) -- prefer Grep for that specific question shape until/unless the query
heuristics improve.

Do not assume anything below is "next up" without the user actually asking.

## Session 16 summary (2026-08-21) -- full detail in [[2026-08-21]]

User asked what was left unaddressed from the prior session; picked two items off
`NEXT_TASK.md`'s "Other findings" list to actually resolve. **Frontend cleanup**: deleted
`button.jsx`, `skiper106.jsx` (+ its now-unused `dialkit` npm dependency), `ShutterText/`,
`WarpText/`, and the dead `apps/frontend/templates/index.html` -- all confirmed via Grep to have
zero real imports. **Test fixes, real root causes found (not just "drift")**: `cookie_worker`,
`headers_worker`, and `sitemap_worker`'s tests only mocked `requests.get`, not the Playwright
browser fallback (`fetch_with_browser`) those workers gained later -- under real network access
the un-mocked fallback silently succeeded against the live `https://example.com` target used in
`setUp()`, masking the error the tests meant to check; fixed by mocking the fallback to fail too.
`ssl_worker`'s `test_socket_timeout` was simply stale -- the worker already treats a TLS timeout as
security evidence (a successful result, not a failure), matching the same philosophy already
applied to cert-verification errors a few lines above; updated the test to match, confirmed with
user first since it's a semantics change not a pure bug fix. Used `graphify affected
"fetch_with_browser"` to find all callers, which caught that `ddos_worker.py`/`robots_worker.py`
also use it (no active bug in either, just flagged for future awareness). Opened as PR #6, user
reviewed and squash-merged as `2b7fe76`. Post-merge: re-verified tests + build on merged `main`,
deleted the branch locally and remotely, regenerated `graphify-out/`, wrote this vault update.

## Session 15 summary (2026-08-20) -- full detail in [[2026-08-20]]

Copied the user's already-working Graphify integration from their other project (Clyro) into this
repo: `.claude/skills/graphify/`, a repo-scoped `.graphifyignore`, and a new `CLAUDE.md` section 11
-- all copied/written by hand, never via `graphify install` (which Clyro's notes document as
auto-installing an unwanted `PreToolUse` hook + CLAUDE.md text). Built the initial graph, excluded
a minified Vite bundle that was polluting it, opened as PR #4, fixed a Gitleaks false-positive on
graphify's own cache directory, squash-merged as `790c000`. User then set a new global rule: no
`Co-Authored-By: Claude` trailer on any commit, ever.

## Standing rules for this engagement (apply to all future sessions, not just this one)

- **Every merge to `main` requires a GitHub PR to exist (no direct pushes), no exceptions** -- see
  CLAUDE.md section 10 and DECISIONS.md's two 2026-08-20 entries. Applies to Claude Code, the repo
  owner, and every other collaborator equally; enforced both as a documented rule and via GitHub
  branch protection (`enforce_admins` on). Required approving reviews are set to **0**, not 1 --
  GitHub blocks a PR author from approving their own PR, and these PRs are opened under the repo
  owner's own account, so requiring an approval would make them permanently unmergeable. The owner
  opens the PR, reads the diff, and merges it themselves -- that's the actual control. Never
  `git push` directly to `main` or `git merge` into a locally checked-out `main` and push that --
  always branch -> commit -> push branch -> open PR -> read the diff -> merge via GitHub (**Squash
  and merge** recommended). Commits carry no `Co-authored-by:` trailer.
- **User wants only `main` to exist in this repo, permanently** -- delete every branch (local +
  remote) as soon as its PR is merged, including short-lived branches created purely for a
  knowledge-vault/graphify-only update.
- **Never spawn a subagent without asking the user first and stating the reason.** Codified
  globally in `C:\Users\ADMIN\.claude\CLAUDE.md`.
- **No commit in this repo (or any repo on this machine) should carry a `Co-Authored-By: Claude`
  trailer.** Commits show only the user's own git identity. Codified globally.
- **`graphify-out/graph.json` exists on `main` -- reach for `graphify query`/`affected`/`path`/
  `explain` first on any structural question** before a grep-and-read sweep. `graphify affected`
  (reverse traversal) has proven the most reliable for "what depends on X" questions; `graphify
  query`'s forward BFS has been noisy for "is X referenced anywhere" dead-code checks -- Grep still
  wins there in practice (see session 16). Regenerate only at session-end, batched with the
  knowledge-vault write, using `graphify extract . --code-only --force` -- never `graphify
  update .` (no `--code-only` flag, can silently reintroduce excluded paths).
- **Never call the Claude-in-Chrome skill or any `mcp__claude-in-chrome__*` tool without the
  user's explicit approval first**, and re-ask for each new need even within the same session.
- **Never write to `knowledge/` while implementation work is in progress** -- read-only during
  active work; writes only after everything for that unit of work is implemented,
  tested/reviewed, and committed *and merged via PR*.
- **Frontend delegation to Gemini remains suspended** for the (closed) UI redesign workstream --
  resumes as the default for any *new* frontend work unless the user says otherwise.
- **Always run the local dev server as `http://localhost:5000`** (Firebase authorized-domains
  covers `localhost` and the Render domain only). Two-step startup: `npm run build` in
  `apps/frontend/react-app`, then `python -m apps.backend.app` from repo root.
- **Never commit `scripts/oauth_client.json`** or any real secret-shaped file.
- **Render deploys must run a single gunicorn worker** (`scan_store.py`'s active-scan state is
  in-memory per-process).
- **Never hardcode a real token/JWT/secret-shaped literal in a committed file.**
- **When CSP changes touch auth or third-party embeds, verify live end-to-end (not just headers).**
- The landing page's scan-authorization consent modal is gone (removed session 8) -- no UI step
  confirms scan ownership/permission, never enforced server-side either. Still open, not yet
  prioritized.
- Real contact address is `sentinelscan@gmail.com` -- old placeholder fully replaced as of
  session 10.
- The GitHub MCP server's token does not have PR-creation scope -- use `gh pr create`/`gh pr edit`
  via Bash instead. No MCP tool exposes branch-protection settings either; use
  `gh api -X PUT repos/{owner}/{repo}/branches/{branch}/protection`.
- **`SplashCursor.jsx` is a hand-modified fork, not vendor-verbatim** -- re-running its own
  `shadcn add` command would silently clobber the modifications.

## Known CLI/registry-access gotchas (React Bits / Skiper UI), reconfirmed across many sessions

- **React Bits registry (`@react-bits/*`):** `npx shadcn@latest add @react-bits/<name>` fails with
  `Unexpected token (1:0)` for most items -- fetch `https://reactbits.dev/r/<name>.json` directly
  and place files manually instead.
- **Skiper UI (`@skiper-ui/*`):** works via plain CLI for free items; numbered Pro items 401 with a
  license-key error.
- **21st.dev registry items are auth-gated** -- try `@aceternity/<slug>` first (same slug, usually
  zero-auth).
- **Aceternity registry (`@aceternity/*`)** -- works with zero auth via plain CLI.

## Other findings (not yet acted on, flagged for awareness)

- `.agents/` and `node_modules/` at the repo root remain untracked -- pre-existing, left alone,
  revisit only if asked.
- The scan-authorization consent modal (removed session 8) has never been replaced -- product/
  security gap, not a bug. No UI step confirms scan ownership/permission; not enforced
  server-side either.
- If raw per-finding evidence is ever re-surfaced in the React report UI, port main's dropped
  `finding.evidence || finding.raw_data` preference into that new display logic.
- Local dev venv may be missing `flask_limiter`/`playwright` on a fresh clone despite being in
  `requirements.txt` -- fix is `pip install -r requirements.txt`.

## Links

- Latest daily log: [[2026-08-21]] (session 16)
- Merged PRs: [#6](https://github.com/Zopyrus269/sentinelscan/pull/6) (frontend cleanup + test
  fixes, session 16, merged as `2b7fe76`), [#4](https://github.com/Zopyrus269/sentinelscan/pull/4)
  (Graphify integration, session 15), [#1](https://github.com/Zopyrus269/sentinelscan/pull/1)
  (dhanush-changes security hardening + SSRF fix), [#2](https://github.com/Zopyrus269/sentinelscan/pull/2)
  (PR-required rule)
- Live site: `https://sentinelscan-yd2u.onrender.com` -- Google sign-in confirmed working
  end-to-end as of session 13.
- Render service: `srv-d9rrj6n40ujc73c4efcg`
- `scripts/README.md` -- team secrets bootstrap setup/usage instructions.
- `render.yaml` -- Render deployment Blueprint (repo root); confirmed `branch: main`,
  `autoDeploy: true`.
- Repo collaborators (via GitHub API, session 14): `Zopyrus269` (admin), `Dannyo6`, `sbsai25`,
  `bhuvan-sk`.
