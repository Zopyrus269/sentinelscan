---
type: knowledge-vault-core
last_updated: 2026-08-07
updated_by: claude-code
---

# Architecture Deltas

This file holds only **changes since** `docs/ARCHITECTURE.md` — it never restates the static doc. If a change here becomes permanent/stable, it's still logged here (not deleted); reconciling it back into `docs/ARCHITECTURE.md` is a separate, deliberate editorial decision, not automatic.

Each entry: date, what changed, why, where.

## 2026-08-07: Knowledge vault + Claude Code workflow added

- Added `knowledge/` (this vault), `CLAUDE.md`, `.mcp.json` (filesystem MCP server intended to be scoped to `knowledge/`), and `.claude/settings.json` (MCP permissions + post-commit reminder hook).
- No changes to `apps/backend/` or `apps/frontend/` runtime behavior — this is tooling/process only.
- See [[2026-08-07]] for full detail and [[DECISIONS]] for the design decisions made along the way.

## 2026-08-07: MCP filesystem scoping bug fixed (same-day audit)

- The `.mcp.json` entry for `knowledge-vault` used a relative path (`./knowledge`) which did not resolve correctly against the cwd Claude Code's MCP client actually spawns with — the server was exposing the entire repo, not just `knowledge/`. Confirmed via `list_allowed_directories` returning the repo root and a successful read of `docs/PRD.md` through the tool.
- Fixed by switching the arg to an absolute path (`C:/Dev/SentinelScan-Project/knowledge`), which is immune to spawn-cwd ambiguity. Verified directly against the MCP protocol (raw `tools/call` to a manually spawned instance of the server): `list_allowed_directories` now returns only `knowledge/`, reads of `docs/PRD.md` are denied, reads of files under `knowledge/` succeed.
- The live Claude Code session's MCP connection was established before this fix and needs a reconnect to inherit it — see [[NEXT_TASK]].

## 2026-08-07: MCP filesystem scoping bug — actual root cause was package roots-override, not stale config (superseding the entry above)

- The absolute-path fix above did not actually resolve the scoping bug. Real cause: `@modelcontextprotocol/server-filesystem` versions `2025.8.21` onward implement the MCP **roots protocol** — on client connect, if the client advertises roots support, the server overwrites its CLI-arg-configured `allowedDirectories` with the client-reported root list. Claude Code advertises roots support and reports the whole project as its root, so the `knowledge/`-scoped arg was being discarded on every connection regardless of the path being absolute or relative, and regardless of session restarts.
- Fixed by pinning `.mcp.json`'s `knowledge-vault` server to `@modelcontextprotocol/server-filesystem@2025.7.1`, the last version confirmed (via source audit) to have no roots-handshake code. See [[DECISIONS]] for the version-audit methodology and alternatives considered.
- Live in-session verification against the pinned version is pending a user-initiated session restart — see [[NEXT_TASK]].

## 2026-08-07: MCP subprocess lifecycle — daemon caches server instances across forked/resumed sessions

- This environment's Claude Code process tree is a persistent daemon (`claude.exe daemon run --origin transient`) hosting one or more `--fork-session --resume <transcript>.jsonl` sessions. A "restart" that goes through fork/resume does **not** cause the daemon to re-read `.mcp.json` or spawn a new `knowledge-vault` subprocess — it hands the resumed session the same subprocess instance that was already running, stale config and all.
- Consequence for this specific bug: both the absolute-path fix and the version-pin fix were correct on disk well before they were confirmed live, because no fork/resume in between actually exercised the corrected config.
- Killing a session's own MCP subprocess (traced via full parent-PID ancestry to avoid hitting a different session's tree) reliably disconnects it but does **not** trigger a respawn — consistent with the earlier-documented finding that this client only spawns MCP servers once per process lifetime.
- Only a genuine cold start (full exit and relaunch of the Claude Code application/CLI, not a fork/resume) causes a fresh process to read `.mcp.json` from scratch and spawn a correctly-configured subprocess. See [[NEXT_TASK]] for outstanding verification.

## 2026-08-07: Final MCP architecture — locally pinned filesystem server, no npx (verified working)

- `knowledge-vault` in `.mcp.json` now runs `node ./node_modules/@modelcontextprotocol/server-filesystem/dist/index.js C:/Dev/SentinelScan-Project/knowledge` — a `devDependency`-pinned local install invoked directly, no `npx`. See [[DECISIONS]] for why.
- This closes both known failure modes together: the absolute path arg removes spawn-cwd ambiguity, and pinning to `2025.7.1` (confirmed roots-handshake-free by source audit) removes the MCP roots-protocol override present in `2025.8.21+` that otherwise silently widens `allowedDirectories` to the client's reported workspace root on every connect.
- Live-verified end-to-end after a genuine cold restart (2026-08-07): `list_allowed_directories` → `C:\Dev\SentinelScan-Project\knowledge` only; `knowledge/NEXT_TASK.md` read → success; `docs/PRD.md` read → access denied.
- This closes out the MCP scoping saga tracked across the entries above. See [[NEXT_TASK]] for current state (setup complete, ready for feature work).
