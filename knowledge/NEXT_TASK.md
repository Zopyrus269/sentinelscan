---
type: knowledge-vault-core
last_updated: 2026-08-30
updated_by: claude-code
---

# Next Task

This file is always **overwritten**, not appended -- it reflects the current handoff state only.
Read this first in any new session, before analyzing code.

## What's next

**The observability project is complete.** `integration/observability` merged into `main` via
PR [#19](https://github.com/Zopyrus269/sentinelscan/pull/19) (`0cb41be`), closing out the 3-phase
branch-integration plan (Phase 1: per-branch review, session 26; Phase 2: combine + cross-branch
fix, session 27; Phase 3: live-checklist + final merge, session 28). No open task from this
project remains. **No active task is queued for the next session** -- start from whatever the
user asks for, informed by the sections below.

- `main` @ `0cb41be` is the only branch that matters now. `workstream-b-pipeline`,
  `fix/telemetry-concurrency`, `workstream-c-`, and `integration/observability` are all
  superseded by it -- none deleted (not asked to); worth cleaning up local/remote refs next time
  someone's doing branch housekeeping, but not urgent.
- Full session-28 narrative (what was checked, what was found, what was fixed) is in
  [[2026-08-30]]. The judgment calls made along the way (the `uptime/` data-loss decision, the
  `stats/` scoping decision) are in [[DECISIONS]]. The merge's architectural summary is in
  [[ARCHITECTURE]].
- **Standing rule 1 (don't push `knowledge/`/`graphify-out/`) is lifted as of this session** --
  see the standing-rules section below. This file, and everything else in `knowledge/`, is
  committed and pushed normally again from now on.

### If someone asks about the demo data or the log site

Production Firestore (`sentinelscan-3f82d`) now has fresh, correctly-timestamped demo data across
`logs`/`presence`/`logs_hourly`/`logs_meta`/`uptime`/`stats`, reseeded by
`scripts/reset_demo_logs.py` (new this session, companion to `scripts/seed_fake_logs.py`) and
confirmed queryable via the real read API. The three composite indexes
`apps/backend/logstore/firestore.indexes.json` declares are live and `Enabled` in the Firestore
console (they never had been before this session, despite being declared in the repo since
Workstream B's Phase 3). `SENTINELSCAN_TELEMETRY_ENABLED` is `"0"` in both `render.yaml` and the
actual Render dashboard (it had never synced to the dashboard before this session either).
Telemetry is still off in production -- turning it on is a separate, deliberate decision nobody
has made yet.

### Side task, unrelated to the branch integration: Antigravity PR Review Explainer

`docs/AGENTS.md` gained a "Side Task: PR Review Explainer Mode" section (committed this session,
session 25's instructions, held uncommitted on purpose until final integration) -- the user runs
Antigravity CLI (Google AI Pro) in a second terminal alongside this one, says a trigger phrase
like `"analyze the PR"`, and Antigravity walks them through the PR's diff in plain language before
they review/merge on GitHub themselves. Read-only against GitHub, explicitly forbidden from
touching the local working tree. Used for real in session 26 (PRs #17, #18) and again this session
for PR #19.

---

## Known gaps, flagged not fixed

- The scan-authorization consent modal (removed session 8) has never been replaced -- a
  product/security gap, not a bug. No UI step confirms scan ownership, and it was never enforced
  server-side either.
- If raw per-finding evidence is ever re-surfaced in the React report UI, port `main`'s dropped
  `finding.evidence || finding.raw_data` preference into that new display logic.
- A fresh clone's venv may be missing `flask_limiter`/`playwright` despite `requirements.txt` --
  fix is `pip install -r requirements.txt`.
- `apps/logsite/api.py` and `probe.py` use an unusual one-argument-per-line formatting style
  throughout (~1,200 lines). Valid, doesn't affect behavior, deliberately not reformatted in
  session 26 to avoid burying real fixes in a huge whitespace diff. Worth a dedicated pass if
  Danny doesn't get to it first.
- No real code path emits `category="scan"` or `category="worker"` events (found session 28,
  grepping for both turned up nothing) -- only `http`/`agent`/`llm` are ever actually recorded.
  The fake seed data and some design docs use all five categories; harmless today, but worth
  reconciling if anyone extends the recorder or trusts the docs' category list at face value.

## Known CLI/registry-access gotchas (React Bits / Skiper UI)

- **React Bits (`@react-bits/*`):** `npx shadcn@latest add @react-bits/<name>` fails with
  `Unexpected token (1:0)` for most items -- fetch `https://reactbits.dev/r/<name>.json`
  directly and place files manually.
- **Skiper UI (`@skiper-ui/*`):** works via plain CLI for free items; numbered Pro items 401.
- **21st.dev registry items are auth-gated** -- try `@aceternity/<slug>` first (same slug,
  usually zero-auth). **Aceternity (`@aceternity/*`)** works with zero auth via plain CLI.

---

## Standing rules (apply to all future sessions)

### 1. `knowledge/` and `graphify-out/` are committed and pushed normally again

**Lifted 2026-08-30**, having been in force from 2026-08-21 while the observability project's
three workstreams lived on separate branches (the risk was divergent copies at merge time, since
Danny and Sanjana's own branches carried their own vault writes). `main` is now the only branch,
so that risk no longer applies. Write vault updates as part of the normal commit/PR flow like any
other change -- no special holding-back.

### 2. The PR-to-`main` rule has an explicit scope

`CLAUDE.md` §10 (every merge to `main` goes through a PR, including knowledge-vault-only commits)
**applies to everyone who commits to this repo**. The one carve-out: Danny and Sanjana commit and
push to their own branches freely -- no PR, no review gate, no approval, until whatever they're
doing needs to reach `main`. The convention that applies to absolutely everyone: no
`Co-Authored-By: Claude` trailer on any commit.

### 3. Fixes to a teammate's own branch land via PR into that branch, confirmed before moving on

When work on this repo touches **any** branch that isn't `main` -- including Sanjana's and
Danny's -- fixes go on a short-lived sub-branch, PR'd into that branch (not `main`), and the user
reviews/merges it themselves (using their Antigravity PR-explainer setup in a second terminal)
before work on the next branch starts. **Each merge is verified via `gh pr view` / `git log`,
never assumed from the user's word alone** -- this has caught a stale assumption more than once
(session 26, and implicitly guarded against again in session 28). Delete the sub-branch local +
remote once merged, and `git fetch --prune` before starting the next branch's worktree.

### 4. Live Firebase credentials are configured on this machine

This machine's local `.env` has real Firebase credentials, so `get_db()` returns a **live client
against the production project** by default.

- **Always mock `get_db`** (or the specific function calling it) in any new test touching
  `apps/backend/logstore/**` or `apps/backend/auth/firebase_client.py`. Every existing test in
  this suite does.
- Before any manual verification that could write telemetry/history/scan data, override
  `FIREBASE_SERVICE_ACCOUNT_PATH` to a nonexistent path for that one process (forces `get_db()`
  to return `None`, no `.env` file touched) so it falls back to the stdout/local sink. Used
  successfully this session for the local live-scan verification (checklist item 4).
- The reverse also applies deliberately: `scripts/seed_fake_logs.py` and
  `scripts/reset_demo_logs.py` are meant to target the live project, always print which project
  they're about to touch, and always require `--confirm` (or an interactive y/N) before writing
  or deleting anything. `reset_demo_logs.py` additionally does a read-only count first, always
  shown, before any deletion.

### 5. Other standing rules, unchanged

- **Never spawn a subagent without asking first and stating the reason -- including a Skill that
  itself launches as a forked/background execution**, not just literal `Agent` tool calls.
- **Never call Claude-in-Chrome tools without explicit approval**, re-asked for each new need --
  including for each *new kind* of action within an already-approved session, e.g. session 28's
  original approval covered only looking at two dashboards; creating Firestore indexes and adding
  a Render env var were each asked for separately once the need became concrete.
- **Never write to `knowledge/` while implementation is in progress** -- read-only during active
  work; writes only after everything is implemented, tested and committed.
- **When presenting a plan or asking the user to choose**, explain it in plain, non-technical
  language first (what the situation is, what each choice means, the real trade-off). Global
  rule, all projects.
- **Every SentinelScan plan states whether Graphify was used and how it helped**, or why not and
  what was used instead. `CLAUDE.md` §6.
- **Graphify read side is free** -- reach for `graphify affected` / `query` / `path` / `explain`
  on structural questions before a grep-and-read sweep. `affected` (reverse traversal) is the
  most reliable; `query`'s forward BFS is noisy for dead-code checks, where Grep still wins.
  Regenerate only at session end with
  `GRAPHIFY_NO_BACKUP=1 graphify extract . --code-only --force` then
  `GRAPHIFY_NO_BACKUP=1 graphify label . --backend=claude-cli --max-concurrency=1` -- never
  `graphify update .`. **Always** set `GRAPHIFY_NO_BACKUP=1`, or a redundant dated backup folder
  gets written. **Regenerated 2026-08-30** -- now covers all three former workstreams (1820
  nodes, 3344 edges, 121 communities), first time it's reflected anything beyond `main` +
  `workstream-b-pipeline`.
- **Always run the local dev server as `http://localhost:5000`** (Firebase authorized domains
  cover `localhost` and the Render domain only). Two-step startup: `npm run build` in
  `apps/frontend/react-app`, then `python -m apps.backend.app` from repo root -- though a
  backend-only check (no UI involved) can skip the frontend build, as session 28 did for the
  live-scan verification.
- **Render deploys must run a single gunicorn worker** (`scan_store.py`'s active-scan state is
  in-memory per-process -- and `firestore_sink.py`'s session de-duplication now assumes it too).
  Confirmed still true after session 28's env-var-triggered redeploy: `WEB_CONCURRENCY=1`,
  `--workers 1`.
- **Never commit `scripts/oauth_client.json`**, any real secret-shaped file, or a hardcoded
  token/JWT literal.
- **When CSP changes touch auth or third-party embeds, verify live end-to-end**, not just
  headers.
- Real contact address is `sentinelscan@gmail.com`.
- **The GitHub MCP token lacks PR-creation scope** -- use `gh pr create` / `gh pr edit` via Bash.
  No MCP tool exposes branch protection either; use
  `gh api -X PUT repos/{owner}/{repo}/branches/{branch}/protection`.
- **`SplashCursor.jsx` is a hand-modified fork, not vendor-verbatim** -- re-running its own
  `shadcn add` command would silently clobber the modifications.
- **This repo has no Firebase CLI, no `gcloud`, and no `google-cloud-firestore-admin` client** --
  confirmed session 28. Firestore index management has to go through the console UI (or Chrome
  automation with per-use approval) until one of those gets installed; don't assume `firebase
  deploy --only firestore:indexes` works without checking first.

---

## Project state as of session 28

- `main` @ `0cb41be` -- the observability project fully merged, PR #19. Live at
  `https://sentinelscan-yd2u.onrender.com`.
- `chore/observability-integration-wrapup` (pushed, PR not yet opened as of this file being
  written -- opened immediately after, see the daily log) carries `docs/AGENTS.md` and the
  Graphify regeneration on top of the merged `main`.
- Production Firestore (`sentinelscan-3f82d`): three composite indexes live and `Enabled`; demo
  data reseeded fresh and confirmed queryable. See [[2026-08-30]] for exact counts.
- Render (`srv-d9rrj6n40ujc73c4efcg`): `SENTINELSCAN_TELEMETRY_ENABLED="0"` now present and
  redeployed successfully.
- `pytest tests/` on `main`: 314 passed, 1 skipped. `npm run test:js`: 25 passed.
- `graphify-out/` regenerated 2026-08-30, covers all three former workstreams.
- Untracked at repo root, pre-existing, left alone: `.agents/`, `node_modules/`.

## Links

- **Session 28 (this session):** [[2026-08-30]] -- full Phase 3 narrative.
- **Branch reviews from session 26:** [[workstream-a-code-review-2026-08-29]],
  [[workstream-c-code-review-2026-08-29]], reverification addendum in
  [[workstream-b-code-review-2026-08-23]]
- **Workstream handoffs (historical, on `main`):** `docs/workstreams/WORKSTREAM_A.md` (Sanjana),
  `docs/workstreams/WORKSTREAM_C.md` (Danny)
- Prior daily logs: [[2026-08-29]] (sessions 26-27), [[2026-08-24]] (sessions 24-25),
  [[2026-08-23]] (sessions 22-23), [[2026-08-22]] (sessions 19-21),
  [[2026-08-21]] (sessions 16-18)
- Session 26 plan: `C:\Users\ADMIN\.claude\plans\right-now-in-the-graceful-coral.md`. Session 27
  plan: `C:\Users\ADMIN\.claude\plans\let-s-proceed-with-the-inherited-magpie.md`. Session 28
  plan: `C:\Users\ADMIN\.claude\plans\let-s-implement-the-last-nifty-rabin.md`
- Merged PRs: [#19](https://github.com/Zopyrus269/sentinelscan/pull/19) (branch integration,
  final merge into `main`; `0cb41be`), [#18](https://github.com/Zopyrus269/sentinelscan/pull/18)
  (Workstream C Phase 1 fixes; `cabd841`), [#17](https://github.com/Zopyrus269/sentinelscan/pull/17)
  (Workstream A Phase 1 fix; `dc13821`), [#16](https://github.com/Zopyrus269/sentinelscan/pull/16)
  (JS test suite for `telemetry.js`; `9effb88`), [#15](https://github.com/Zopyrus269/sentinelscan/pull/15)
  (review fixes: read cost, ordering, deployment config, C4; `00daf3f`),
  [#14](https://github.com/Zopyrus269/sentinelscan/pull/14) (review fixes: correctness and
  production bugs; `d6ef21f`), [#13](https://github.com/Zopyrus269/sentinelscan/pull/13)
  (Phase 4 seed data; `e073d35`), [#12](https://github.com/Zopyrus269/sentinelscan/pull/12)
  (Phase 3 read API + rollup; `a24860b`), [#11](https://github.com/Zopyrus269/sentinelscan/pull/11)
  (Phase 2 ingest endpoint; `703b85e`), [#10](https://github.com/Zopyrus269/sentinelscan/pull/10)
  (Phase 1 storage backbone; `7a02649`), [#9](https://github.com/Zopyrus269/sentinelscan/pull/9)
  (observability handoff docs; `1e98e80`), [#8](https://github.com/Zopyrus269/sentinelscan/pull/8)
  (graphify backup hygiene), [#6](https://github.com/Zopyrus269/sentinelscan/pull/6) (frontend
  cleanup + test fixes; `2b7fe76`), [#4](https://github.com/Zopyrus269/sentinelscan/pull/4)
  (Graphify integration), [#1](https://github.com/Zopyrus269/sentinelscan/pull/1) (security
  hardening + SSRF fix), [#2](https://github.com/Zopyrus269/sentinelscan/pull/2) (PR-required
  rule)
- Live site: `https://sentinelscan-yd2u.onrender.com`. Render service: `srv-d9rrj6n40ujc73c4efcg`.
- `render.yaml` -- Render deployment Blueprint (repo root); `branch: main`, `autoDeploy: true`.
- Repo collaborators: `Zopyrus269` (admin, Shreyas), `Dannyo6`, `sbsai25`, `bhuvan-sk`.
  Workstream owners are Sanjana (A, GitHub handle `sbsai25`) and Danny (C, commits show as
  "Dhanush V").
