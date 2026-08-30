> **Superseded by `CLAUDE.md` for Claude Code sessions.** This file remains the instructions document for the Antigravity coding agent; Claude Code reads `CLAUDE.md` at the repo root instead.

# Agent Instructions (Antigravity)

As the Antigravity coding agent working on the SentinelScan repository, you must adhere strictly to the following guidelines in all future sessions:

## Documentation Prerequisites
Before making any architectural, structural, or significant feature changes, you **MUST** read and understand:
- `docs/PRD.md`
- `docs/ARCHITECTURE.md`
- `docs/AI_AGENT.md`
- `docs/API.md`
- `docs/WORKERS.md`

## Safety and Scope Constraints
- **AUTHORIZED USE ONLY**: SentinelScan is an assessment tool. You must assume all operations are authorized.
- **NO EXPLOIT CODE**: You are strictly prohibited from writing, generating, or suggesting active exploit code (e.g., payloads, reverse shells, memory corruption scripts). Confine your implementation to reconnaissance, vulnerability assessment, and reporting.

## Architectural Principles
- **Dumb Workers**: Python workers must NEVER contain business logic, orchestration logic, or state. They execute exactly what they are told and return structured JSON. The AI Agent holds all the intelligence and state.
- **Dynamic Orchestration**: Ensure the AI Agent (Gemini) maintains control of the loop. Do not hardcode sequential scans.

## Coding Conventions
- **Language Standards**: Write Python compliant with PEP8 guidelines.
- **Typing**: Use standard Python type hints (`typing` module) for all function signatures and complex variables to ensure maintainability.
- **Modularity**: Keep functions small and modular.
- **Documentation**: Provide clear, concise docstrings for all classes and functions.

## Version Control
- **Commits**: Structure your commits logically. They should be small, descriptive, and atomic (e.g., "feat(worker): implement WHOIS parsing logic").

Failure to adhere to these rules violates the core design principles of the SentinelScan college project.

---

## Side Task: PR Review Explainer Mode

This is a **project-scoped side workflow**, separate from your normal coding-agent duties above. It does not replace anything in this file — it only activates when the trigger phrases below appear, and only within the SentinelScan repo.

### When this activates

Any message from the user that mentions reviewing or analyzing a pull request — for example: `"analyze the PR"`, `"analyze PR #<n>"`, `"review this PR"`, `"help me review this PR"`. If more than one PR is open and it isn't clear which one is meant, ask which PR/number rather than guessing.

### What to do when triggered

1. Fetch the PR from `Zopyrus269/sentinelscan` on GitHub — remotely, read-only (see Concurrency rule below).
2. Walk through every changed file, **in logical chunks (function/block level, not literal line-by-line)**. For each chunk explain:
   - What language/construct is being used, and why.
   - What the code actually does.
   - Why it's written this way — the design reasoning, not a restatement of the syntax.
3. Use plain, beginner-friendly language. Assume the reader can read code syntax but wants the *intent* explained, not a line-by-line transliteration.
4. **Take no action on the PR itself** — no comments, no approvals, no merging. The user reviews and merges on GitHub themselves. Your job stops at explaining.
5. After explaining, stop and wait. Don't keep re-explaining or proactively follow up.

The user does the actual merge through the human-reviewed PR process this repo already requires (see `CLAUDE.md` §10 in the repo root, if readable from this session) — you are not part of that merge step.

### Standing down

When the user later says something like `"done reviewing"`, `"reviewed and merged"`, or `"merged it"`, acknowledge it and drop this mode. Return to normal behavior until the next trigger phrase appears.

### Concurrency: do not touch the local working tree

Claude Code may be actively running in this same project folder, in a separate terminal, **at the same time** you are doing this. To avoid any collision between the two of you:

- Treat this workflow as **strictly remote and read-only**. Fetch the PR via `gh pr view <n>` / `gh pr diff <n>` (or equivalent read-only GitHub API/tooling) — do **not** check out the PR branch locally.
- Do **not** run any local git operation that changes working-tree or branch state during this workflow: no `checkout`, `switch`, `pull`, `merge`, `reset`, or `stash`, and no local file edits. Everything needed (diff, file contents, commit messages) is available directly from GitHub without touching the local checkout.
- This keeps your review pass fully non-interfering with whatever Claude Code is doing locally — mid-edit, mid-commit, or on a different branch — at that same moment.
