---
type: knowledge-vault-core
last_updated: 2026-08-07
updated_by: claude-code
---

# Project Context

Living "state of the union" for SentinelScan. This file changes as the project evolves — for the unchanging product vision, see `docs/PRD.md`. For the static system design, see `docs/ARCHITECTURE.md` (and [[ARCHITECTURE]] for deltas not yet folded back into it).

## What SentinelScan is

An AI-driven reconnaissance/assessment tool. Gemini is the only decision-maker — it dynamically chooses which of 11 single-purpose "dumb" workers to run next based on prior results, scores findings with CVSS, and triggers report generation. Workers and the report generator contain zero business logic or judgment; all reasoning lives in the Gemini agent layer (`apps/backend/agent/`).

Scope is strictly passive/read-only reconnaissance for explicitly authorized targets — no exploit code, no active attacks.

## Current milestone / phase

Public-release polish. The project started as a college project and is now a working end-to-end platform. Recent commits (as of 2026-08-07) focused on preparing the repo for public release: renaming internal helpers, updating README, adding contributing guidelines and license section, removing internal team attribution.

This session's work: setting up a persistent Claude Code development workflow (this knowledge vault, `CLAUDE.md`, MCP filesystem access, and an automatic post-commit vault-update nudge), followed same-day by a workflow audit that found and fixed an MCP scoping gap and a duplicate Obsidian vault root — see [[2026-08-07]].

## What works end-to-end today

- Flask backend (`apps/backend/app.py`) with blueprints for auth, scans, and history (`apps/backend/routes/`).
- Gemini-driven orchestration loop (`apps/backend/agent/orchestrator.py`, `gemini_client.py`) dispatching to 11 workers via `worker_dispatch.py`.
- 11 workers: Reverse DNS, DNS, WHOIS, Port Scanner (nmap with TCP-connect fallback), SSL Check, HTTP Headers, Cookies, Sitemap, robots.txt, CVSS Scoring, Report Generator (PDF via reportlab + JSON).
- SQLite-backed scan storage and history (`apps/backend/models/`).
- Firebase Admin auth (`apps/backend/auth/`).
- Plain HTML/CSS/JS frontend (`apps/frontend/`) — dashboard, report viewer, status, terms/privacy/documentation pages. No JS framework, no build step, no `package.json` anywhere in the repo.
- pytest suite: 18 test files under `tests/`, run via `pytest tests/` (not `unittest discover`, which silently skips the pytest-style files).

## What's stubbed / incomplete / worth knowing

- Database is SQLite by design, explicitly noted in `docs/ARCHITECTURE.md` as intended to be swappable to PostgreSQL later — not yet done.
- No CI/CD exists (no `.github/workflows`, no other CI config). Testing is manual-only (`pytest tests/`).
- README claims "123 tests" but a raw `def test_` count across `tests/*.py` comes to 99 — likely explained by `pytest.mark.parametrize` expansion, not independently verified by actually running the suite.
- No Docker/docker-compose — no containerization exists.

## Active known issues (flagged, not yet fixed — see CLAUDE.md "Known Hygiene Notes")

- `headless_auth_test.py` is tracked in git and contains a hardcoded Firebase custom-auth JWT literal (looks like a dev/test token, `uid: test-uid-playwright-001`, not a production credential, but still a committed secret-shaped string worth reviewing/rotating).
- A stray empty (0-byte) `LICENSE.md` sits untracked at repo root alongside the real tracked `LICENSE` (MIT) — likely an accidental artifact from the public-release prep commits.
- `README.md` has an uncommitted local modification as of 2026-08-07 (pre-dates this session's work, not investigated).
- README test-count mismatch noted above.

None of the above were touched as part of the AI-workflow setup or its audit — see [[2026-08-07]] for why.

## Workflow tooling status (as of 2026-08-07 audit)

- `knowledge-vault` MCP is now correctly scoped to `knowledge/` only (fixed: `.mcp.json` used a relative path that wasn't resolving against the intended root; switched to an absolute path — verified directly against the MCP protocol). The live Claude Code session still needs a reconnect to pick this up; see [[NEXT_TASK]].
- The vault's Obsidian setup previously had two `.obsidian/` directories (repo root and `knowledge/`); the stale root one was removed. `knowledge/` is now the sole, canonical vault root.

## Required reading before architectural changes

`docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/AI_AGENT.md`, `docs/API.md`, `docs/WORKERS.md` — enforced via `CLAUDE.md`.
