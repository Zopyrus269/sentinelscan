---
type: knowledge-vault-core
last_updated: 2026-08-07
updated_by: claude-code
---

# Decisions

Lightweight, reverse-chronological decision log. Not full ADR ceremony — kept cheap enough to actually maintain. Newest first.

## 2026-08-07: Knowledge vault stays plain markdown, not Obsidian-dependent

**Context:** The repo root was already opened as an Obsidian vault (`.obsidian/` present, untracked, with dataview/obsidian-git/templater plugins installed but no notes). The user wants an "Obsidian-compatible" persistent memory system.

**Decision:** `knowledge/` is plain markdown with minimal YAML frontmatter — useful to Claude Code, grep, and git diff with zero Obsidian dependency, while still rendering nicely inside the existing Obsidian vault for anyone who opens it there.

**Alternatives considered:** Obsidian-specific features (canvas files, complex dataview queries, templater automation) — rejected because they'd make the vault's usefulness contingent on Obsidian being installed, undermining the "usable by a fresh Claude Code session" requirement.

**Consequences:** `.obsidian/` itself is gitignored (local editor state, like `.vscode/`), so the vault's persistence relies entirely on `knowledge/` being tracked in git, not on Obsidian sync.

## 2026-08-07: docs/AGENTS.md kept, not deleted or merged

**Context:** `docs/AGENTS.md` contains agent instructions written for a different AI tool ("Antigravity") — safety constraints and architecture principles that are still correct, now duplicated into `CLAUDE.md`.

**Decision:** Keep `docs/AGENTS.md` as-is, add a one-line pointer at its top noting it's superseded by `CLAUDE.md` for Claude Code sessions.

**Alternatives considered:** Deleting it (rejected — still useful if the repo is used with Antigravity or another tool); merging/deduplicating content across both files (rejected — adds complexity for no real benefit at this scale, two files with a pointer is simpler than one file trying to serve two tools' conventions).

## 2026-08-07: Post-commit vault-update hook is a soft nudge, not a hard gate

**Context:** Requirement 6 needs the knowledge vault updated "automatically" after implementation + test + review + commit. A hook can trigger on `git commit`, but only an LLM turn can write a meaningful summary — and not every commit is feature-complete (some are small fixups).

**Decision:** `PostToolUse` hook on `git commit` injects a reminder into context; Claude judges whether the commit is feature-complete (update the vault) or a minor fixup (acknowledge and skip). Not a hard block.

**Alternatives considered:** Hard gate blocking further action until the vault is updated — rejected as too strict, risks blocking legitimate small commits and creating friction.

## 2026-08-07: No custom `.claude/agents/*.md` at initial setup

**Context:** User wants sub-agent usage to be cost-aware — spawned only when it actually helps, not by default.

**Decision:** Rely on `CLAUDE.md` instructions plus the built-in Explore/Plan/general-purpose agent types. No custom "knowledge-updater" or "frontend-plan-writer" agent defined.

**Alternatives considered:** A custom `knowledge-updater` agent — rejected because vault updates need the main thread's full in-conversation context (code changes, test results, decisions just made); spawning a sub-agent would mean re-deriving that context from scratch, which is strictly more expensive, not less.

**Consequences:** Revisit only if a repeatable, genuinely parallelizable pattern emerges (e.g. a `backend-analyst` agent for pre-plan codebase surveys) that would clearly earn its fixed definition cost.
