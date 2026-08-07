---
type: knowledge-vault-core
last_updated: 2026-08-07
updated_by: claude-code
---

# Architecture Deltas

This file holds only **changes since** `docs/ARCHITECTURE.md` — it never restates the static doc. If a change here becomes permanent/stable, it's still logged here (not deleted); reconciling it back into `docs/ARCHITECTURE.md` is a separate, deliberate editorial decision, not automatic.

Each entry: date, what changed, why, where.

## 2026-08-07: Knowledge vault + Claude Code workflow added

- Added `knowledge/` (this vault), `CLAUDE.md`, `.mcp.json` (filesystem MCP server scoped to `knowledge/`), and `.claude/settings.json` (MCP permissions + post-commit reminder hook).
- No changes to `apps/backend/` or `apps/frontend/` runtime behavior — this is tooling/process only.
- See `knowledge/daily-logs/2026-08-07.md` for full detail and `knowledge/DECISIONS.md` for the design decisions made along the way.
