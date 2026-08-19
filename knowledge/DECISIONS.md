---
type: knowledge-vault-core
last_updated: 2026-08-20
updated_by: claude-code
---

# Decisions

Lightweight, reverse-chronological decision log. Not full ADR ceremony — kept cheap enough to actually maintain. Newest first.

## 2026-08-20: All merges to `main` require a reviewed, accepted pull request — no exceptions

**Context:** Reviewing the `dhanush-changes` branch during a repo cleanup surfaced a real bug that would
have broken every scan submission (`ssrf_validator.py`'s rewritten loop referenced `addr_info` without
ever assigning it — see [[2026-08-20]]) if it had been merged straight into `main` without review.
Several prior sessions had also pushed commits directly to `main` when the user gave in-session
authorization (e.g. session 13's CSP fixes) — convenient, but it means nothing forces a second set of
eyes on AI-generated code before it ships, even when the diff is subtle enough to hide a
crash-on-every-request bug.

**Decision:** Every commit that reaches `main` — code, docs, and `knowledge/` vault updates alike, no
size exception — must go through a GitHub pull request that is reviewed and explicitly accepted first.
This is codified two ways: a new CLAUDE.md section (10) documenting the rule for any Claude Code
session, and GitHub branch protection on `main` (`required_pull_request_reviews` with
`required_approving_review_count: 1`, `enforce_admins: true`, force-push/deletion disabled) so it's
enforced server-side for every collaborator, not just as a convention Claude Code happens to follow.

**Alternatives considered:** Keeping the rule as a documented convention only, without branch
protection — rejected because a documented rule doesn't stop a direct `git push origin main` by anyone
(including Claude Code under a future looser instruction, or another collaborator not using Claude
Code); a lighter version scoped to "feature branches only" (letting small doc/vault commits go straight
to `main`) — rejected per explicit user instruction that this should apply to every commit, since the
whole point is forcing a human read, and small commits are exactly the ones most likely to get rubber-stamped
without one.

**Consequences:** Every future unit of work — including a routine knowledge-vault log update — now
needs its own branch and PR, which is slower than a direct commit. The repo owner (`Zopyrus269`, admin)
is also subject to `enforce_admins`, so even they can't bypass the PR requirement; with 4 collaborators
on the repo (`Dannyo6`, `sbsai25`, `bhuvan-sk`, `Zopyrus269`) there's always someone else available to
provide the required approval. If the repo ever drops to a single active collaborator, this setting
would need revisiting (a solo maintainer can't get a second approval from themselves).

## 2026-08-20 (correction, same day): required approving reviews dropped from 1 to 0

**Context:** The above decision set `required_approving_review_count: 1`, assuming any of the 4
collaborators could approve any PR. In practice, the PRs opened this session (`gh pr create`) were
authored under the repo owner's own GitHub account (`Zopyrus269`, since that's who `gh` is
authenticated as) — and GitHub has a hard platform rule that a PR author can never approve their own
PR, for anyone, regardless of admin status. That's not a branch-protection setting and can't be
configured around. With `required_approving_review_count: 1`, every PR the owner opens under their own
account would be permanently stuck needing an approval nobody involved can give. The owner's actual
goal (stated directly) was never "get a second person's sign-off" — it was building a personal habit of
reading the diff before merging AI-generated code.

**Decision:** Set `required_approving_review_count: 0`. `main` still cannot be pushed to directly
(branch protection still requires a PR to exist, `enforce_admins` stays on) — but a PR the owner authors
no longer needs an unobtainable approval to merge; they open it, read it, and merge it themselves. If
another collaborator opens a PR and wants an actual second-person review before merging, they can still
request and wait for one — this setting doesn't forbid that, it just doesn't force it.

**Alternatives considered:** Opening future PRs from a separate bot/service account so the owner could
approve them — rejected as unnecessary complexity for a solo-habit goal, and it would mean Claude Code
managing a second set of credentials; lowering `enforce_admins` instead so the owner could bypass PRs
entirely — rejected, since that would remove the "a PR must exist" guarantee too, not just the
unobtainable-approval problem, defeating the actual point of the rule.

**Consequences:** The "required PR" guarantee (no direct pushes to `main`, forced diff review before
merge) still holds for everyone. The "someone else approved it" guarantee never actually existed for
solo-authored PRs and is now honestly reflected in the setting rather than silently unsatisfiable.

## 2026-08-07: MCP filesystem server invocation moved from `npx` to a locally pinned dependency

**Context:** `.mcp.json` pinned the server version via a CLI arg string (`npx -y @modelcontextprotocol/server-filesystem@2025.7.1`). That pin is only as reliable as `npx`'s resolution/caching behavior on every invocation — it isn't installed, tracked, or auditable as part of the repo, and nothing prevents a future edit or environment difference from silently resolving a different version. This risk was not hypothetical: while preparing this cleanup commit, `package.json`/`package-lock.json` were found to have drifted (uncommitted) to `2025.11.25` — a version re-confirmed via source audit to still contain the roots-protocol override that caused the original scoping bug.

**Decision:** Add `@modelcontextprotocol/server-filesystem@2025.7.1` as a `devDependency` in `package.json`, commit `package-lock.json` for reproducible installs, and change `.mcp.json`'s `knowledge-vault` command to invoke the local copy directly: `node ./node_modules/@modelcontextprotocol/server-filesystem/dist/index.js C:/Dev/SentinelScan-Project/knowledge`. This removes `npx` — and its registry/cache resolution step — from the picture entirely; the exact pinned code is what's on disk and in git.

**Alternatives considered:** Keeping `npx -y ...@2025.7.1` and just being more careful — rejected, since the drift found during this session's cleanup shows "being careful" isn't a durable control; a global (unpinned, un-tracked) `npm install -g` — rejected, invisible to other clones/machines and to git history.

**Consequences:** `node_modules/` must exist (`npm install`) before `knowledge-vault` can start — an implicit setup step for any fresh clone. `package.json`/`package-lock.json` are now part of the repo's auditable dependency surface for this tool; any future version bump must be re-audited against the roots-protocol pattern described in the entry below before landing, not assumed safe.

## 2026-08-07: MCP filesystem scoping fixed with an absolute path, not a cwd workaround

**Context:** A same-day workflow audit found the `knowledge-vault` MCP server (`.mcp.json`, `./knowledge` relative arg) was actually exposing the whole repo, not just `knowledge/` — `list_allowed_directories` returned the repo root, and `docs/PRD.md` was readable through the tool. Root cause: relative paths passed to `@modelcontextprotocol/server-filesystem` resolve against whatever cwd the spawning client uses, which isn't guaranteed to match assumptions made when the config was written; a manual `npx` test earlier had appeared to work but exercised a different spawn path than Claude Code's own MCP client actually uses.

**Decision:** Use an absolute path (`C:/Dev/SentinelScan-Project/knowledge`) in `.mcp.json` instead. Absolute paths resolve identically regardless of spawn cwd, removing the ambiguity entirely rather than trying to control or predict the client's cwd.

**Alternatives considered:** Pinning/documenting the expected spawn cwd — rejected, since that cwd is controlled by the Claude Code client, not by anything in this repo, so it isn't a guarantee this project can enforce; a wrapper script that `cd`s before invoking `npx` — rejected as unnecessary indirection when an absolute path solves it directly.

**Consequences:** The path is now Windows-machine-specific inside `.mcp.json`. Acceptable here since the project is developed on a single known machine; if `.mcp.json` needs to be portable across machines/OSes later, this should move to a relative path resolved via a wrapper that reads `process.cwd()` correctly, or an env-var-based path.

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

## 2026-08-07: Pin `@modelcontextprotocol/server-filesystem` to `2025.7.1` instead of using unpinned `-y`

**Context:** The `knowledge-vault` MCP scoping bug (repo root exposed instead of `knowledge/`) survived both an absolute-path fix and a full session restart. Root cause: the package's newer versions implement the MCP roots protocol, and on connect, silently overwrite the CLI-arg-configured `allowedDirectories` with whatever root directory the connecting client (Claude Code) reports — which is the whole project, not `knowledge/`. This is a client-vs-server precedence design in the package, not something fixable from this repo's `.mcp.json` structure alone.

**Decision:** Pin the exact package version in `.mcp.json`'s `args` (`@modelcontextprotocol/server-filesystem@2025.7.1`) rather than `-y @modelcontextprotocol/server-filesystem` (unpinned, always resolves latest). `2025.7.1` was confirmed via full source audit to have no roots-handshake code at all — `allowedDirectories` is a `const`, never reassigned after startup.

**Alternatives considered:** Patching or forking the package to strip roots support — rejected as unnecessary maintenance burden for a single dev-tooling dependency; looking for a config flag to disable roots negotiation — none exists in the package; switching to a different filesystem MCP server implementation entirely — rejected, would be a bigger change for the same outcome a version pin already achieves.

**Consequences:** `knowledge-vault` is now pinned below the package's latest release, so it won't receive upstream fixes/features via `-y` auto-resolution. If a future need arises to move past `2025.7.1` (e.g. a required bugfix in a later version), re-audit whichever target version's `dist/index.js` for the same `clientCapabilities?.roots` / `oninitialized` override pattern before upgrading — don't assume it's been removed.
