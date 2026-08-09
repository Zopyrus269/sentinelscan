---
type: knowledge-vault-core
last_updated: 2026-08-09
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

- No CI/CD exists (no `.github/workflows`, no other CI config). Testing is manual-only (`pytest tests/`).
- No Docker/docker-compose — no containerization exists.

## Active known issues

None open. The `CLAUDE.md` §9 items (hardcoded JWT in `headless_auth_test.py`, stray empty `LICENSE.md`, README's stale test-count claim) were all resolved 2026-08-09 — see [[2026-08-09]] Pass 6.

## Workflow tooling status (as of 2026-08-07 audit)

- `knowledge-vault` MCP is now correctly scoped to `knowledge/` only (fixed: `.mcp.json` used a relative path that wasn't resolving against the intended root; switched to an absolute path — verified directly against the MCP protocol). The live Claude Code session still needs a reconnect to pick this up; see [[NEXT_TASK]].
- The vault's Obsidian setup previously had two `.obsidian/` directories (repo root and `knowledge/`); the stale root one was removed. `knowledge/` is now the sole, canonical vault root.

## Required reading before architectural changes

`docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/AI_AGENT.md`, `docs/API.md`, `docs/WORKERS.md` — enforced via `CLAUDE.md`.
