---
type: knowledge-vault-core
last_updated: 2026-08-30
updated_by: claude-code
---

# Architecture Deltas

This file holds only **changes since** `docs/ARCHITECTURE.md` — it never restates the static doc. If a change here becomes permanent/stable, it's still logged here (not deleted); reconciling it back into `docs/ARCHITECTURE.md` is a separate, deliberate editorial decision, not automatic.

Each entry: date, what changed, why, where.

## 2026-08-30: Observability project fully merged into `main` (branch-integration Phase 3)

`integration/observability` merged into `main` via PR #19 (`0cb41be`) — the recorder
(`apps/backend/observability/`), the storage pipeline (`apps/backend/logstore/`), and the
developer log site (`apps/logsite/`) are no longer split across branches; `main` is the only
branch that matters going forward. `SENTINELSCAN_TELEMETRY_ENABLED` stays `"0"` in both
`render.yaml` and (as of this session) the actual Render dashboard — merging the code did not
turn telemetry on.

New in this merge beyond what the 2026-08-21/29 entries already describe:
`scripts/reset_demo_logs.py`, a delete-then-reseed tool for the demo data seeded into production
Firestore (companion to `scripts/seed_fake_logs.py`) — full wipe of
`logs`/`presence`/`logs_hourly`/`logs_meta`/`uptime`, plus `stats/{date}` scoped to the reseeded
range. Full reasoning in [[DECISIONS]] (2026-08-30). The three composite indexes
`apps/backend/logstore/firestore.indexes.json` declares were also deployed directly to the
Firestore console this session — they were never actually live in production despite being
declared in the repo since Phase 3 of Workstream B (see [[2026-08-30]] session 28).

## 2026-08-29: The recorder and the pipeline now share one queue (branch-integration Phase 2)

First time Workstream A (`observability/`) and Workstream B (`logstore/`) existed in the same
tree. `observability/emit.py`'s `get_queue()` no longer maintains its own queue — it now returns
`apps.backend.logstore.pipeline.get_queue()` directly, so the one background sink thread
(`logstore/sink.py`) drains every backend-originated event (http/error/agent/worker/llm) the
same way it already drained browser-originated ones. Before this, the diagram implied by the
2026-08-21 entry below (recorder → `emit_event()` → sink thread → Firestore) was aspirational:
A's events had nowhere real to go until this merge. See [[DECISIONS]] for the full writeup and
why this direction (`observability` depending on `logstore`, not the reverse) is the one the
project's own R5 import-DAG rule already sanctioned.

New branch `integration/observability` (local only) now carries all three workstreams' code
together for the first time; none of the three source branches (`fix/telemetry-concurrency`,
`workstream-c-`, `workstream-b-pipeline`) were themselves modified this session. Full narrative
in [[2026-08-29]] session 27.

## 2026-08-21: Observability layer planned -- a recording pipeline plus a second developer-only web service

Design only as of this date; no code exists yet. `docs/ARCHITECTURE.md` does not know about any
of this. Full specifications live in `docs/workstreams/WORKSTREAM_A.md` and
`docs/workstreams/WORKSTREAM_C.md`; rationale in [[DECISIONS]] and [[2026-08-21]] (session 18).

**Three new components, none of which exist yet:**

- `apps/backend/observability/` -- the recorder. Flask request/response hooks, exception capture
  via the `got_request_exception` signal (not an error handler, so it observes without altering
  responses), a `logging.Handler` bridge, a Gemini token meter, `contextvars`-based request
  context, and centralised PII redaction. Terminates at `emit_event()`.
- `apps/backend/logstore/` -- the pipeline and store. A background daemon thread drains the
  recorder's queue, batches ~100 events into one Firestore document, and maintains pre-aggregated
  counters. Also `POST /api/v1/telemetry`, the public browser-ingest endpoint, and `query.py`, the
  read API the log site consumes.
- `apps/logsite/` -- a **second Flask service**, deployed as a second Render web service from this
  same repo (`gunicorn apps.logsite.app:app`), with its own domain and five screens. Reads
  Firestore directly; never calls the main app except one uptime probe.

**New Firestore collections:** `logs/` (batched event documents with an `expires_at` TTL field),
`presence/`, `stats/` (pre-aggregated daily counters via `Increment`), `uptime/`.

**Two properties that are architectural, not incidental:**

1. **The main app never blocks on logging.** `emit_event()` only appends to a bounded in-process
   `queue.Queue` using `put_nowait`, drops on overflow, and cannot raise. All network I/O happens
   on the sink thread. This is what makes the log site "a window to" the main app rather than a
   component of it -- the project's stated hard constraint.
2. **Correlation via `trace_id` + `session_id`.** The browser generates a `session_id` per tab
   session and a fresh `trace_id` per user action, sending both as `X-SentinelScan-Session` /
   `X-SentinelScan-Trace`. Flask reads them into `g`; every backend event inherits them. Grouping
   events by `trace_id` is the entire mechanism behind the requirement to show "the internal work
   behind a button click". **This breaks silently** unless context is explicitly snapshotted and
   restored across the `threading.Thread` boundary in `_run_scan_background`
   (`apps/backend/routes/scan_routes.py:81`) -- `contextvars` do not propagate into new threads.

**Existing architecture is preserved, deliberately.** The eleven workers in
`apps/backend/workers/` gain **zero** new code: they already call `logging.getLogger(__name__)`,
and the logging bridge adopts those existing calls. The "dumb workers" principle in `CLAUDE.md`
section 3 therefore holds by construction rather than by discipline. Likewise the orchestrator is
instrumented through its **existing** `on_progress` callback via a single wrapping line, not a
second callback mechanism.

**Auth reuses what exists.** The log site is gated by `require_auth` + `require_developer` from
`apps/backend/auth/auth_utils.py` and the existing `developers/{uid}` Firestore allowlist -- the
same gate that already protects `dev_routes.py`. No second login system.

**Everything gates behind `SENTINELSCAN_TELEMETRY_ENABLED` (default off)**, which is what allows
the three workstreams to be merged one at a time without any of them affecting production or the
existing 144-test suite.

## 2026-08-20: Graphify code-structure graph added as a second, automatic memory layer

- Added `graphify-out/` (a code-only, LLM-free AST call/import/class graph built by the third-party
  [Graphify](https://github.com/Graphify-Labs/graphify) CLI), `.graphifyignore`, and
  `.claude/skills/graphify/` — sits alongside `knowledge/`, not inside it. `knowledge/` stays
  WHY/intent/history (manual, session-end writes); `graphify-out/` is WHAT-exists/WHERE/HOW-it-connects
  (automatic, code-only, rebuilt only at session-end same as the vault).
- No changes to `apps/backend/` or `apps/frontend/` runtime behavior — this is tooling/process only,
  same category as the 2026-08-07 knowledge-vault entry below.
- Setup was copied from an already-working integration in the user's other project (Clyro), adapted for
  this repo's scope (`apps/backend/`, `apps/frontend/`, `scripts/`, `tests/`) and its own generated/
  sensitive paths (`reports/`, `secrets/`, `.venv/`, `auth_session.json`, `scripts/oauth_client.json`,
  all hard-excluded via `.graphifyignore`).
- See [[2026-08-20]] (session 15) for the full build process and a bug caught mid-build (a minified Vite
  bundle, `apps/frontend/static/react-dist/main.js`, initially polluted 57% of the graph with build-
  artifact noise — excluded and rebuilt) and [[DECISIONS]] for the full rationale, mirroring Clyro's own
  ADR for the same integration.

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

## 2026-08-09: Team secrets bootstrap system added (new Firestore collections + auth layer)

- New Firestore document `config/secrets` (shared dev-environment values: `GEMINI_API_KEY`, `DATABASE_URL`, etc.) and new Firestore collection `developers/{uid}` (an admin-managed allowlist; a doc's mere existence grants access, its content isn't used for anything).
- New `require_developer` decorator in `apps/backend/auth/auth_utils.py`, always used stacked on top of the existing `require_auth` (never standalone) — it assumes `g.user` is already populated. New route `GET /api/v1/dev/bootstrap-secrets` (`apps/backend/routes/dev_routes.py`, blueprint `dev_bp`) is the only consumer so far.
- This is the first place in the codebase with an authorization layer beyond "is this a logged-in user" (`require_auth` alone) — everywhere else (auth/history/scan routes) only checks identity, not role. Precedent for any future role-gated endpoint: add a decorator, not a new token-verification mechanism; stack it after `require_auth`.
- Still consistent with the existing pattern that only the trusted Flask backend ever talks to Firestore directly (via the Admin SDK, which bypasses security rules by design) — there is still no Firestore security-rules file anywhere in this repo, and this change doesn't introduce one. Access control for these two new collections is enforced entirely by `require_developer`, same as `users` is already enforced entirely by `require_auth`.
- New `scripts/` directory: dev tooling only, never imported by or run as part of the deployed Flask app. `admin_seed_secrets.py` / `admin_add_developer.py` are one-off admin scripts; `bootstrap_env.py` is what teammates run. See `scripts/README.md` and [[2026-08-09]] for the full flow and a real wrong-GCP-project gotcha hit and fixed during setup.

## 2026-08-24: Observability read/write layer hardened after the branch-wide review

All 19 findings of [[workstream-b-code-review-2026-08-23]] closed on `workstream-b-pipeline`
(PRs #14 and #15, merged as `d6ef21f` and `00daf3f`). `docs/ARCHITECTURE.md` still knows nothing
about the observability layer at all; this entry records only what changed relative to what
sessions 19-22 built. Full narrative in [[2026-08-24]].

**Read path — `apps/backend/logstore/query.py`**

- **Every read is now bounded on the Firestore side.** `_fetch_batches` takes a `limit`
  (`_MAX_BATCH_SCAN`) and a direction; `query_events` applies a 24-hour default window when
  given neither a time bound nor a cursor. Previously an unfiltered call read every batch
  document ever written and filtered in Python.
- **A cursor now narrows the `created_at` range** to what arrived after it. This is the change
  that makes cursor polling actually cheap rather than merely paginated -- it is what the "zero
  to three documents per poll" arithmetic in `docs/workstreams/WORKSTREAM_C.md` section 10
  assumes, and it was not true before.
- **First-page ordering reversed** (see [[DECISIONS]]) -- return shape unchanged, semantics
  changed.
- **Multi-document reads go through one `get_all` round trip** via a new `_read_documents`
  helper (uptime history, rollup hours), with a per-document fallback for clients without it.
- `get_llm_usage` now splits its range on rollup's real checkpoint
  (`logs_meta/rollup_checkpoint`) rather than an assumed 7-day cutoff, with raw batches covering
  the partial hours at each edge. The rollup branch is only trusted when that checkpoint exists.

**Write path**

- `stats/{date}` no longer carries a `session_ids` array; `unique_sessions` is a scalar counter
  (see [[DECISIONS]]). Reads keep a fallback for documents written before this.
- `rollup.py` advances its checkpoint per chunk of batches rather than once per run, bounding
  the double-counting a crash can cause to one chunk.
- The sink's `SIGTERM` handler chains to whatever handler it replaced, so it no longer prevents
  the process from shutting down under gunicorn.

**Process/deployment**

- `create_app()` now wraps the app in `ProxyFix` (`x_for=1, x_proto=1`) — **app-wide, not
  telemetry-specific**. Behind Render's proxy `get_remote_address()` returned the proxy's
  address, so every visitor shared one flask-limiter bucket. This is the first change in this
  repo to acknowledge the reverse proxy at all.
- The sink thread now only starts when `SENTINELSCAN_TELEMETRY_ENABLED` is on, which is not the
  production default. `render.yaml` declares the flag explicitly as `"0"`.
- `logstore/firestore.indexes.json` composite indexes changed from `created_at DESCENDING` to
  `ASCENDING`. **Not yet verified against a real Firestore project** — the fake client used in
  tests models no indexes, and a missing index fails a query outright at runtime.

**Client — `apps/frontend/static/js/telemetry.js`**

- `newTraceId()` is now **stateful**: it starts a trace and every event captured afterwards
  carries that id, so the `X-SentinelScan-Trace` header `app.js` sends and the events recorded
  in the browser finally share one value. Before this the two could never match and
  requirement 4 ("the internal work behind a button click") produced nothing.
- The client sends the signed-in user's Firebase ID token, so `uid` is derived server-side
  instead of always being null. Events sent via `sendBeacon` on page unload remain anonymous —
  beacons cannot carry headers.
- Public surface gained `getTraceId()` and `correlationHeaders()`. `app.js` needed no change.
