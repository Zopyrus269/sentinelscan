---
type: knowledge-vault-core
last_updated: 2026-08-07
updated_by: claude-code
---

# Next Task

This file is always **overwritten**, not appended — it reflects the current handoff state only. Read this first in any new session, before analyzing code.

## What's next

MCP scoping fix for `knowledge-vault` is **complete and live-verified**. All three verification checks passed after a genuine cold restart:
- `list_allowed_directories` → `C:\Dev\SentinelScan-Project\knowledge` only.
- Reading `knowledge/NEXT_TASK.md` through `knowledge-vault` → success.
- Reading `docs/PRD.md` through `knowledge-vault` → access denied.

No setup work is queued. **SentinelScan is ready for real feature development.** Start any new feature request by reading `knowledge/NEXT_TASK.md` (this file), `knowledge/PROJECT_CONTEXT.md`, and the latest `knowledge/daily-logs/` entry, then follow the planning-mode-first workflow in `CLAUDE.md` section 6 (read `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/AI_AGENT.md`, `docs/API.md`, `docs/WORKERS.md` as relevant, enter plan mode, get explicit approval before writing code).

## Why

The user asked for a persistent AI development workflow (planning-gate, frontend delegation to Gemini, cost-aware sub-agents, this knowledge vault, filesystem MCP access, automatic post-commit vault updates) so that returning sessions have full continuity without re-explaining context. The MCP scoping gap turned out to be three-layered: (1) relative-vs-absolute path issue, (2) a package-level MCP roots-protocol override present in versions `2025.8.21+`, (3) a daemon-level subprocess-caching behavior across forked/resumed sessions. All three are now fixed, committed, and confirmed live. See [[ARCHITECTURE]] for the final architecture and [[DECISIONS]] for why each fix was made.

## Blockers

None.

## Other findings (not part of this task, flagged for awareness)

- `~/.claude.json` (user-level, outside this repo) stores a GitHub PAT in plaintext under `mcpServers.github` — recommend rotating and confirming it's not committed anywhere.
- `~/.claude.json` has two case-mismatched project entries (`c:/Dev/SentinelScan-Project` vs `C:/Dev/SentinelScan-Project`), both with empty `mcpServers`/`enabledMcpjsonServers` — latent Windows path-casing bug, worth deduplicating.
- Multiple Claude Code sessions/forks can be running concurrently against this project, each potentially with its own `knowledge-vault` MCP subprocess tree under a shared daemon — always trace process ancestry (parent PID chain up to the owning `claude.exe`) before killing anything, to avoid disrupting a different session.
- During this cleanup pass, `package.json`/`package-lock.json` were found drifted (uncommitted) from the pinned `2025.7.1` to `2025.11.25` — a version re-confirmed to still contain the roots-protocol override. Reverted and reinstalled before committing; no outstanding action needed, but **never bump `@modelcontextprotocol/server-filesystem` without re-running the roots-protocol source audit** described in [[DECISIONS]] first.
- Pre-existing, unrelated, left untouched: `README.md` local modification, untracked `LICENSE.md`, `headless_auth_test.py` hardcoded test JWT — see `CLAUDE.md` section 9.

## Links

- Latest daily log: [[2026-08-07]]
- Open frontend handoff plans: none yet.
