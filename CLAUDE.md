# CLAUDE.md

Instructions for Claude Code working on SentinelScan. This file is the entry point — it is read automatically at session start, so it must be self-sufficient: assume zero memory of any prior conversation.

## 1. Project Snapshot

SentinelScan is an AI-driven reconnaissance/assessment tool: Gemini is the only decision-maker, dynamically choosing which of 11 single-purpose "dumb" workers to run next; workers and the report generator contain zero business logic.

Before any architectural or structural change, read:
- `docs/PRD.md` — product requirements, goals, explicit non-goals
- `docs/ARCHITECTURE.md` — system design, data flow, component responsibilities
- `docs/AI_AGENT.md` — agent spec, decision loop, Gemini implementation lessons learned
- `docs/API.md` — REST API spec
- `docs/WORKERS.md` — per-worker input/output contracts

## 2. Safety & Scope Constraints

- **Authorized use only** — SentinelScan is an assessment tool; assume all operations are against explicitly authorized targets.
- **No exploit code** — never write, generate, or suggest active exploit code (payloads, reverse shells, memory corruption scripts). Confine implementation to reconnaissance, vulnerability assessment, and reporting.

## 3. Architectural Principles

- **Dumb workers** — Python workers in `apps/backend/workers/` must never contain business logic, orchestration logic, or state. They execute exactly what they're told and return structured JSON. The AI Agent holds all intelligence and state.
- **Dynamic orchestration** — the AI Agent (`apps/backend/agent/orchestrator.py`) must stay in control of the loop. Do not hardcode sequential scan order.

## 4. Coding & Commit Conventions

- PEP8-compliant Python, type hints (`typing`) on function signatures and non-trivial variables.
- Small, modular functions; concise docstrings for classes and functions.
- Small, atomic, conventional-style commits (e.g. `feat(worker): implement WHOIS parsing logic`).

## 5. Knowledge Vault Protocol

`knowledge/` is the persistent project-memory vault. This protocol is the *only* continuity mechanism relied on — treat it as mandatory, not optional, in every session:

- **Before starting any feature work**, read, in order: `knowledge/NEXT_TASK.md`, `knowledge/PROJECT_CONTEXT.md`, and the most recent file in `knowledge/daily-logs/`. Do this before analyzing the codebase for the task at hand.
- **After implementation is approved, tested, reviewed, and committed**, update the vault before ending the session:
  - Append an entry to `knowledge/daily-logs/YYYY-MM-DD.md` (create the file if today's doesn't exist) covering: what was implemented and why, files changed, architecture/API/DB changes, new endpoints/components, decisions made (cross-link `knowledge/DECISIONS.md` if it warrants a full entry there), bugs fixed, testing performed, current project state, and recommended next steps.
  - Overwrite `knowledge/NEXT_TASK.md` (don't append) to reflect the new current handoff state.
  - If the change is architecturally significant and not yet reflected in the static docs, add a dated delta entry to `knowledge/ARCHITECTURE.md` (never restate `docs/ARCHITECTURE.md` there — deltas only).
- This is reinforced by a `PostToolUse` hook that fires a reminder after every `git commit` (see `.claude/settings.json`) — but the hook is a nudge, not a substitute for actually doing the update. Use the `knowledge-vault` MCP filesystem tools to read/write `knowledge/`, not ad-hoc assumptions about its contents.
- Never write secrets, tokens, or credentials into the vault.

## 6. Planning-Mode-First Workflow

For any new feature request:

1. Read the knowledge vault (section 5) and analyze the existing codebase — understand how the feature fits the current architecture before proposing anything.
2. Enter plan mode. Produce a detailed implementation plan covering:
   - Files to modify, new files required
   - Backend changes
   - Database changes (if applicable)
   - API changes
   - Frontend impact (see section 7 if delegation is needed)
   - Security considerations
   - Testing strategy
   - Deployment considerations
   - Potential risks
3. **No code is written until the user explicitly approves the plan.**

## 7. Frontend Delegation Workflow

After the backend/system plan is approved, if the feature requires frontend work:

- Write a **separate** frontend implementation plan to `knowledge/frontend-plans/<feature-slug>.md`, sized for independent execution by another AI coding agent (Gemini) that has **no access to this conversation** — the file must be fully self-contained, no "as discussed above" references.
- Include: UI components required, user flows, screens/pages affected, state management requirements, API integrations needed, design requirements, expected behavior, edge cases.
- Link the handoff file from the relevant `knowledge/daily-logs/` entry and, while still open, from `knowledge/NEXT_TASK.md`.
- Claude Code's role stops at authoring this plan and coordinating — it does not implement the frontend itself under this workflow. Stay focused on architecture, backend, logic, and coordination.

## 8. Sub-agent Usage Policy

Cost-aware, not agent-happy:

- **Small/simple tasks** — complete directly. Do not spawn agents just because they're available.
- **Large/complex tasks** — evaluate whether parallel agents would help before spawning. When they would, use the built-in Explore agent (codebase search/location), Plan agent (implementation design), or general-purpose agent (multi-step research/execution) — e.g. one agent surveying backend impact, one summarizing test results, one cross-checking documentation consistency.
- No custom `.claude/agents/*.md` are defined for this project at this time (see `knowledge/DECISIONS.md`, 2026-08-07 entry, for why) — rely on the built-in agent types above.

## 9. Known Hygiene Notes

All previously flagged items here were resolved on 2026-08-09 (see `knowledge/daily-logs/2026-08-09.md`, Pass 6): the hardcoded JWT literal was removed from `headless_auth_test.py` in favor of an env-var-supplied token, the stray empty `LICENSE.md` was deleted, and README's test-count claim was corrected to match the actual `pytest tests/` output. No open hygiene items at this time.

## 10. Git Workflow — Pull Request Required for All Merges to `main`

**Permanent, project-scoped rule. No exceptions, including single-line knowledge-vault or doc commits.**

- No commit reaches `main` directly, ever. All work — code, docs, `knowledge/` updates, everything —
  happens on a branch first. Landing on `main` always goes through a GitHub pull request that is
  reviewed and explicitly accepted before merging.
- Applies no matter who or what is doing the merging — Claude Code, the repo owner, or any other
  collaborator. This is enforced both here and via GitHub branch protection on `main` (required PR
  review, `enforce_admins` on, no force-push/delete) — the doc rule and the server-side setting are
  meant to match.
- Workflow: create/checkout a branch → commit there → push the branch → open a PR (`gh pr create` or
  the GitHub MCP `create_pull_request` tool) → wait for it to be reviewed and accepted → merge via
  GitHub (`gh pr merge`, the merge button, or the MCP `merge_pull_request` tool). Never `git merge`
  a branch into a locally checked-out `main` and push that.
- Rationale: forces a human to actually read AI-generated code before it reaches `main`, rather than
  trusting it blindly. See `knowledge/DECISIONS.md`, 2026-08-20 entry.

See `knowledge/PROJECT_CONTEXT.md` for full current-state detail.
