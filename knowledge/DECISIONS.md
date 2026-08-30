---
type: knowledge-vault-core
last_updated: 2026-08-30
updated_by: claude-code
---

# Decisions

Lightweight, reverse-chronological decision log. Not full ADR ceremony — kept cheap enough to actually maintain. Newest first.

## 2026-08-30: Accept the loss on `uptime/`'s real history rather than try to reconstruct it

**Context:** Branch-integration Phase 3 ([[NEXT_TASK]], [[2026-08-30]] session 28) built
`scripts/reset_demo_logs.py` to close the "delete and reseed the live demo data" checklist item.
While designing it, found that `scripts/seed_fake_logs.py`'s `_seed_uptime()` writes
`uptime/{date}` documents with a plain `.set()` (overwrite, no `merge=True`), while the real
uptime probe (`query.py`'s `record_uptime_probe()`, run every 5 minutes by a GitHub Actions
workflow independent of `SENTINELSCAN_TELEMETRY_ENABLED`) merges into those same date-keyed
documents. Session 22's original seed run therefore likely overwrote whatever real probe history
existed for the ~14 days it touched, and nothing in that collection distinguishes real writes
from fake ones the way `env: "dev"` does inside a `logs` batch's events.

**Decision:** asked the user directly rather than guessing. Presented three options — leave
`uptime/` untouched pending investigation, try to reconstruct real history from GitHub Actions
run logs, or accept the loss and reseed it clean. The user chose the third: reseed it anyway,
prioritizing a demo-realistic status page over an uncertain, possibly-incomplete reconstruction
effort for data that may already be three weeks stale regardless.

**Consequences:** `reset_demo_logs.py` includes `uptime` in its full-wipe-then-reseed set,
alongside `logs`/`presence`/`logs_hourly`/`logs_meta`. Also surfaced a related, smaller judgment
call: the original handoff note's "safe to blanket-wipe" list named those four collections but
not `stats/`, even though `stats/{date}` is equally demo-only while telemetry stays off — treated
as an omission, not a deliberate exclusion, since leaving it unswept would double every counter
on the very next reseed (`firestore.Increment` is additive). `reset_demo_logs.py` deletes
`stats/{date}` too, scoped to exactly the date range being reseeded rather than the whole
collection, since unlike the other four it isn't unconditionally safe outside that range.

## 2026-08-29: `observability.emit`'s queue is `logstore.pipeline`'s queue, not a second one

**Context:** Branch-integration Phase 2 ([[NEXT_TASK]], [[2026-08-29]] session 27) merged
Workstream A (`apps/backend/observability/`, the recorder) and Workstream B
(`apps/backend/logstore/`, the storage pipeline) into one tree for the first time. Each was
built and tested in isolation, so neither branch could ever have caught what only exists once
they're both present: `observability/emit.py` kept its own private `queue.Queue` for every
backend-originated event (HTTP requests, unhandled errors, agent decisions, worker logs, LLM
usage), and nothing in Workstream A's own package ever drained it — it ships only a manual
`stdout_sink.py`, never started automatically. Meanwhile `logstore/sink.py`'s real background
thread drained a *different* queue, `logstore/pipeline.py`'s, fed solely by the browser's own
`POST /api/v1/telemetry`. Left as-is, switching telemetry on in production would have recorded
browser clicks and navigation only — never a single backend error, AI agent decision, or LLM
cost figure, which is most of the actual value the observability project was built for.

**This was not a surprise either branch's author missed** — both sides' own code comments
describe the *intended* design without it ever having been wired that way, because the two
branches had literally never coexisted until this merge. `logstore/sink.py`'s docstring already
claimed "this is what keeps Workstream A's `emit_event()` non-blocking." `logstore/pipeline.py`'s
docstring said outright: *"Workstream A's `observability.emit` will eventually own a queue of
its own for backend-originated events; reconciling the two into a single shared queue is
integration work, once her branch exists."* `observability/emit.py`'s own `get_queue()`
docstring even already read "The bounded queue Workstream B's sink thread drains" — describing
a fact that, until this fix, was simply false.

**Decision:** `observability/emit.py`'s `get_queue()` now delegates to
`apps.backend.logstore.pipeline.get_queue()` instead of maintaining a second queue and its own
duplicate size-from-env-var logic (removed). This is the architecturally sanctioned direction —
the project's own integration rule (`knowledge/DECISIONS.md`, 2026-08-21 "no workstream edits
any existing file" entry, rule R5) says imports may only flow `observability → logstore →
logsite`, never upward, and this is exactly that direction, not a new coupling invented for
convenience.

**Verified, not assumed:** a new `tests/test_observability_logstore_integration.py` pushes a
real `observability.events.build_event(...)`-produced event through an actual `SinkThread` to a
fake backend (proving the wiring), and separately through `schema.build_batch_document`/
`FirestoreSink.write_batch` against a mocked Firestore client (proving the two teams' event
schemas genuinely agree, not just by inspection — they do; both were built against the same
frozen schema in `docs/workstreams/WORKSTREAM_A.md` section 4). Also confirmed live: running the
app locally with telemetry and stdout-debug both on showed a real HTTP request's event actually
reach the sink and print.

**A second-order bug this surfaced:** `tests/test_telemetry_routes.py` builds the real app with
telemetry enabled, so once Workstream A's request hooks were actually wired in, every test's own
`self.client.post()` to the ingest endpoint under test also generated a backend-sourced `http`
event into the same now-shared queue the tests inspect, breaking exact-count assertions. Fixed
by filtering `_drain_queue()` on `source == "frontend"` — the browser-ingest path's own,
permanent tag — rather than changing production routing to skip instrumenting that endpoint,
since recording hits to the telemetry endpoint itself is reasonable production behavior, not a
bug; the tests' old assumption (that the queue would contain *only* what they posted) was simply
never going to survive contact with the rest of the system.

**Alternatives considered:** *Keep both queues and have something periodically drain A's into
B's* — rejected, adds a second moving part (another thread, another failure mode) to solve a
problem a direct delegation solves with less code and no new state. *Have `logstore.pipeline`
depend on `observability.emit` instead* — rejected, backwards: it would make B (the storage
layer, meant to be a stable base other things build on) depend on A, violating the one-way
import DAG the whole three-way split was designed around.

**Consequences:** `observability/emit.py`'s `get_queue()`/`get_stats()`/`drain_for_test()` are
now thin wrappers over `logstore.pipeline`'s state rather than owning any of their own; any test
touching either module must reset `pipeline._queue`/`pipeline._started`, not a private `emit`
module global (three existing tests updated accordingly). A subtle Python import gotcha
surfaced while writing the new test file: `apps/backend/observability/__init__.py` does
`from .emit import emit, ...`, which shadows the package's `emit` attribute with the *function*
of the same name — so `from apps.backend.observability import emit` (and even
`import apps.backend.observability.emit as x`, confirmed empirically, not just by reading docs)
silently returns the function, not the submodule. The only reliable way to reach the submodule's
own names is importing them directly from its full path
(`from apps.backend.observability.emit import get_queue`), which is what the pre-existing tests
already did and what the new test file was corrected to do.

## 2026-08-24: `query_events` returns the newest events on a first load, not the oldest

**Context:** The branch-wide review ([[workstream-b-code-review-2026-08-23]], finding C1) found
that `query.query_events` sorted ascending by `ts` and took the head, so a caller with no cursor
got the **oldest** events in the database. Workstream C's Live activity feed
(`docs/workstreams/WORKSTREAM_C.md` section 9.2) is specified as "newest first", so its primary
screen would have opened on ancient history. The return shape is frozen and Danny is coding
against it blind, so this needed a decision rather than a quiet fix.

**The tension:** the shape has to serve two different callers at once. A live screen wants the
newest events. The cursor-polling mechanism -- which is the only thing standing between three
developers idling with tabs open and exhausting the 50k/day read quota (section 10) -- only
works if order runs oldest → newest, because a cursor means "everything after this point".

**Decision:** split on whether a cursor was given.

- **No cursor** (a screen's first load) → the newest `limit` matching events, still ordered
  oldest-first *within* the page.
- **With a cursor** → only what arrived after it, walking forward. Unchanged.
- **`next_cursor` is now returned whenever the page is non-empty**, and echoes the caller's own
  cursor back on an empty poll. Previously it appeared only when more than `limit` events
  remained, so a screen receiving a short page had no cursor to poll from at all -- which
  section 10's design assumes it always has.

The **return shape is unchanged** (`{"events": [...], "next_cursor": str | None}`), so the
frozen contract holds. The semantics are not, which is why this is here. **Danny must be told at
integration.**

**Alternatives considered:** *Fix only the docstring and leave the behaviour* -- rejected;
cheapest and zero-risk, but Danny's main screen would open on the oldest events until he wrote
a workaround, and coding blind he might not notice until integration. *Reverse to newest-first
everywhere* -- rejected; it matches the screen spec most literally but breaks the "give me only
what is new" polling mechanism, which is precisely the read-quota protection the architecture
depends on.

**Consequences:** paginating *backwards* through a historical range is no longer expressible --
a cursor always walks forward. Nothing in `WORKSTREAM_C.md` asks for backwards paging, and a
caller wanting a specific historical window passes explicit `since`/`until` instead.

## 2026-08-24: `unique_sessions` is a counter with in-process de-duplication, not a stored array

**Context:** Session 21 chose to track `get_daily_stats().unique_sessions` at write time rather
than derive it at read time -- see [[2026-08-22]]. The implementation unioned every session id
of the day into a `session_ids` array on `stats/{date}`. The review (finding A3) found that
array had **no upper bound**: past Firestore's 1 MB document limit, every stats write for that
date fails, which makes the sink drop *every* batch for the rest of the UTC day. Reachable
organically at ~25,000 sessions/day, or deliberately in about four minutes.

**Decision:** keep tracking it at write time -- the session-21 reasoning still holds -- but stop
storing the ids. `FirestoreSink` keeps a bounded in-process `{date: set(session_id)}` and
`Increment`s a scalar `unique_sessions` counter only for ids it has not already counted for that
date. Both the per-date set and the number of dates retained are capped.

**Accepted trade:** de-duplication is per process, so a restart can double-count a session that
spans it, and the counter saturates on an absurd day. Acceptable because Render runs a **single**
gunicorn worker (`render.yaml`, `--workers 1`), the number is an activity gauge rather than
billing data, and the alternative was a field that destroys the whole day's telemetry when it
grows too large.

**Alternatives considered:** *Derive uniqueness from the `presence/` collection at read time*
(one document per session already) -- viable, and the natural choice if this ever needs to be
exact across restarts, but it turns a single-document read into a collection scan on a screen
that auto-refreshes, which is the cost session 21 deliberately avoided.

**Consequences:** `get_daily_stats` reads `unique_sessions` and **falls back to
`len(session_ids)`** when absent, so the ~14 days of stats documents already in live Firestore
keep reporting correctly. Do not remove that fallback while any pre-2026-08-24 stats document
still exists.

## 2026-08-22: Every phase of Workstream B lands via a PR into `workstream-b-pipeline`, never a direct push

**Context:** The project's own rule (`knowledge/NEXT_TASK.md` R8, inherited from
`docs/workstreams/WORKSTREAM_A.md`/`WORKSTREAM_C.md`) says a workstream branch needs no PR --
only merges into `main` do. While reviewing the Phase 1-4 plan for Workstream B, the user asked
for something stricter for their own branch specifically.

**Decision:** `workstream-b-pipeline` is the durable base branch for all four of Workstream B's
phases. Each phase is implemented on its own short-lived sub-branch, pushed, and opened as a PR
with base `workstream-b-pipeline` (not `main`). The user reviews and merges each one themselves;
the next phase doesn't start until they've given a headsup that it landed, which gets verified
(`git log`/`gh pr view`) rather than assumed. See standing rule 3 in [[NEXT_TASK]].

**Why, in the user's own words:** *"this is to enforce an habit for me to read all the code and
changes which you make so that i dont become dumb and actually understand whats going on."* Not
a correctness or safety concern -- a deliberate personal discipline choice, scoped only to their
own branch. Doesn't apply to Sanjana's or Danny's branches, and doesn't change the final
integration step (`workstream-b-pipeline` plus A's and C's branches still merge into `main`
through the existing project-wide PR rule, later).

## 2026-08-21: Withhold `knowledge/` from the repo for the duration of the observability project

**Context:** Two teammates (Sanjana, Danny) are working on their own branches off `main` for the
observability project. `knowledge/` is already tracked and already on `main`, so they receive a
copy whenever they pull, and several AI agent workflows write to a project's memory vault
automatically at session end. Three divergent vaults arriving at merge time would leave no way to
tell which version is authoritative.

**Decision:** From 2026-08-21 until the user explicitly says otherwise -- which will be after all
workstream branches are merged and `main` is the only branch left -- **no `knowledge/` update is
committed or pushed**. Vault updates are written to disk and left as uncommitted working-tree
changes. This binds every future session, not just the one that set it: a later session must not
commit the vault simply because every prior session did.

Two mechanical steps enforce it, both performed by the user:
1. Stop pushing vault updates (this decision).
2. **Discard every incoming `knowledge/` diff at merge**, unread (`git checkout HEAD -- knowledge/`
   after merging each workstream branch).

**Rejected alternative -- a "treat `knowledge/` as read-only" rule for teammates.** This was
proposed first and the user rejected it explicitly: *"i don't think setting a hard rule for
keeping the knowledge vault READ only will work."* They were right. The rule would depend on
compliance from AI agents nobody in this project controls, and its failure mode is silent. Moving
enforcement from other people's discipline to our own tooling makes it actually hold. Rule R10 in
both handoff documents is therefore phrased as **information** ("anything written here will be
discarded") rather than as an instruction anyone is relied upon to follow.

**A factual correction worth preserving:** withholding future updates does **not** hide the vault.
`knowledge/` is already on `main` from prior sessions, so teammates get its 2026-08-21 state
regardless. What this decision protects is the *authoritative* copy going forward, not secrecy.

**Consequences:** Exactly one correct vault exists, on the user's machine, never at the mercy of
someone else's tooling. Cost: uncommitted work is not backed up by git, so `git checkout .`,
`git reset --hard`, `git clean` and `git stash` are all hazardous in this repo while the policy
holds. Recorded prominently at the top of [[NEXT_TASK]].

## 2026-08-21: The PR-to-`main` rule binds merges into `main` only, not teammates' branches

**Context:** `CLAUDE.md` section 10 requires every merge to `main` to go through a pull request.
With two teammates now working on their own branches, the question arose of whether they must
also open PRs for their own work.

**Decision:** No. The rule's scope is **merging into `main`**, and the user performs that step
himself as the sole integrator. Sanjana and Danny commit and push to `workstream-a-recorder` and
`workstream-c-logsite` freely -- no PR, no review gate, no approval, any commit style they like.
The user's framing: the PR rule is *"only for me for my own benefit."*

One convention still applies to everyone: **no `Co-Authored-By: Claude` trailer on any commit**
(see the 2026-08-20 global rule).

**Consequences:** GitHub branch protection (`enforce_admins: true`) already blocks direct pushes
to `main` for everyone including admins, and does not restrict pushing feature branches -- so the
existing configuration already implements exactly this scope with no change needed. The rule's
real purpose is unchanged: force a human to read AI-generated code before it reaches `main`. That
happens once, at integration, when the user reads the combined diff.

## 2026-08-21: No workstream edits any existing file; all integration edits belong to the integrator

**Context:** The observability project is split three ways and built in parallel. Workstream A
(the recorder) naturally needs hooks in `app.py`, `gemini_client.py`, `orchestrator.py` and
`scan_routes.py`; Workstream C (the log site) needs a second service in `render.yaml`. Those five
files are the only real collision surface between the three branches.

An earlier draft of the split had Workstream A making those four backend edits directly -- which
was tolerable only because A was, at that point, assigned to the user (the integrator). When the
user reassigned A to Sanjana and took Workstream B instead, the problem surfaced.

**Decision (rule R2 in both handoff documents):** **No workstream edits a single existing file.**
Each package instead ships an `INTEGRATION.md` at its root listing the exact edits required, with
copy-paste-ready snippets and precise anchor lines, which the integrator applies during
integration. `app.py`, `gemini_client.py`, `orchestrator.py`, `scan_routes.py`, `render.yaml`,
`requirements.txt`, `apps/frontend/**`, `docs/**`, `knowledge/**`, `CLAUDE.md` and
`graphify-out/**` are integrator-only.

Supporting rules adopted alongside it: file ownership is absolute and the three lists are disjoint
(R1); imports form a one-way DAG, `observability` to `logstore` to `logsite`, never upward (R5);
everything gates behind `SENTINELSCAN_TELEMETRY_ENABLED` default off, so any single stream can
merge alone without affecting production or the test suite (R6); nobody regenerates `graphify-out/`
during the project (R9).

**Consequences:** Three parallel branches should merge with close to zero conflicts, since no two
of them can touch the same file. Cost: the integrator does more work at the end, and each
workstream must write a genuinely precise `INTEGRATION.md` -- a vague one converts a merge
conflict into a reverse-engineering exercise, which is worse. Both handoff documents therefore
specify the `INTEGRATION.md` structure and its required entries rather than leaving it to taste.

## 2026-08-21: Firestore over Postgres for log storage; written timeline over session replay; a second Render service over a subpath

Three product/architecture choices made together for the observability project, all presented to
the user as explicit alternatives and chosen deliberately.

**Firestore, not Postgres.** Firestore is already wired (`apps/backend/auth/firebase_client.py`,
`models/history_store.py`), free, and needs no new credentials for a three-person team. Postgres
would query far better for a log-search UI -- `GROUP BY`, time bucketing, full-text over
messages -- but Render **deletes free Postgres instances after 30 days**, which disqualified it
for a store whose entire value is retention. *Rejected also:* an external SaaS (Sentry, Axiom,
BetterStack). Their free tiers would have cut the work by roughly 80%, which is precisely why it
was rejected -- it would have left too little for three people to build.

*The cost of choosing Firestore:* the Spark tier allows 20k writes and 50k reads per day, so
**batching is mandatory rather than an optimisation**. ~100 events per batch document makes a
10-minute user session cost ~2 writes. On the read side, cursor-based incremental polling is
equally mandatory: three developers idling with the log site open, refreshing every 20s over a
50-doc window, computes to ~108,000 reads/day against a 50,000/day limit -- which would take the
main app's history feature down with it, since they share the quota. Cursor polling at 30s
intervals brings it to ~2,900/day.

**Written timeline, not session replay.** rrweb-style DOM replay was offered and rejected: bundle
weight on a site that already ships a heavy React bundle, storage volume against the quota above,
and the masking burden of guaranteeing typed text is never recorded. A timestamped timeline of
clicks, navigations, requests and errors answers "what did the user do" well enough, at a small
fraction of the cost and privacy risk. A middle option -- one screenshot captured at the moment of
a crash -- was also offered and not taken.

**A second Render service from this same repo, not a subpath on the main app.** The user wanted
two genuinely separate websites. Accepted cost: free-tier services sleep after 15 minutes idle, so
the log site cold-starts in ~30-50s. Mitigated architecturally rather than accepted as a flaw --
**ingestion lives on the main service** (`POST /api/v1/telemetry`), and the log site only ever
reads Firestore, so nothing is lost while the log site sleeps, and no traffic on the log site can
slow the main site down. That last property is the project's hard constraint, in the user's words:
the log site is *"a window to it"*, not a component of it.

**Consequences:** All three choices are documented in `docs/workstreams/WORKSTREAM_A.md` and
`docs/workstreams/WORKSTREAM_C.md` with the arithmetic, so the constraints read as engineering
requirements rather than style preferences. If the project ever outgrows the Spark tier, the
decision to revisit first is Firestore-vs-Postgres -- the batching and cursor-polling machinery
exists specifically to work around limits Postgres would not have imposed.

## 2026-08-20: Integrate Graphify as a code-only structural graph layer, copied from Clyro

**Context:** The user had already worked out this integration once, in their other project (Clyro), and
wanted the identical setup in this repo rather than a fresh design — see [[2026-08-20]] (session 15) for
the full copy-and-adapt process. Clyro's own vault documented a real gotcha worth inheriting the fix
for: `graphify install --project` / `graphify claude install` auto-append a section to `CLAUDE.md` and
auto-install a `PreToolUse` hook intercepting every Read/Grep/Bash call — neither wanted, since it adds
a second enforcement layer on top of this project's existing permission-gate philosophy that nobody
asked for.

**Decision:**
1. **Scope permanently code-only.** `.graphifyignore` excludes `knowledge/`, `docs/`, `.agents/`,
   `.claude/`, `secrets/`, `.venv/`, and other non-code/sensitive paths; every build uses `--code-only`.
   Graphify's semantic/subagent path never triggers, so it never collides with the global "ask before
   spawning any subagent" rule.
2. **No installer, no hook.** Every file (`.claude/skills/graphify/`, `.graphifyignore`, the CLAUDE.md
   section) was copied/written by hand from Clyro's working setup, never via `graphify install`. This
   project's existing single `PostToolUse` vault-reminder hook in `.claude/settings.json` stays as the
   only hook.
3. **Read/write asymmetry, mirroring the knowledge vault exactly.** Querying the graph (`graphify
   query`/`path`/`explain`) is allowed automatically, anytime, during a build task — no approval needed.
   Regenerating it only happens at session-end, batched with the (unchanged) knowledge-vault write
   trigger.
4. **Regenerate with `graphify extract . --code-only --force`, never `graphify update .`** — inherited
   directly from a bug Clyro hit and fixed on 2026-08-18: `update` has no `--code-only` flag, so it
   re-extracts whatever the manifest already holds and cannot narrow scope, letting excluded paths back
   into the graph silently.
5. **`graphify-out/` is committed to git**, except `graphify-out/cost.json` (gitignored, local-only
   noise) — same call Clyro made, appropriate at this project's similar solo/small-team scale.
6. Already-installed CLI (`uv tool install graphifyy`, v0.9.45, done previously for Clyro) — machine-wide,
   not a project dependency, nothing added to `package.json`/`requirements.txt`.

**A real bug caught during the first build (not present in Clyro's setup, SentinelScan-specific):**
`apps/frontend/static/react-dist/main.js`, a minified Vite build bundle vendoring three.js, was not
excluded and accounted for 1409 of the first build's 2459 nodes (57%) — pure build-artifact noise,
surfacing as meaningless communities like "Minified Bundle Internals". Added
`apps/frontend/static/react-dist/` to `.graphifyignore` and rebuilt to a clean 1050-node graph. Verified
afterward that no node's `source_file` lives under any excluded path.

**Consequences:** Structural questions during build tasks ("what calls X", "where is Y defined") can be
answered from a pre-built index instead of a grep-and-read sweep, at zero ongoing token cost for
extraction (ND: community labeling used the local `claude-cli` backend, ~93k input / 3.6k output tokens
for 86 communities, since no `GEMINI_API_KEY`/`GOOGLE_API_KEY` is set on this machine — a one-time cost
per relabel, not per query). The graph can go stale mid-session by design (write side is session-end
only) — always verify a query's answer against the real file before editing, never trust it blindly. If
Graphify is ever reinstalled/upgraded past v0.9.45, re-check for the installer-hook/CLAUDE.md-append
behavior — Clyro's experience showed it should not be assumed to only do what's expected.

**Rejected alternatives:** same as Clyro's original ADR (including docs/PDFs in the graph — would
require per-instance subagent-spawn approval on every doc-touching rebuild; using
`graphify install`/`claude install` — adds an unwanted second enforcement layer;
`graphify update .` after every prompt — wastes cycles during in-session iteration). Not re-litigated
here since the underlying reasoning is identical to Clyro's; see that project's
`knowledge/Decisions/Integrate Graphify as a code-only structural graph layer.md` if the full original
writeup is ever needed.

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
