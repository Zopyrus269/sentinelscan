---
type: knowledge-vault-core
last_updated: 2026-08-30
updated_by: claude-code
---

# Project Context

Living "state of the union" for SentinelScan. This file changes as the project evolves — for the unchanging product vision, see `docs/PRD.md`. For the static system design, see `docs/ARCHITECTURE.md` (and [[ARCHITECTURE]] for deltas not yet folded back into it).

## What SentinelScan is

An AI-driven reconnaissance/assessment tool. Gemini is the only decision-maker — it dynamically chooses which of 11 single-purpose "dumb" workers to run next based on prior results, scores findings with CVSS, and triggers report generation. Workers and the report generator contain zero business logic or judgment; all reasoning lives in the Gemini agent layer (`apps/backend/agent/`).

Scope is strictly passive/read-only reconnaissance for explicitly authorized targets — no exploit code, no active attacks.

## Current milestone / phase

Public-release polish. The project started as a college project and is now a working end-to-end platform. Recent commits (as of 2026-08-07) focused on preparing the repo for public release: renaming internal helpers, updating README, adding contributing guidelines and license section, removing internal team attribution.

2026-08-07: set up a persistent Claude Code development workflow (this knowledge vault, `CLAUDE.md`, MCP filesystem access, and an automatic post-commit vault-update nudge), then a same-day audit that found and fixed an MCP scoping gap and a duplicate Obsidian vault root — see [[2026-08-07]].

2026-08-09: synced local `main` with 4 commits of real upstream work it had missed (orchestrator, workers, frontend, tests), then fixed the first round of user-reported bugs from manual testing (dark-mode CSS, an invalid Gemini API key + a stale-process gotcha, dead footer links + 2 missing pages), built a team secrets-bootstrap system, then **deployed the app live** to Render's free tier (`https://sentinelscan-yd2u.onrender.com`, auto-deploying on push to `main`, fully verified end-to-end), and finally cleared every item flagged in `CLAUDE.md` §9. See [[2026-08-09]] (Passes 1–6) and [[NEXT_TASK]].

2026-08-21: **new milestone started -- the observability project.** A recording layer inside the main app plus a second, developer-only status/log website, so a vague user bug report can be answered by reading that person's actual session instead of re-reading code. Split into three parallel workstreams: A (Sanjana) `apps/backend/observability/`, B (Shreyas) `apps/backend/logstore/`, C (Danny) `apps/logsite/`. Shreyas integrates. Design and handoff documentation only as of this date -- no code written yet. See `docs/workstreams/WORKSTREAM_A.md`, `docs/workstreams/WORKSTREAM_C.md`, [[ARCHITECTURE]]'s 2026-08-21 delta, and [[2026-08-21]] session 18.

2026-08-22: Workstream B (ours) split into 4 phases; **Phase 1 implemented** -- the storage & pipeline backbone (`apps/backend/logstore/schema.py`, `sink.py`, `firestore_sink.py`, `stdout_sink.py`), 20 new tests, 164 passed/1 skipped overall. Open as PR #10 into a new durable `workstream-b-pipeline` branch, awaiting the user's review/merge under a new personal PR-review habit (see [[DECISIONS]] 2026-08-22). Phases 2-4 (ingest endpoint + browser client, read API + rollup, seed data) remain. See [[2026-08-22]] session 19 and [[NEXT_TASK]].

2026-08-24: Workstream B feature-complete at all 4 phases; a branch-wide code review found 19 issues, all closed across two PRs, plus a JS test suite added for `telemetry.js` (25 tests, no framework installed). `workstream-b-pipeline` @ `9effb88`. See [[2026-08-24]] sessions 24-25 and [[NEXT_TASK]].

2026-08-29: **branch-integration Phase 1 complete** -- each of the three workstream branches reviewed and fixed independently (by hand, no automated review skill, after an early attempt at using one turned out to itself be an unapproved subagent spawn). Workstream A (now `fix/telemetry-concurrency`, Sanjana having replaced `workstream-a-handoff`) and Workstream C (`workstream-c-`) each got one small PR of fixes, both merged. Workstream B was reverified with no new issues. Phase 2 (combine all three into one integration branch) and Phase 3 (merge that into `main`) remain. See [[2026-08-29]] session 26 and [[NEXT_TASK]].

2026-08-29 (same day): **branch-integration Phase 2 complete** -- new local branch `integration/observability` now carries all three workstreams' code together for the first time, and one real cross-branch bug was found and fixed: Workstream A's recorded events (http/error/agent/worker/llm) had nowhere to go, since its own queue and Workstream B's sink thread's queue were two separate objects until this session unified them. Both branches' own code comments had already described this as expected, deferred integration work. Verified end-to-end with a new cross-branch test file plus a live local run, not just by inspection. Also fixed a docstring that would have misled a future session into an unsafe "cleanup," added a privacy-disclosure sentence the user explicitly asked for, and confirmed a previously-flagged Firestore-index mismatch was already resolved days before it was flagged (a stale vault note, now corrected). See [[2026-08-29]] session 27, [[DECISIONS]], and [[NEXT_TASK]].

2026-08-30: **the observability project is complete -- branch-integration Phase 3 merged `integration/observability` into `main`.** Closed out the 5-item live-verification checklist Phase 2 had deferred: confirmed cross-thread trace propagation against a real scan (not just code review), discovered and fixed two production infrastructure gaps that had nothing to do with the code being wrong (the three Firestore composite indexes the read API needs were never actually deployed, and `SENTINELSCAN_TELEMETRY_ENABLED` had never synced to the Render dashboard despite being in `render.yaml`), built and ran a delete-then-reseed tool for the demo data sitting in production (also surfacing that the original 2026-08-09 seed run had likely overwritten some real uptime-probe history, a loss the user chose to accept rather than chase). PR #19 merged by the user (`0cb41be`), verified via `gh pr view` rather than taken on their word. `docs/AGENTS.md` (held since session 25) and a full Graphify regeneration (now covering all three workstreams for the first time) landed afterward on their own short branch/PR. **Standing rule 1 (don't push `knowledge/`/`graphify-out/`) is lifted as of this session** -- `main` is the only branch now. See [[2026-08-30]] session 28, [[DECISIONS]], [[ARCHITECTURE]], and [[NEXT_TASK]].

## What works end-to-end today

- Flask backend (`apps/backend/app.py`) with blueprints for auth, scans, and history (`apps/backend/routes/`).
- Gemini-driven orchestration loop (`apps/backend/agent/orchestrator.py`, `gemini_client.py`) dispatching to 11 workers via `worker_dispatch.py`.
- 11 workers: Reverse DNS, DNS, WHOIS, Port Scanner (nmap with TCP-connect fallback), SSL Check, HTTP Headers, Cookies, Sitemap, robots.txt, CVSS Scoring, Report Generator (PDF via reportlab + JSON).
- Active-scan state is an in-memory, per-process store (`apps/backend/models/scan_store.py`); completed-scan history persists to Firestore (`apps/backend/models/history_store.py`), with the in-memory store as a local-dev fallback when Firebase isn't configured. `DATABASE_URL`/SQLite is not used anywhere in the app (confirmed 2026-08-09, fully removed from docs/scripts).
- Firebase Admin auth (`apps/backend/auth/`).
- Plain HTML/CSS/JS frontend (`apps/frontend/`) — dashboard, report viewer, status, terms/privacy/documentation pages. No JS framework, no build step, no `package.json` anywhere in the repo.
- pytest suite: run via `pytest tests/` (not `unittest discover`, which silently skips the pytest-style files) — 137 passed, 1 skipped as of 2026-08-09.
- **Deployed and live**: `https://sentinelscan-yd2u.onrender.com` (Render free tier, single gunicorn worker — required, not optional, since the active-scan store above is per-process — auto-deploys on push to `main`).

## What's stubbed / incomplete / worth knowing

- CI is minimal: `.github/workflows/secret-scanning.yml` (Gitleaks) is the only workflow. No test/lint/deploy pipeline -- testing is manual (`pytest tests/`). The observability project adds a second workflow, a 5-minute uptime probe.
- No Docker/docker-compose — no containerization exists.

## Active known issues

None open. The `CLAUDE.md` §9 items (hardcoded JWT in `headless_auth_test.py`, stray empty `LICENSE.md`, README's stale test-count claim) were all resolved 2026-08-09 — see [[2026-08-09]] Pass 6.

## Workflow tooling status (as of 2026-08-07 audit)

- `knowledge-vault` MCP is now correctly scoped to `knowledge/` only (fixed: `.mcp.json` used a relative path that wasn't resolving against the intended root; switched to an absolute path — verified directly against the MCP protocol). The live Claude Code session still needs a reconnect to pick this up; see [[NEXT_TASK]].
- The vault's Obsidian setup previously had two `.obsidian/` directories (repo root and `knowledge/`); the stale root one was removed. `knowledge/` is now the sole, canonical vault root.

## Required reading before architectural changes

`docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/AI_AGENT.md`, `docs/API.md`, `docs/WORKERS.md` — enforced via `CLAUDE.md`.
