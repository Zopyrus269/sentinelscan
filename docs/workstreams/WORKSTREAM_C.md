# Workstream C — The Log Site

**Owner:** Danny
**Branch:** `workstream-c-logsite`
**Service you build:** `apps/logsite/`

> This document is self-contained. It assumes you have never seen this project before and
> have no access to the conversation that produced it. Everything you need is here. If you
> are an AI coding agent, read this file end to end before writing any code.

---

## 1. Orientation — what you are working on

### 1.1 What SentinelScan is

SentinelScan is an AI-driven website reconnaissance and security-assessment tool. A user
enters a domain; the backend runs a read-only assessment against it and produces a PDF/JSON
report with CVSS-scored findings.

Its defining architectural idea: **Google's Gemini is the only decision-maker.** Gemini
dynamically chooses which of eleven single-purpose "dumb" workers to run next, based on what
previous workers found. The workers (`apps/backend/workers/`) contain zero business logic.
All intelligence and state live in the agent layer (`apps/backend/agent/orchestrator.py`).

Relevant facts about the stack:

| Thing | Detail |
|---|---|
| Backend | Flask, application factory in `apps/backend/app.py` |
| Deployment | Render free tier, **single gunicorn worker** (state is per-process) |
| Auth | Firebase Authentication (Google Sign-In) + Firebase Admin SDK |
| Database | Firestore only. There is no SQL database anywhere in this project |
| Frontend | Static HTML pages plus a React bundle compiled by Vite into an IIFE |
| Tests | `pytest tests/` — currently **144 passed, 1 skipped** |
| Live site | `https://sentinelscan-yd2u.onrender.com` |

Scope is strictly passive reconnaissance against authorized targets. **Never write, generate,
or suggest exploit code** anywhere in this project.

### 1.2 The problem this project solves

Today, when a user reports a bug, there is no record of what they did. Render's free tier
keeps no durable logs. The codebase calls `logging.getLogger(__name__)` in thirteen modules,
but no handler is ever configured, so almost all of that output goes nowhere. Nothing at all
is captured from the browser.

So debugging a user report means re-reading code and guessing.

### 1.3 What is being built

Two things:

1. **A recording layer** inside the main app that writes down everything that happens.
2. **A second, developer-only website — the one you are building** — that reads those
   recordings back.

When a user says "something broke", a developer opens your site, finds that person's session,
and reads exactly what happened, without reading any code.

**Hard constraint: your site must never slow the main site down.** It is a *window* into the
main app, not a component of it. Your site reads Firestore directly and never calls the main
app, with one exception: a scheduled uptime probe.

### 1.4 The six things your site must show

This is the acceptance criteria for the whole project. Your five screens deliver all six.

1. Whether the main website is up and running
2. The number of active users right now
3. Each user's activity, with timestamps
4. The internal work behind a button click, which the user never sees
5. Gemini API token usage
6. Overall website health

### 1.5 The three workstreams

The project is split three ways, built in parallel, merged by one integrator.

| | Who | Builds | Role |
|---|---|---|---|
| **A** | Sanjana | `apps/backend/observability/` | Notices things happen and describes them |
| **B** | Shreyas | `apps/backend/logstore/` | Batches records into Firestore; answers queries |
| **C** | **Danny (you)** | `apps/logsite/` | The second website that displays it all |

Analogy: the project is a CCTV system. A installs the cameras. B lays the cables and runs the
tape room. **You build the viewing room.**

**Shreyas is the integrator.** He merges all three branches at the end. Every rule in
section 3 exists to make that merge painless.

### 1.6 Where your work fits

```
   MAIN SITE (public)                      YOUR SITE (developer-only)
   ┌─────────────────────┐                 ┌──────────────────────────┐
   │ A records events    │                 │ 5 screens                │
   │ B batches them into │                 │ Firebase Google sign-in  │
   │ Firestore           │                 │ developer allowlist gate │
   └──────────┬──────────┘                 └────────────┬─────────────┘
              │ writes                                  │ reads
              ▼                                         │
        ┌──────────────────────────────────────────────▼┐
        │ FIRESTORE:  logs/  presence/  stats/  uptime/  │
        └───────────────────────────────────────────────┘

   You never call the main site, except one uptime probe every 5 minutes.
   That is what keeps your site a window rather than a component.
```

You only ever **read**. You call Workstream B's `query.py` functions (section 5) and render
the results. You never write application data.

---

## 2. Your scope

### 2.1 What you build

- `apps/logsite/` — a complete second Flask service with its own web address: backend API,
  developer authentication, and five plain HTML/JS screens.
- `.github/workflows/uptime-probe.yml` — a scheduled job that pings the main site every five
  minutes so uptime is recorded even while both services are asleep.
- `apps/logsite/INTEGRATION.md` — the deployment instructions Shreyas applies.
- `tests/test_logsite_*.py`.

### 2.2 What you must NOT build

- **The browser-side `telemetry.js` that records clicks on the main site is not yours.**
  It belongs to Workstream B, because it is the client half of B's ingest endpoint. Do not
  write it, and do not touch `apps/frontend/`.
- **You do not edit `render.yaml`.** You describe the change in your `INTEGRATION.md` and
  Shreyas applies it.
- **You do not build a second login system.** Reuse the one that already exists (section 7).
- **You do not edit a single existing file in this repository.** Not one.

---

## 3. Working rules

These are binding. They exist so that combining three parallel branches produces close to
zero conflicts.

### R1 — File ownership is absolute

You may create and edit only:

- `apps/logsite/**`
- `.github/workflows/uptime-probe.yml`
- `tests/test_logsite_*.py`

Nothing else. If you believe you need to touch something outside this list, **stop and ask
Shreyas** rather than doing it.

For reference, the other owners:

| Owner | Owns |
|---|---|
| A (Sanjana) | `apps/backend/observability/**`, `tests/test_observability_*.py` |
| B (Shreyas) | `apps/backend/logstore/**`, `apps/backend/routes/telemetry_routes.py`, `scripts/seed_fake_logs.py`, `tests/test_logstore_*.py`, `tests/test_telemetry_*.py` |
| C (you) | `apps/logsite/**`, `.github/workflows/uptime-probe.yml`, `tests/test_logsite_*.py` |
| Integrator only | `app.py`, `gemini_client.py`, `orchestrator.py`, `scan_routes.py`, `apps/frontend/**`, `render.yaml`, `requirements.txt`, `docs/**`, `knowledge/**`, `CLAUDE.md`, `graphify-out/**` |

### R2 — No workstream edits any existing file

Everything you would want to change in an existing file goes into your `INTEGRATION.md` as an
instruction instead. For you that means `render.yaml`, the Firebase console settings, and the
Firestore index/TTL deployment.

### R3 — Never edit `requirements.txt` or any `package.json`

List new dependencies in `INTEGRATION.md` with justification. **The target is zero new
dependencies.** Your service needs `flask` and `firebase-admin`, both already installed. Your
frontend is plain HTML and vanilla JavaScript with Tailwind from a CDN — there is no build
step and no npm package for your site.

### R4 — The event schema is frozen

Section 4 defines it. The identical schema block appears in Sanjana's handoff document.
Changing a field name or type silently breaks the other two workstreams, which are coded
against it blind. **Any change requires Shreyas's sign-off first.**

### R5 — Imports are a one-way DAG

`logsite` imports only `apps.backend.logstore.query` and `apps.backend.auth.auth_utils`.
Nothing else from the main app. Nothing ever imports *from* `logsite`. This prevents
circular-import failures that only surface at merge time.

### R6 — Everything is off by default

The main app's recording gates behind `SENTINELSCAN_TELEMETRY_ENABLED`, default `"0"`. Your
site is a separate service, so it is "off" simply by not being deployed — but it must still
degrade gracefully when the collections it reads are empty. Every screen needs a sensible
empty state, not a stack trace.

### R7 — Tests are additive and isolated

Never modify an existing test file. New tests go in new files named `tests/test_logsite_*.py`.
With your branch checked out, `pytest tests/` must still report **at least 144 passed,
1 skipped**.

### R8 — Work on your branch however you like; no pull request is required of you

Branch: `workstream-c-logsite`. Commit and push to it as often as you want, in whatever style
suits you. There is no review gate, no PR ceremony, no approval needed. Just tell Shreyas when
your branch is ready.

The project's "every merge needs a PR" rule applies **only to merging into `main`**, and only
Shreyas performs that step. (GitHub branch protection blocks direct pushes to `main` for
everyone — this does not affect pushing your own branch.)

One convention does apply to everyone: **never add a `Co-Authored-By:` trailer to a commit.**
Commits show only your own git identity. No "Generated with…" footers either.

### R9 — Do not regenerate `graphify-out/`

That directory holds a ~30,000-line generated code graph. If more than one person regenerates
it, the merge conflict is unresolvable. Shreyas regenerates it once, at the end. You may read
it freely.

### R10 — Anything written under `knowledge/` will be discarded

`knowledge/` is Shreyas's personal Claude Code memory vault. It is tracked in git, so a copy
will appear when you pull `main`, and some AI agent workflows write to it automatically at the
end of a session.

That is fine and nothing to worry about — **at integration, Shreyas discards every
`knowledge/` change coming from any branch, unread.** The only consequence for you: nothing
you put there survives, so do not record anything you need in it. Read it if useful.
Everything required to do this workstream is in the file you are reading.

### R11 — Names are part of the contract

Module paths, function names, environment variable names and route paths are specified exactly
in this document. Match them character-for-character. Workstream B is writing the query
functions you call without being able to see your code.

### R12 — No secrets

Never commit a real key, token, or `secrets/`-shaped file. Gitleaks runs in CI
(`.github/workflows/secret-scanning.yml`) and will fail the build. The one apparent exception
is the Firebase **client** config (`apiKey`, `authDomain`, `projectId`, …) — that is public by
design, is already committed at `apps/frontend/static/js/auth.js` lines 4-11, and is safe to
copy into your site. Everything else is a secret.

### R13 — Integration is Shreyas's job, in order A → B → C

You do not merge anything. When your branch is ready, tell him. He merges A, then B, then C
into an integration branch, applies each `INTEGRATION.md`, runs the full suite, and opens one
PR into `main`.

---

## 4. The frozen event schema

This is what a single record looks like. Your screens render these.

```jsonc
{
  "event_id": "uuid4 string",
  "ts": "2026-08-21T14:22:03.123456+00:00",   // ISO-8601, UTC, always tz-aware
  "level": "debug|info|warn|error|fatal",
  "source": "frontend|backend|agent|worker",
  "category": "http|auth|scan|agent|worker|llm|ui|error|health",
  "message": "human-readable one-liner",
  "trace_id": "uuid4 string or null",   // ties a click to the backend work it caused
  "session_id": "uuid4 string or null", // one browser tab session
  "uid": "firebase uid or null",        // server-derived, never client-supplied
  "scan_id": "string or null",
  "duration_ms": 0,
  "data": { },                          // category-specific, already redacted
  "release": "git sha or 'dev'",
  "env": "prod|dev"
}
```

Rules:

- Every key is always present. Use `null`, not omission.
- `data` is category-specific and already redacted before it ever reaches you.
- Never render `data` blindly into HTML. Escape everything — see section 9.3.

**The two id fields are the heart of the product.** `session_id` is one person's visit;
`trace_id` is one user action plus every piece of backend work it caused. Requirement 4 is
implemented by grouping events that share a `trace_id`.

### 4.1 What each category looks like

| Category | Source | Meaning | Key `data` fields |
|---|---|---|---|
| `http` | backend | One request/response | `method`, `path`, `route`, `status`, `ip_hash`, `ua`, `query_keys` |
| `ui` | frontend | A click or navigation in the browser | `action`, `target`, `label`, `route` |
| `llm` | agent | One Gemini API call | `model`, `prompt_tokens`, `response_tokens`, `total_tokens`, `cached`, `retries` |
| `agent` | agent | The AI choosing or finishing a stage | `tool_name`, `phase`, `iteration`, `reasoning`, `action` |
| `worker` | worker | One of the eleven workers running | `logger`, `func`, `line` |
| `error` | backend/frontend | A crash | `type`, `stack`, `fingerprint`, `route` |
| `auth` | backend | Sign-in / session events | `event`, `provider` |
| `scan` | backend | Scan lifecycle | `target`, `status` |
| `health` | health | Uptime probe results | `component`, `ok`, `latency_ms` |

`fingerprint` on an `error` is a short stable hash identifying "the same bug". Group by it to
show "this crash happened 47 times".

---

## 5. The data layer you code against (Workstream B's contract)

You do **not** talk to Firestore directly. You call these functions, which Shreyas is
building in `apps/backend/logstore/query.py`. Treat these signatures as fixed.

```python
def query_events(*, since=None, until=None, level=None, source=None, category=None,
                 session_id=None, uid=None, trace_id=None, scan_id=None,
                 cursor=None, limit=200) -> dict
    # -> {"events": [ ...event dicts... ], "next_cursor": str | None}

def list_sessions(*, since=None, limit=50) -> list[dict]
    # -> [{"session_id", "uid", "email", "started_at", "last_seen",
    #      "event_count", "error_count", "routes": [...]}, ...]

def get_session_timeline(session_id: str) -> dict
    # -> {"session_id", "uid", "started_at", "last_seen",
    #     "events": [ ...ordered by ts ascending... ]}

def get_trace(trace_id: str) -> dict
    # -> {"trace_id", "events": [...]}  everything sharing one user action

def count_active_users(window_minutes: int = 5) -> dict
    # -> {"count": int, "sessions": [{"session_id", "uid", "last_seen"}, ...]}

def get_daily_stats(date: str) -> dict
    # -> {"date", "events", "errors", "requests", "scans",
    #     "llm_calls", "llm_tokens", "unique_sessions"}

def get_llm_usage(*, since=None, until=None, group_by="day") -> dict
    # -> {"total_tokens", "prompt_tokens", "response_tokens", "calls",
    #     "cache_hits", "buckets": [{"bucket", "tokens", "calls"}, ...]}

def get_health_snapshot() -> dict
    # -> {"error_rate", "p50_ms", "p95_ms", "requests_1h",
    #     "workers": [{"name", "ok", "failed", "success_rate"}, ...],
    #     "llm_failure_rate"}

def get_uptime_history(days: int = 90) -> list[dict]
    # -> [{"date", "uptime_pct", "checks", "failures"}, ...]

def record_uptime_probe(result: dict) -> None
    # the only write you perform, and only from the probe endpoint
```

**Firestore collections** (owned by B, read-only to you): `logs/`, `presence/`, `stats/`,
`uptime/`.

**If `query.py` does not exist yet on your branch**, that is expected — build against a local
stub with the same signatures returning fake data, and delete the stub before you finish.
Shreyas is also providing `scripts/seed_fake_logs.py`, which populates realistic data so you
can build every screen before Workstreams A and B are finished.

---

## 6. File-by-file specification

```
apps/logsite/
  __init__.py
  app.py                 the Flask application factory
  auth.py                developer gate (thin wrapper — see section 7)
  api.py                 the HTTP API (section 8)
  probe.py               uptime probe ingest + history
  INTEGRATION.md         deployment instructions for Shreyas
  frontend/
    index.html           screen 1 — status board (the default landing screen)
    live.html            screen 2 — live activity feed
    sessions.html        screen 3 — session list and timeline
    llm.html             screen 4 — Gemini usage
    health.html          screen 5 — health
    static/
      css/logsite.css
      js/auth.js         Firebase Google sign-in + developer gate
      js/api.js          fetch wrapper that attaches the ID token
      js/status.js
      js/live.js
      js/sessions.js
      js/llm.js
      js/health.js
```

### 6.1 `app.py`

Its own application factory, entirely separate from the main app's.

```python
def create_app() -> Flask:
    """Builds the developer-only log site."""
```

Requirements:

- Register the `api` and `probe` blueprints.
- Serve `frontend/` as static files, with `index.html` at `/`.
- Security headers on every response, via `after_request`:
  - `X-Robots-Tag: noindex, nofollow` — this site must never be indexed
  - `X-Frame-Options: DENY`
  - `X-Content-Type-Options: nosniff`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - A Content-Security-Policy. Model it on the main app's
    (`apps/backend/app.py` lines 44-55), which already permits the Firebase
    sign-in scripts and frames you need. Copy that structure rather than inventing one, or
    Google sign-in will break in ways that are tedious to debug.
  - Pop the `Server` and `X-Powered-By` headers.
- An unauthenticated `GET /healthz` returning `{"status": "ok"}` — Render's own health check
  needs this and must not require a login.
- Module-level `app = create_app()` so gunicorn can find it.

### 6.2 `auth.py`

Deliberately thin. See section 7 — you are reusing the existing gate, not building one.

### 6.3 `api.py`

The endpoints in section 8. Every handler:

- Is decorated `@require_auth` then `@require_developer`.
- Parses and validates its query parameters, rejecting nonsense with a 400 rather than
  passing it through to Firestore.
- Calls exactly one `query.py` function and returns its result as JSON.
- Contains no business logic of its own. Aggregation lives in B's layer; this is a thin,
  well-validated HTTP surface over it.
- Returns the project's standard error shape on failure:
  `{"error": "...", "message": "...", "code": 400}` with a matching HTTP status. This mirrors
  `_error()` in `apps/backend/routes/scan_routes.py`.

### 6.4 `probe.py`

Two responsibilities:

- `POST /api/probe` — receives an uptime result from the GitHub Action. **This is the only
  unauthenticated-by-Firebase endpoint that writes anything**, so it is gated by a shared
  secret instead: compare an `X-Probe-Token` header against the `LOGSITE_PROBE_TOKEN`
  environment variable using `hmac.compare_digest` (constant-time — a plain `==` leaks timing
  information). Reject with 401 on mismatch. Validate the body strictly.
- A helper that reads uptime history for the status board.

### 6.5 `frontend/`

Plain HTML, vanilla JavaScript, Tailwind from a CDN. **No build step, no npm, no framework.**

The main site has a React/Vite build (`apps/frontend/react-app/`) — **do not use it, do not
import from it, and do not add your site to its build config.** Your site is intentionally
plain: it is an internal tool, and a build step would make it harder to maintain than the
thing it monitors.

Aim for the look of `status.claude.com` or `status.gemini.google.com`: dense, calm, monospace
for data, large coloured state indicators, no animation.

Shared JavaScript:

- `js/auth.js` — Firebase Google sign-in. Copy the `firebaseConfig` object verbatim from
  `apps/frontend/static/js/auth.js` (lines 4-11); it is the same Firebase project and the
  config is public by design. Expose `window.getIdToken()`.
- `js/api.js` — one `apiFetch(path, params)` helper that attaches
  `Authorization: Bearer <idToken>`, handles 401 by prompting sign-in, and handles 403 by
  showing "this account is not on the developer allowlist".

---

## 7. Authentication — reuse, do not rebuild

A developer allowlist **already exists** in this project and already protects a sensitive
endpoint. Use it.

- `apps/backend/auth/auth_utils.py` provides two decorators:
  - `require_auth` — verifies a Firebase ID token from the `Authorization: Bearer <token>`
    header and populates `flask.g.user` with `uid`, `email`, `name`.
  - `require_developer` — checks that a Firestore document exists at `developers/{uid}`. The
    document's contents are irrelevant; its existence is the allowlist entry. **Must be
    applied below `require_auth`** in the decorator stack, since it reads `g.user`.
- `apps/backend/routes/dev_routes.py` shows exactly how to stack them — read it first, it is
  45 lines.
- `scripts/admin_add_developer.py` adds a teammate to the allowlist. Shreyas runs it for all
  three of you.

So every one of your API handlers looks like:

```python
@api_bp.route("/status", methods=["GET"])
@require_auth
@require_developer
def status():
    ...
```

**Do not** invent a password, a shared link, an IP allowlist, or a second Firebase project.
The gate that exists is the gate.

**One deployment detail that will otherwise waste your afternoon:** Firebase only permits
sign-in from domains on its authorized-domains list. That list currently contains `localhost`
and the main Render domain. Your new site's domain **must be added in the Firebase console**
or Google sign-in fails with an opaque error. Put this in your `INTEGRATION.md` — it is a
console setting, not a code change, so only Shreyas can do it.

---

## 8. The log site's HTTP API

Your backend serves these. Your frontend consumes them. Nothing else consumes them.

| Method | Path | Auth | Returns |
|---|---|---|---|
| GET | `/healthz` | none | `{"status": "ok"}` |
| GET | `/api/status` | dev | Component tiles plus overall state |
| GET | `/api/uptime?days=90` | dev | `get_uptime_history(days)` |
| GET | `/api/active-users?window=5` | dev | `count_active_users(window)` |
| GET | `/api/events` | dev | `query_events(...)` — filters below |
| GET | `/api/sessions?since=&limit=` | dev | `list_sessions(...)` |
| GET | `/api/sessions/<session_id>` | dev | `get_session_timeline(session_id)` |
| GET | `/api/traces/<trace_id>` | dev | `get_trace(trace_id)` |
| GET | `/api/llm-usage?since=&until=&group_by=` | dev | `get_llm_usage(...)` |
| GET | `/api/health` | dev | `get_health_snapshot()` |
| GET | `/api/stats/<date>` | dev | `get_daily_stats(date)` |
| POST | `/api/probe` | `X-Probe-Token` | `204` |

`GET /api/events` query parameters: `since`, `until`, `level`, `source`, `category`,
`session_id`, `uid`, `trace_id`, `scan_id`, `cursor`, `limit` (default 200, **hard maximum
500** — reject larger values with a 400 rather than silently clamping, so a caller's bug is
visible).

`GET /api/status` response shape:

```json
{
  "overall": "operational|degraded|down",
  "checked_at": "2026-08-21T14:30:00+00:00",
  "components": [
    {"name": "Web",       "state": "operational", "detail": "200 in 412ms"},
    {"name": "Scan API",  "state": "operational", "detail": "error rate 0.4%"},
    {"name": "Gemini",    "state": "degraded",    "detail": "3 failures in last hour"},
    {"name": "Firestore", "state": "operational", "detail": null},
    {"name": "Workers",   "state": "operational", "detail": "success rate 96%"}
  ]
}
```

Derive `overall` from the worst component state. Define the thresholds as named module
constants, not magic numbers scattered through the code.

---

## 9. The five screens

### 9.1 Screen 1 — Status board (`index.html`) → requirements 1 and 6

The landing screen. Modelled on `status.claude.com`.

- A large overall banner: "All systems operational" in green, or degraded/down in amber/red.
- One tile per component from `/api/status`, each with a coloured state dot and one line of
  detail.
- Beneath each, a **90-day uptime bar**: 90 thin vertical bars, green for a fully healthy day,
  amber for partial, red for a day with failures, grey for no data. From `/api/uptime`.
- An overall uptime percentage for the period.
- Refresh every 60 seconds. This screen is cheap — it reads one pre-aggregated counters
  document, never raw events.

### 9.2 Screen 2 — Live activity feed (`live.html`) → requirements 2 and 3

- A prominent **active user count** from `/api/active-users` (default 5-minute window), with
  the contributing sessions listed beneath.
- A reverse-chronological stream of events, newest first, auto-refreshing.
- Each row: timestamp, a coloured level chip, source, and message. Errors visually distinct.
- Filter controls for level, source and category. Filtering re-queries from the server; it
  does not filter client-side over a partial window.
- Clicking any row with a `session_id` jumps to that session's timeline.

**This screen must use cursor polling.** See section 10 — it is a hard requirement, not an
optimisation.

### 9.3 Screen 3 — Session timeline (`sessions.html`) → requirements 3 and 4

**This is the screen that justifies the entire project.** Everything else is supporting cast.
Build it first, and spend your quality time here.

Two panes.

**Left — session list**, from `/api/sessions`: user email or "anonymous", when the visit
started, how long it lasted, event count, and an error badge when the visit contained a crash.
Sessions with errors sort to the top by default, because those are the ones anybody actually
opens this site to look at.

**Right — the timeline**, from `/api/sessions/<id>`: that person's visit as a vertical,
timestamped list.

The critical interaction: **each top-level user action is expandable, and expanding it reveals
everything the server did underneath.** Group by `trace_id`. A `ui` or `http` event is the
collapsed header; every other event sharing its `trace_id` is a child.

Collapsed:

```
14:22:01   nav      opened /dashboard
14:22:03   click    "Start Scan"                              ▸ 23 events   1.4s
14:22:19   error    TypeError in report.js:412                ▸ 2 events
```

Expanded:

```
14:22:03   click    "Start Scan"                              ▾ 23 events   1.4s
           ├ 14:22:03.118  http    POST /api/v1/scans -> 202          181ms
           ├ 14:22:03.301  scan    scan started: target=acme.com
           ├ 14:22:04....    llm     gemini: 1204 + 88 tokens           940ms
           ├ 14:22:05....    agent   AI selected dns_lookup
           │                       "Resolving the domain first establishes ..."
           ├ 14:22:06....    worker  dns_lookup COMPLETED               1.2s
           ├ 14:22:19....    worker  ssl_check TIMEOUT                  10.0s
           └ 14:22:19....    error   TypeError: cannot read 'score'
                                   at renderReport (report.js:412)
```

Requirements for this view:

- Show elapsed time between consecutive events; a long gap is usually the bug.
- Colour by level; make errors impossible to miss.
- Render the `reasoning` field on `agent` events — that is the AI explaining its own decision,
  and it is often the fastest route to understanding a weird scan.
- A "copy as text" button producing a plain-text timeline that can be pasted into a chat.
- Deep-link support: `sessions.html?session_id=<id>&trace_id=<id>` opens that session with
  that action already expanded, so developers can share a link to a specific bug.

**Escape everything.** Event messages contain user-supplied text — scan targets, error strings
from remote servers. Build DOM nodes with `textContent`, or escape rigorously before
`innerHTML`. An unescaped `<script>` in a scanned domain's error message would be a
self-inflicted XSS in your own debugging tool.

### 9.4 Screen 4 — Gemini usage (`llm.html`) → requirement 5

From `/api/llm-usage`:

- Total tokens today, this week, and over a selectable range.
- Split between prompt and response tokens.
- A simple bar chart per day or hour. Plain SVG or CSS bars — **do not add a charting
  library** (R3).
- Cache hit rate. The client caches identical requests in SQLite
  (`apps/backend/agent/gemini_cache.sqlite3`) specifically to survive the free tier's rate
  limits, so this number matters.
- Tokens per scan, and the most expensive recent scans.
- Call rate against the free-tier limit. The client enforces a minimum 2-second gap between
  calls (`MIN_SECONDS_BETWEEN_CALLS` in `apps/backend/agent/gemini_client.py`); surface how
  close usage runs to the ceiling.
- An estimated cost figure. Make the per-token rate a clearly-labelled constant so it can be
  corrected without hunting through code.

### 9.5 Screen 5 — Health (`health.html`) → requirement 6

From `/api/health`:

- Error rate over the last hour and last 24 hours.
- Request latency p50 and p95.
- A per-worker table: each of the eleven workers with success/failure counts and a success
  rate. This is genuinely useful — a worker quietly failing 40% of the time against real
  targets is invisible today.
- Gemini failure and retry rate.
- The most frequent errors, grouped by `fingerprint`, with counts and a link to the most
  recent occurrence's session.

---

## 10. Cursor polling — a hard requirement

Firestore's free tier allows **50,000 document reads per day**, shared across everything.

Naive auto-refresh breaks this. Three developers, four hours each, refreshing every 20
seconds, reading 50 events each time:

```
3 devs × 4 h × 180 polls/h × 50 docs  =  108,000 reads/day
```

That is more than double the daily allowance, from three people idling with a tab open. The
site would stop working — and so would the main app's history feature, since they share the
quota.

**The fix:** every polling screen keeps the `next_cursor` from its last response and sends it
as `?cursor=` on the next poll. The server returns only what is new, which is usually zero to
three documents.

```
3 devs × 4 h × 120 polls/h × ~2 docs  ≈  2,900 reads/day
```

Rules that follow from this:

- Poll every 30 seconds, not every 5.
- Never re-query a whole time window on a timer. Only user-initiated filter changes do a
  fresh query.
- The status board reads one pre-aggregated counters document, never a scan over raw events.
- Pause polling when the tab is hidden (`document.visibilityState`) and resume on focus.
- Show the reader when data last refreshed, so a paused tab is never mistaken for a quiet
  system.

---

## 11. Deployment (specify in `INTEGRATION.md`, do not do it yourself)

Your site is a second Render service, built from this same repository.

- **`render.yaml`** gains a second entry alongside the existing `sentinelscan` service:
  name `sentinelscan-logs`, `branch: main`, `autoDeploy: true`,
  `buildCommand: pip install -r requirements.txt`,
  `startCommand: gunicorn --workers 1 --bind 0.0.0.0:$PORT apps.logsite.app:app`,
  `healthCheckPath: /healthz`. Environment variables:
  `FIREBASE_SERVICE_ACCOUNT_PATH`, `LOGSITE_PROBE_TOKEN`, `MAIN_SITE_URL`.
  Write the exact YAML block in your `INTEGRATION.md`; do not edit the file (R2).
- **Firebase console**: add the new Render domain to authorized domains (section 7).
- **Firestore**: deploy the composite indexes and the TTL policy that Workstream B defines.
  Reference it; B owns the specifics.
- **GitHub secret**: `LOGSITE_PROBE_TOKEN`, matching the Render environment variable, for your
  workflow to use.

**Free-tier behaviour worth knowing.** Render sleeps a free service after 15 minutes of
inactivity, so your site takes roughly 30-50 seconds to wake. That is fine for an internal
tool. Critically, **recording is unaffected** — it happens on the main service, so no data is
lost while your site sleeps. Add a "waking up…" message rather than letting the first load
look broken.

### 11.1 `.github/workflows/uptime-probe.yml`

This file you *do* own and create.

- Schedule: `*/5 * * * *`.
- Steps: `curl` the main site's `/health` endpoint with a timeout, measure the response time,
  then `POST` the result to your site's `/api/probe` with the `X-Probe-Token` header from
  `secrets.LOGSITE_PROBE_TOKEN`.
- Record failures as data, not as a red workflow run — `curl --fail` on a down site would mark
  the job failed and stop the run before it reports anything. Capture the outcome and always
  post it. A workflow that goes red exactly when the site goes down is the opposite of useful.
- Body: `{"component": "web", "ok": true|false, "status": 200, "latency_ms": 412,
  "checked_at": "…"}`.
- Keep `permissions:` minimal (`contents: read`).

This also usefully keeps the main service warm.

---

## 12. Working alone

You do not need Workstreams A or B to exist.

1. Ask Shreyas for `scripts/seed_fake_logs.py`, or write a local throwaway stub of `query.py`
   returning realistic fake data with the exact signatures in section 5.
2. Build all five screens against it.
3. Delete any stub before you finish, and confirm the real signatures still match.

Running your site locally:

```bash
python -m apps.logsite.app
```

**Use `http://localhost:5000` if you need Google sign-in to work** — Firebase's authorized
domains cover `localhost` only on that basis. If you run both services locally at once, put
the log site on a different port and expect sign-in to need the extra domain registered.

If a fresh clone is missing `flask_limiter` or `playwright`, run
`pip install -r requirements.txt`.

Your demo for Shreyas: open the site, sign in, and walk through all five screens with seeded
data — expanding a click on the timeline to show the backend work underneath it.

---

## 13. Tests

New files only, named `tests/test_logsite_*.py`. The suite currently reports **144 passed,
1 skipped**; it must still do so with your branch checked out.

Required coverage:

| File | Must prove |
|---|---|
| `test_logsite_auth.py` | Every `/api/*` route returns 401 without a token and 403 for a non-allowlisted user; `/healthz` needs no auth |
| `test_logsite_api.py` | Each endpoint validates parameters, rejects `limit` over 500, returns the documented shape, and returns a sensible empty state when collections are empty |
| `test_logsite_probe.py` | `/api/probe` rejects a missing or wrong token; uses a constant-time comparison; validates the body; returns 204 on success |
| `test_logsite_headers.py` | `X-Robots-Tag: noindex` and the other security headers are present on every response |

Use Flask's test client and monkeypatch the `query.py` functions — your tests must not require
a live Firestore. Follow the style of `tests/test_dev_routes.py`, which already tests
allowlist-gated routes. Never use a real credential in a fixture (R12).

---

## 14. Definition of done

Tick every box before telling Shreyas the branch is ready.

- [ ] `apps/logsite/` contains every file from section 6
- [ ] All five screens work end to end against seeded data
- [ ] The session timeline expands a click to reveal the backend work sharing its `trace_id`
- [ ] Deep-linking to a specific session and trace works
- [ ] Every polling screen uses cursor polling and pauses on a hidden tab (section 10)
- [ ] All `/api/*` routes are gated by `require_auth` + `require_developer`; `/healthz` is not
- [ ] `X-Robots-Tag: noindex` is on every response
- [ ] `/api/probe` uses `hmac.compare_digest`, never `==`
- [ ] All event text is escaped before rendering (section 9.3)
- [ ] Zero existing files modified — verify with `git diff --name-only main...HEAD`
- [ ] `requirements.txt` untouched; no new dependency; no charting library; no npm package
- [ ] `apps/logsite/INTEGRATION.md` written, covering `render.yaml`, the Firebase domain, the Firestore indexes/TTL, and the GitHub secret
- [ ] `.github/workflows/uptime-probe.yml` exists and reports a down site as data, not as a failed run
- [ ] `pytest tests/` reports at least 144 passed, 1 skipped
- [ ] All four test files from section 13 exist and pass
- [ ] Any local stub of `query.py` has been deleted
- [ ] No secret-shaped string anywhere in the diff (R12)
- [ ] Nothing under `knowledge/`, `graphify-out/`, `apps/frontend/`, or another workstream's paths is in your diff
- [ ] Every public function has a type-hinted signature and a docstring
- [ ] No commit carries a `Co-Authored-By:` trailer

---

## 15. Git workflow

```bash
git checkout main
git pull
git checkout -b workstream-c-logsite

# ... work, committing as often as you like ...
git add apps/logsite .github/workflows/uptime-probe.yml tests/test_logsite_*.py
git commit -m "feat(logsite): add status board and session timeline"

git push -u origin workstream-c-logsite
```

Commit style: conventional prefixes (`feat(...)`, `fix(...)`, `test(...)`, `docs(...)`), small
and atomic. **No `Co-Authored-By:` trailer, ever.**

Stage your own paths explicitly rather than using `git add -A`, so nothing from `knowledge/`
or `graphify-out/` is swept in accidentally.

When the checklist in section 14 is complete, tell Shreyas. Do not merge anything yourself.

---

## 16. Questions

Anything not answered here — especially anything that would require changing the event schema
(R4), changing a `query.py` signature (section 5), adding a dependency (R3), or touching a
file outside your ownership (R1) — goes to Shreyas before you act on it. A guess that diverges
from the frozen contract costs all three workstreams a rewrite.
