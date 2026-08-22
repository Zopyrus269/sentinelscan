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
   - **Graphify usage** (new 2026-08-22): state whether Graphify (section 11) was used while
     researching this plan. If used, say which query/path/explain/affected/god-nodes calls
     were run and specifically how they helped — e.g. what token-costly grep-and-read sweep
     they replaced, or what design choice they informed. If not used, say so plainly and name
     what was used instead (e.g. direct file reads, a specific Grep) and why that fit better
     for this particular plan. Every plan states one of these two outcomes, with a reason —
     never omit the section.
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
  happens on a branch first. Landing on `main` always goes through a GitHub pull request; a direct push
  to `main` is blocked outright by branch protection (`enforce_admins` on, so this applies to the repo
  owner too, not just other collaborators).
- Required approving reviews on `main` are set to **0**, not 1 — GitHub hard-blocks a PR author from
  approving their own PR (no setting overrides this), and since the sole repo owner opens most PRs
  under their own account, requiring 1 approval would make those PRs permanently unmergeable. The
  control that matters here is "a PR must exist and be manually merged," not "someone else approved
  it" — the owner opening the PR, reading the diff, and clicking merge themselves satisfies the actual
  goal (see `knowledge/DECISIONS.md`, 2026-08-20 entries). If another collaborator opens a PR, they're
  welcome to request/receive a real review from someone else before merging — nothing here prevents
  that, it's just not force-required by GitHub.
- Workflow: create/checkout a branch → commit there → push the branch → open a PR (`gh pr create` or
  the GitHub MCP `create_pull_request` tool — the GitHub MCP token has been observed to lack
  PR-creation scope, so `gh pr create` is the reliable path) → read the diff → merge via GitHub
  (`gh pr merge`, the merge button, or the MCP `merge_pull_request` tool). Never `git merge` a branch
  into a locally checked-out `main` and push that.
- Rationale: forces a human to actually read AI-generated code before it reaches `main`, rather than
  trusting it blindly — a habit, not a gate that needs a second person.

## 11. Graphify — code structure layer

`graphify-out/` holds a code-only structural graph (imports, calls, classes — via local AST parsing, no LLM) built by [Graphify](https://github.com/Graphify-Labs/graphify). It is a **separate layer from `knowledge/`**: `knowledge/` is WHY/intent/history (manual, human-curated); `graphify-out/` is WHAT exists/WHERE/HOW it connects (automatic, code-only). Scope is permanently code-only (`apps/backend/`, `apps/frontend/`, `scripts/`, `tests/`) — `knowledge/`, `docs/`, `.agents/`, `.claude/`, `secrets/` and generated/runtime output are hard-excluded via `.graphifyignore`, so Graphify never needs to spawn subagents (which would otherwise require the per-instance approval required by the global Subagent policy).

**Read side — automatic, no approval needed.** During any build task, freely run `graphify query "<question>"`, `graphify path "<A>" "<B>"`, or `graphify explain "<concept>"` against `graphify-out/graph.json` (when it exists) to understand code structure before editing — cheaper and more targeted than a grep-and-read sweep. Treat its answers as a starting point, not gospel: verify against the actual file before editing, since the graph can lag behind the latest edits.

**Write side — session-end only, same rule as the knowledge vault.** Any regeneration of `graphify-out/` is **never** run mid-task or after every prompt — only when the user signals the session is wrapping up, batched together with the (separate, still-on-explicit-request-only) knowledge base update above. Reasoning: a session may add and remove features repeatedly before settling, so refreshing the graph after every intermediate step wastes cycles and defeats the point of using it to cut tokens.

**Regenerate with `GRAPHIFY_NO_BACKUP=1 graphify extract . --code-only --force`, not `graphify update .`.** `update` has **no** `--code-only` flag — it re-extracts whatever the manifest already holds, so it cannot narrow scope and would let excluded paths back into the graph. Then name the clusters with `GRAPHIFY_NO_BACKUP=1 graphify label . --backend=claude-cli --max-concurrency=1`; there is no `GEMINI_API_KEY`/`GOOGLE_API_KEY` on this machine, and the local CLI backend needs neither. Afterwards **verify the scope held**: no node's `source_file` should be a `.md` or live under `.agents/`, `.claude/`, `docs/`, `knowledge/` or `secrets/`.

**Always set `GRAPHIFY_NO_BACKUP=1` on `extract`/`label`.** Graphify's `backup_if_protected()` (fires whenever the graph has real LLM-assigned community labels, which ours does) snapshots the entire `graph.json` + friends into a dated `graphify-out/YYYY-MM-DD/` subfolder before every overwrite — a full duplicate of a file git already versions on every commit. Sessions 15 and 16 both committed these before this was caught: each one adds ~30K duplicate lines to the repo for zero benefit (any prior `graph.json` is already recoverable via `git show <commit>:graphify-out/graph.json`). `.gitignore` now backstops any that slip through (`graphify-out/YYYY-MM-DD/` pattern), but the env var is the real fix — it stops them from being written at all. If a dated folder ever does appear, delete it rather than committing it.

See `knowledge/PROJECT_CONTEXT.md` for full current-state detail.
