# Workstream A — The Recorder

**Owner:** Sanjana
**Branch:** `workstream-a-recorder`
**Package you build:** `apps/backend/observability/`

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
previous workers found. The workers (`apps/backend/workers/`) contain zero business logic —
they execute exactly one job and return structured JSON. All intelligence and state live in
the agent layer (`apps/backend/agent/orchestrator.py`).

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
but **no handler is ever configured**, so almost all of that output goes nowhere. Nothing at
all is captured from the browser.

So debugging a user report means re-reading code and guessing.

### 1.3 What is being built

Two things:

1. **A recording layer** inside the main app that writes down everything that happens.
2. **A second, developer-only website** that reads those recordings back, showing whether the
   site is up, who is active, each user's activity with timestamps, the internal work behind
   each button click, Gemini token usage, and overall health.

When a user says "something broke", a developer opens the log site, finds that person's
session, and reads exactly what happened — without reading any code.

**Hard constraint: the log site must never slow the main site down.** It is a *window* into
the main app, not a component of it.

### 1.4 The three workstreams

The project is split three ways. They are being built in parallel, by different people, and
merged by one integrator.

| | Who | Builds | Role |
|---|---|---|---|
| **A** | **Sanjana (you)** | `apps/backend/observability/` | Notices things happen and describes them |
| **B** | Shreyas | `apps/backend/logstore/` | Batches records into Firestore; answers queries |
| **C** | Danny | `apps/logsite/` | The second website that displays it all |

Analogy: the project is a CCTV system. **You install the cameras.** B lays the cables and runs
the tape room. C builds the viewing room.

**Shreyas is the integrator.** He merges all three branches together at the end. Every rule in
section 3 exists to make that merge painless.

### 1.5 Where your work fits

```
   ┌──────────────────────────────────────────┐
   │  YOU (Workstream A)                      │
   │                                          │
   │  Flask request hooks ──┐                 │
   │  Error capture ────────┤                 │
   │  logging bridge ───────┼──► emit_event() │──┐
   │  Gemini token meter ───┤                 │  │
   │  Orchestrator progress ┘                 │  │
   └──────────────────────────────────────────┘  │
                                                 │  a bounded in-memory queue
   ┌─────────────────────────────────────────────▼───┐
   │  Workstream B — drains the queue, batches,      │
   │  writes to Firestore, answers queries           │
   └─────────────────────────────────────────────────┘
                                                 │
   ┌─────────────────────────────────────────────▼───┐
   │  Workstream C — the log website (read-only)     │
   └─────────────────────────────────────────────────┘
```

You produce events and hand them to `emit_event()`. **You never care what happens next.** B
collects from the other side of that function. You can build, test, and demo your entire
workstream with events simply printing to the terminal.

---

## 2. Your scope

### 2.1 What you build

A new Python package, `apps/backend/observability/`, containing nine modules, plus tests.
Full specification in section 5.

### 2.2 What you must NOT touch

**You do not edit a single existing file in this repository.** Not one.

That includes the four files your code obviously needs to hook into:

- `apps/backend/app.py`
- `apps/backend/agent/gemini_client.py`
- `apps/backend/agent/orchestrator.py`
- `apps/backend/routes/scan_routes.py`

Instead of editing them, you write `apps/backend/observability/INTEGRATION.md` — a document
listing the exact edits, with copy-paste-ready snippets, that Shreyas applies during
integration. Section 9 gives you the template and the four required entries.

This is deliberate. Those four files are the ones all three workstreams would otherwise
collide in. Moving every edit to a single integrator eliminates the collision entirely.

---

## 3. Working rules

These are binding. They exist so that combining three parallel branches produces close to
zero conflicts.

### R1 — File ownership is absolute

You may create and edit only:

- `apps/backend/observability/**`
- `tests/test_observability_*.py`

Nothing else. If you believe you need to touch something outside this list, **stop and ask
Shreyas** rather than doing it.

For reference, the other owners:

| Owner | Owns |
|---|---|
| A (you) | `apps/backend/observability/**`, `tests/test_observability_*.py` |
| B (Shreyas) | `apps/backend/logstore/**`, `apps/backend/routes/telemetry_routes.py`, `scripts/seed_fake_logs.py`, `tests/test_logstore_*.py`, `tests/test_telemetry_*.py` |
| C (Danny) | `apps/logsite/**`, `.github/workflows/uptime-probe.yml`, `tests/test_logsite_*.py` |
| Integrator only | `app.py`, `gemini_client.py`, `orchestrator.py`, `scan_routes.py`, `apps/frontend/**`, `render.yaml`, `requirements.txt`, `docs/**`, `knowledge/**`, `CLAUDE.md`, `graphify-out/**` |

### R2 — No workstream edits any existing file

Covered above. Everything you would want to change in an existing file goes into your
`INTEGRATION.md` as an instruction instead.

### R3 — Never edit `requirements.txt` or any `package.json`

List new dependencies in `INTEGRATION.md` with justification. **The target is zero new
dependencies.** Everything in your workstream is achievable with the Python standard library
(`logging`, `queue`, `threading`, `contextvars`, `uuid`, `hashlib`, `datetime`, `json`, `re`)
plus the already-installed `flask`. Do not add a logging framework.

### R4 — The event schema is frozen

Section 4 defines it. The identical schema block appears in Danny's handoff document. Changing
a field name or type silently breaks the other two workstreams, which are coded against it
blind. **Any change requires Shreyas's sign-off first.**

### R5 — Imports are a one-way DAG

`observability` imports **nothing** from `logstore` or `logsite`. Ever. B imports from you; you
never import from B. This prevents circular-import failures that only surface at merge time.

Within the main app, you may import from `flask` and from the standard library. Prefer not to
import other `apps.backend.*` modules at all.

### R6 — Everything is off by default

All new behaviour gates behind the environment variable `SENTINELSCAN_TELEMETRY_ENABLED`,
default `"0"`. When it is off:

- `emit_event()` returns immediately without doing anything
- the Flask hooks do nothing
- the logging bridge is not installed

This is what makes sequential merging safe: a merged-but-disabled workstream cannot break
production or the test suite.

### R7 — Tests are additive and isolated

Never modify an existing test file. New tests go in new files named
`tests/test_observability_*.py`. With your branch checked out, `pytest tests/` must still
report **at least 144 passed, 1 skipped**.

### R8 — Work on your branch however you like; no pull request is required of you

Branch: `workstream-a-recorder`. Commit and push to it as often as you want, in whatever style
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

Module paths, function names, environment variable names and header names are specified
exactly in this document. Match them character-for-character. B is writing code that calls
your functions without being able to see them.

### R12 — No secrets

Never commit a real key, token, or `secrets/`-shaped file, and never paste one into a
document or a test fixture. Gitleaks runs in CI (`.github/workflows/secret-scanning.yml`) and
will fail the build. Use obviously-fake values like `"test-token-not-real"` in tests.

### R13 — Integration is Shreyas's job, in order A → B → C

You do not merge anything. When your branch is ready, tell him. He merges A, then B, then C
into an integration branch, applies each `INTEGRATION.md`, runs the full suite, and opens one
PR into `main`.

---

## 4. The frozen event schema

Every event, from every source, in every workstream, is exactly this shape:

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
- `ts` is timezone-aware UTC: `datetime.now(timezone.utc).isoformat()`.
- `data` is a flat-ish dict, already redacted, JSON-serializable, and **must not exceed
  roughly 8 KB serialized**. Truncate long strings to 2000 characters with a `…[truncated]`
  suffix.
- `uid` is only ever set server-side from a verified Firebase token. Never trust a client's
  claim about who it is.

### 4.1 Worked example per category

**`http`** — emitted by your Flask `after_request` hook:
```json
{
  "event_id": "3f2a...", "ts": "2026-08-21T14:22:03.481203+00:00",
  "level": "info", "source": "backend", "category": "http",
  "message": "POST /api/v1/scans -> 202",
  "trace_id": "9c1e...", "session_id": "77bd...", "uid": "aZ3...", "scan_id": null,
  "duration_ms": 181,
  "data": {
    "method": "POST", "path": "/api/v1/scans", "route": "/api/v1/scans",
    "status": 202, "ip_hash": "b41c9e77a2d0f318", "ua": "Mozilla/5.0 ...",
    "query_keys": [], "content_length": 34
  },
  "release": "4e3db94", "env": "prod"
}
```

**`llm`** — emitted by your Gemini meter. This is what produces the token-usage screen:
```json
{
  "level": "info", "source": "agent", "category": "llm",
  "message": "gemini-flash-lite-latest: 1204 prompt + 88 response tokens",
  "duration_ms": 940, "scan_id": "b7e2...",
  "data": {
    "model": "gemini-flash-lite-latest",
    "prompt_tokens": 1204, "response_tokens": 88, "total_tokens": 1292,
    "cached": false, "retries": 0, "error": null
  }
}
```

**`agent`** — emitted from the orchestrator's progress callback:
```json
{
  "level": "info", "source": "agent", "category": "agent",
  "message": "AI selected ssl_check",
  "scan_id": "b7e2...",
  "data": {
    "tool_name": "ssl_check", "phase": "selected", "iteration": 4,
    "reasoning": "TLS posture is the natural next check after DNS resolved.",
    "action": "ssl_check(target=acme.com, port=443)"
  }
}
```

**`worker`** — arrives automatically via your logging bridge, from existing worker code:
```json
{
  "level": "warn", "source": "worker", "category": "worker",
  "message": "SSL handshake timed out after 10s",
  "scan_id": "b7e2...", "duration_ms": 10021,
  "data": { "logger": "apps.backend.workers.ssl_worker", "func": "check_ssl", "line": 142 }
}
```

**`error`** — emitted by your exception capture:
```json
{
  "level": "error", "source": "backend", "category": "error",
  "message": "TypeError: unsupported operand type(s) for +: 'NoneType' and 'int'",
  "trace_id": "9c1e...", "session_id": "77bd...",
  "data": {
    "type": "TypeError",
    "stack": "Traceback (most recent call last): ...",
    "fingerprint": "a71c3f90",
    "route": "/api/v1/scans"
  }
}
```

`fingerprint` is a short stable hash of the exception type plus the last in-project frame's
`file:function`. It lets the log site group repeats of the same bug. Compute it as the first
8 hex characters of a SHA-256 over that pair.

---

## 5. File-by-file specification

Create `apps/backend/observability/` with these modules. Follow the project's existing
conventions: PEP8, type hints on function signatures, concise docstrings on every module,
class and function.

### 5.1 `__init__.py`

The package's public face. Re-exports, plus the single entry point Shreyas will call.

```python
from apps.backend.observability.emit import (
    emit_event, emit, get_queue, get_stats, is_enabled,
)
from apps.backend.observability.context import (
    set_context, get_context, clear_context, snapshot, restore, bound, new_trace_id,
)

def init_app(app: "Flask") -> None:
    """Installs request hooks and the logging bridge. No-op when disabled."""

def wrap_progress_callback(callback):
    """Wraps the orchestrator's on_progress callback so agent stages are recorded.
    Returns callback unchanged when telemetry is disabled."""
```

`wrap_progress_callback` matters: it lets the orchestrator be instrumented with a **single
line**, instead of edits scattered across its many progress call sites. See section 9.3.

### 5.2 `events.py`

Builds and validates events. No I/O.

```python
SCHEMA_VERSION: int = 1
LEVELS: tuple[str, ...] = ("debug", "info", "warn", "error", "fatal")
SOURCES: tuple[str, ...] = ("frontend", "backend", "agent", "worker")
CATEGORIES: tuple[str, ...] = (
    "http", "auth", "scan", "agent", "worker", "llm", "ui", "error", "health",
)
MAX_DATA_BYTES: int = 8192
MAX_STRING_CHARS: int = 2000

def build_event(*, level: str, source: str, category: str, message: str,
                data: dict | None = None, duration_ms: int = 0,
                trace_id: str | None = None, session_id: str | None = None,
                uid: str | None = None, scan_id: str | None = None) -> dict:
    """Builds a schema-conformant event.

    Any of trace_id/session_id/uid/scan_id left as None are filled from the
    current context (see context.py). Generates event_id and ts. Reads release
    and env from the environment. Runs data through redaction and truncation.
    """

def validate_event(event: dict) -> tuple[bool, str]:
    """Returns (True, "") or (False, reason). Used by tests and by Workstream B."""

def fingerprint(exc_type: str, frame_id: str) -> str:
    """First 8 hex characters of sha256 over the exception type and frame id."""
```

Environment reads: `SENTINELSCAN_RELEASE` (default `"dev"`), `SENTINELSCAN_ENV` (default
`"dev"`).

### 5.3 `context.py`

Carries "who is this and what action is this" alongside execution, so every event is
automatically attributed without every call site passing it.

```python
_trace_id: ContextVar[str | None]
_session_id: ContextVar[str | None]
_uid: ContextVar[str | None]
_scan_id: ContextVar[str | None]

TRACE_HEADER: str = "X-SentinelScan-Trace"
SESSION_HEADER: str = "X-SentinelScan-Session"

def new_trace_id() -> str: ...
def set_context(*, trace_id=None, session_id=None, uid=None, scan_id=None) -> None: ...
def get_context() -> dict: ...
def clear_context() -> None: ...
def snapshot() -> dict:
    """Captures the current context as a plain dict, for handing to a new thread."""
def restore(snap: dict) -> None:
    """Re-binds a snapshot inside a new thread. See section 6.2 — this is essential."""

@contextmanager
def bound(**kwargs):
    """Temporarily sets context, restoring the previous values on exit."""
```

The two header names are part of the frozen contract — the browser-side telemetry client
(built by Workstream B) sends exactly these, and Workstream C displays what they correlate.

### 5.4 `redaction.py`

Central, tested, and the only place privacy rules live. No call site should ever have to
remember to redact.

```python
REDACTED: str = "[REDACTED]"

SENSITIVE_HEADERS: frozenset[str] = frozenset({
    "authorization", "cookie", "set-cookie", "x-api-key", "proxy-authorization",
})
SENSITIVE_KEYS: frozenset[str] = frozenset({
    "password", "passwd", "token", "id_token", "access_token", "refresh_token",
    "api_key", "apikey", "secret", "authorization", "credential", "private_key",
    "gemini_api_key", "flask_secret_key", "session", "cookie",
})

def redact_mapping(mapping: "Mapping[str, Any]", depth: int = 0) -> dict: ...
def redact_headers(headers: "Mapping[str, str]") -> dict: ...
def query_keys(query_string: str) -> list[str]:
    """Returns parameter NAMES only. Values are never recorded."""
def hash_ip(ip: str | None) -> str | None:
    """Salted SHA-256, first 16 hex characters. Never store a raw IP."""
def scrub_text(text: str) -> str:
    """Removes secret-shaped substrings from free text (messages, stack traces)."""
def redact_data(data: dict) -> dict:
    """Recursive redaction plus truncation. Depth-limited to 6."""
```

`scrub_text` must catch, at minimum:

| Pattern | Regex |
|---|---|
| JWT / Firebase ID token | `eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+` |
| Google API key | `AIza[0-9A-Za-z_\-]{35}` |
| Bearer header value | `(?i)bearer\s+[A-Za-z0-9._\-]+` |
| Long opaque blobs | any unbroken `[A-Za-z0-9+/=_-]{40,}` |

IP salt: read `TELEMETRY_IP_SALT`; fall back to `FLASK_SECRET_KEY`; fall back to a constant
development salt. Never log the salt.

### 5.5 `emit.py`

The hand-off point to Workstream B. **The most safety-critical module you write.**

```python
DEFAULT_QUEUE_SIZE: int = 10_000

def is_enabled() -> bool:
    """True when SENTINELSCAN_TELEMETRY_ENABLED is one of 1/true/yes/on."""

def get_queue() -> "queue.Queue[dict]":
    """The bounded queue Workstream B's sink thread drains. Created lazily."""

def emit_event(event: dict) -> None:
    """Enqueues one event. Never blocks. Never raises. Never retries."""

def emit(*, level: str, source: str, category: str, message: str, **kwargs) -> None:
    """Convenience: build_event(...) then emit_event(...)."""

def get_stats() -> dict:
    """{'emitted': int, 'dropped': int, 'queued': int, 'errors': int}"""

def drain_for_test(max_items: int = 1000) -> list[dict]:
    """Test helper. Empties the queue and returns its contents."""
```

Required behaviour of `emit_event`, in order:

1. If not enabled, return immediately.
2. Wrap the entire body in `try` / `except Exception`. On any exception, increment an internal
   error counter and **return normally**. It must be impossible for this function to raise.
3. Use `queue.put_nowait()`. Never `put()`, never a timeout, never a lock held across I/O.
4. On `queue.Full`, increment the dropped counter and return. **Dropping is correct
   behaviour.** Losing telemetry is always preferable to slowing down a user's request.
5. If `SENTINELSCAN_TELEMETRY_STDOUT` is truthy, also print the event as one line of JSON —
   this is the standalone mode described in section 10.

### 5.6 `flask_hooks.py`

```python
def init_app(app: "Flask") -> None:
    """Registers before_request, after_request, teardown_request, and an
    exception listener. No-op when telemetry is disabled."""
```

**before_request**
- Read `X-SentinelScan-Trace` and `X-SentinelScan-Session` from the request. Generate a fresh
  trace id if absent. Validate both look like UUIDs; ignore junk rather than storing it.
- Resolve `uid`: only from a verified Firebase token, never from a client-supplied field. If
  `Authorization: Bearer ...` is present you may reuse the same verification approach as
  `apps/backend/auth/auth_utils.py`. If verification fails or is unavailable, `uid` is `None`
  — **never** fall back to a client-provided value.
- Call `set_context(...)`, and stash a monotonic start time on `flask.g`.

**after_request**
- Build and emit one `http` event: method, raw path, matched route pattern
  (`request.url_rule.rule` — prefer this, since raw paths contain scan ids), status,
  `duration_ms`, hashed IP, user agent, query parameter **names only**, content length.
- Echo the trace id back as a response header so the browser can correlate.
- Skip static assets (`/static/...`) and `/health` by default — pure noise, and `/health` is
  polled every 5 minutes by an uptime probe. Make the skip list a module constant.
- Return the response object unchanged, always.

**teardown_request** — call `clear_context()`.

**Exception capture** — use Flask's `got_request_exception` signal:

```python
from flask import got_request_exception
got_request_exception.connect(_on_exception, app)
```

Do **not** use `app.register_error_handler(Exception, ...)`. An error handler changes what the
application returns to the user; a signal listener observes without interfering. Your job is
to record, never to alter behaviour.

In the listener, emit an `error` event with the exception type, the scrubbed traceback, the
computed `fingerprint`, and the matched route.

### 5.7 `logging_bridge.py`

This is the highest-leverage module in your workstream. Thirteen existing modules already
call `logger.error(...)`, `logger.warning(...)` and so on, and currently write to nowhere.
One handler makes all of them work — **and you never touch those thirteen files.**

It is also what keeps the project's "dumb workers" principle intact: workers gain zero new
code, because their existing `logging` calls are simply adopted.

```python
class TelemetryHandler(logging.Handler):
    """Routes standard-library log records into the telemetry pipeline."""
    def emit(self, record: logging.LogRecord) -> None: ...

def install(level: int = logging.INFO) -> None: ...
def uninstall() -> None: ...
```

Mapping rules:

| Logger name starts with | `source` | `category` |
|---|---|---|
| `apps.backend.workers.` | `worker` | `worker` |
| `apps.backend.agent.` | `agent` | `agent` |
| anything else | `backend` | `error` if `record.exc_info` else `scan` |

Level mapping: `DEBUG` to `debug`, `INFO` to `info`, `WARNING` to `warn`, `ERROR` to `error`,
`CRITICAL` to `fatal`.

`data` carries `{"logger": record.name, "func": record.funcName, "line": record.lineno}`, plus
a scrubbed `stack` when `exc_info` is present.

**Two failure modes you must guard against:**

1. **Infinite recursion.** If a log record originates from `apps.backend.observability` or
   `apps.backend.logstore`, drop it immediately. Otherwise a log statement inside the sink
   produces an event, which produces a log statement, forever.
2. **Handler exceptions.** `logging.Handler.emit` must never raise. Wrap the body in
   `try` / `except Exception: self.handleError(record)`.

Install the handler on the `apps` logger, not the root logger, so third-party library chatter
(`werkzeug`, `urllib3`, `google`) is not swept in.

### 5.8 `gemini_meter.py`

Produces the token-usage data for requirement 5.

```python
def usage_from_response(response: "Any") -> dict:
    """Extracts {'prompt_tokens', 'response_tokens', 'total_tokens'} from a
    google.genai GenerateContentResponse. Returns zeros if unavailable."""

def record_llm_call(*, model: str, usage: dict, duration_ms: int,
                    cached: bool = False, retries: int = 0,
                    error: str | None = None) -> None:
    """Emits one `llm` event."""
```

The SDK exposes usage at `response.usage_metadata` with attributes
`prompt_token_count`, `candidates_token_count` and `total_token_count`. **Read every one
defensively with `getattr(..., None)`** — the field is absent on some responses and on every
cached response, and an `AttributeError` here would break a live scan. Return zeros rather
than raising.

Also record cache hits (`cached=True`, zero tokens). The log site shows cache hit-rate, and a
cache hit that emits nothing would make the rate wrong.

### 5.9 `stdout_sink.py`

See section 10. A small module letting you run and demo with no Workstream B in existence.

---

## 6. The two hard problems

Everything above is routine. These two are not, and both fail *silently* if missed.

### 6.1 `emit_event()` must be incapable of slowing the site down

The whole project rests on this. The log site is a window into the main app; the moment
recording adds latency to a user's request, the feature has made the product worse.

Firestore is a network service. It can be slow, rate-limited, or completely down. If
`emit_event()` ever waits on it — even indirectly, even once — a user's scan request waits too.

The defence is architectural, not careful coding:

- `emit_event()` only ever appends to an **in-process, bounded** `queue.Queue`.
- It uses `put_nowait()`, so it cannot block even when the queue is full.
- When the queue is full it **throws the event away** and increments a counter.
- It never raises, so a caller can never be interrupted by a telemetry failure.
- All network I/O happens on Workstream B's background thread, which you never touch.

You must write `tests/test_observability_emit.py::test_emit_never_blocks_or_raises` proving
this: fill the queue past capacity, then assert `emit_event()` still returns promptly and
without raising, and that the dropped counter increased.

### 6.2 Context does not cross thread boundaries

This one is subtle and it silently destroys the single most valuable feature of the whole
project.

Scans do not run inside the request. `apps/backend/routes/scan_routes.py` line 81 defines
`_run_scan_background`, and `start_scan` launches it on a fresh `threading.Thread` so the
POST can return `202` immediately.

**Python `contextvars` do not automatically propagate into a thread started with
`threading.Thread`.** A fresh thread begins with an empty context.

So without a fix, the sequence is:

1. User clicks "Start Scan"; the browser sends `trace_id` = `9c1e...`
2. Flask records the HTTP event with `trace_id` = `9c1e...` — correct
3. The background thread starts; its context is empty
4. Every Gemini decision, all ten workers, the CVSS stage and the report get
   `trace_id = None` — broken

Requirement 4 — "show the internal work behind a button click" — is implemented by grouping
events that share a `trace_id`. With the ids lost, the log site shows the click and nothing
underneath it. Nothing errors. No test fails. The feature is simply empty.

The fix is small; knowing it is needed is the hard part. Provide `snapshot()` and `restore()`
in `context.py`, then specify in your `INTEGRATION.md` that the thread's creator captures a
snapshot and the thread's body restores it (section 9.4).

Prove it with `tests/test_observability_context.py::test_context_survives_thread_handoff`:
set a context, call `snapshot()`, start a real `threading.Thread`, call `restore()` inside it,
and assert an event emitted from that thread carries the original `trace_id`.

---

## 7. Privacy and redaction rules

This project records what real users do, so recording carelessly creates a privacy problem
where none existed. These rules are requirements, not suggestions, and they are centralised in
`redaction.py` with tests so no individual call site has to remember them.

**Never record:**

- The **value** typed into any input, textarea, or form field. Capture the element's `id`,
  `name` or visible label only. (This constrains Workstream B's browser client too; you
  enforce the server-side half.)
- `Authorization` headers, `Cookie` / `Set-Cookie` headers, Firebase ID tokens, session
  cookies.
- Anything read from `secrets/`, `GEMINI_API_KEY`, or `FLASK_SECRET_KEY`.
- Raw IP addresses. Store `hash_ip(ip)` instead.
- Full query strings. Store parameter **names** only.
- Full request or response bodies.

**Always:**

- Run every free-text field — messages and stack traces included — through `scrub_text()`.
  Stack traces are the sneakiest leak: a `repr()` of a config object in a traceback frame can
  contain an API key.
- Truncate strings at 2000 characters and cap serialized `data` at 8 KB.

There is a privacy section on the live site's documentation page. Updating that text is
Shreyas's job at integration; note it in your `INTEGRATION.md` so it is not forgotten.

---

## 8. Configuration

All environment variables you introduce, with defaults. Document these in `INTEGRATION.md`
too, since Shreyas must set them in Render.

| Variable | Default | Purpose |
|---|---|---|
| `SENTINELSCAN_TELEMETRY_ENABLED` | `"0"` | Master switch. Off means every hook is a no-op. |
| `SENTINELSCAN_TELEMETRY_STDOUT` | `"0"` | Also print each event as JSON — standalone mode. |
| `SENTINELSCAN_TELEMETRY_QUEUE_SIZE` | `"10000"` | Bounded queue capacity. |
| `SENTINELSCAN_RELEASE` | `"dev"` | Git SHA, stamped on every event. |
| `SENTINELSCAN_ENV` | `"dev"` | `prod` or `dev`. |
| `TELEMETRY_IP_SALT` | falls back to `FLASK_SECRET_KEY` | Salt for IP hashing. |

Read them through a small helper so tests can monkeypatch cleanly. Do not read `os.environ`
at import time for the master switch — read it per call, or tests cannot toggle it.

---

## 9. `INTEGRATION.md` — the document you must write

Create `apps/backend/observability/INTEGRATION.md`. This is a **required deliverable**, not
optional. It is how your code actually gets connected, since you never edit an existing file.

Write it for Shreyas: precise, copy-paste-ready, with enough context that he does not have to
reverse-engineer your intent.

### Required structure

```markdown
# Workstream A — Integration Instructions

## Summary
One paragraph: what this package does and what enabling it changes.

## New dependencies
(Expected: none. If any, name it and justify it.)

## Environment variables
The table from section 8, plus which must be set in Render.

## Edits required
### Edit 1 — apps/backend/app.py
### Edit 2 — apps/backend/agent/gemini_client.py
### Edit 3 — apps/backend/agent/orchestrator.py
### Edit 4 — apps/backend/routes/scan_routes.py

Each with: the anchor (existing code to find), the replacement, and one line on why.

## Verification after integration
Concrete steps proving the wiring works.

## Rollback
How to disable everything instantly.
```

### 9.1 Edit 1 — `apps/backend/app.py`

`create_app()` currently calls `limiter.init_app(app)` around line 30. Your instruction: add
the import near the other `apps.backend` imports, and call `init_app(app)` immediately after
the limiter, before the blueprints register.

### 9.2 Edit 2 — `apps/backend/agent/gemini_client.py`

In `GeminiClient.generate()`, the live API call is
`raw_response = self._call_with_backoff(history)` (around line 284). Your instruction: time
that call, then record usage. Also record a cache hit in the branch above it, where
`cached is not None` returns early.

Every added line must be wrapped so a telemetry failure cannot break a scan.

### 9.3 Edit 3 — `apps/backend/agent/orchestrator.py`

`run_scan(target, max_iterations=..., on_progress=None)` already receives a progress callback
and already invokes it at every stage with `tool_name`, `phase`, `reasoning`, `action`,
`summary`, `status` and `duration`. That is exactly the agent-stage data the log site needs —
**do not add a second callback mechanism.**

Your instruction should be a single line at the top of `run_scan`:

```python
on_progress = wrap_progress_callback(on_progress)
```

Your `wrap_progress_callback` returns a function that emits an `agent` event and then calls
the original callback (if any) with the identical arguments. It must tolerate `on_progress`
being `None`, must never raise into the orchestrator, and must return the original callback
unchanged when telemetry is disabled.

### 9.4 Edit 4 — `apps/backend/routes/scan_routes.py`

The fix for section 6.2. Two changes in one file:

- In `start_scan`, before `threading.Thread(...)` (around line 236): capture
  `ctx = snapshot()` and pass it into the thread's args.
- In `_run_scan_background` (line 81): accept the new parameter and call `restore(ctx)` plus
  `set_context(scan_id=scan_id)` as the very first statements.

Give the exact signature change, and note that the parameter must default to `None` so any
other caller and the existing tests keep working.

---

## 10. Working alone

You do not need Workstream B or C to exist. Set:

```
SENTINELSCAN_TELEMETRY_ENABLED=1
SENTINELSCAN_TELEMETRY_STDOUT=1
```

and every event prints to the terminal as one JSON line. Nothing drains the queue in this
mode, so also have `stdout_sink.py` offer an opt-in draining thread — or simply let the
bounded queue fill and drop, which is realistic and proves your drop path works.

Running the app locally — the project's standing instructions:

```bash
cd apps/frontend/react-app && npm run build && cd ../../..
python -m apps.backend.app
```

**Always use `http://localhost:5000`.** Firebase's authorized-domain list covers `localhost`
and the Render domain only; any other host breaks Google sign-in.

If a fresh clone is missing `flask_limiter` or `playwright`, run
`pip install -r requirements.txt`.

Your demo for Shreyas: start the app with the two variables set, click through the site, run a
scan, and show a terminal full of correctly-attributed events — with every scan-stage event
carrying the same `trace_id` as the click that started it.

---

## 11. Tests

New files only, named `tests/test_observability_*.py`. The suite currently reports **144
passed, 1 skipped**; it must still do so with your branch checked out.

Required coverage:

| File | Must prove |
|---|---|
| `test_observability_emit.py` | `emit_event` never blocks and never raises, even with a full queue; drops are counted; disabled means no-op |
| `test_observability_context.py` | **Context survives a real thread handoff** (section 6.2); `bound()` restores prior values; `clear_context()` works |
| `test_observability_redaction.py` | Every rule in section 7: headers, sensitive keys, nested dicts, JWTs and API keys in free text, IP hashing is stable and irreversible, truncation |
| `test_observability_events.py` | Schema conformance; every key always present; `ts` is tz-aware UTC; `validate_event` rejects bad levels/sources/categories; fingerprints are stable |
| `test_observability_logging_bridge.py` | Existing `logger.*` calls become events with correct source/category; records from `observability`/`logstore` are dropped (no recursion); a raising handler cannot propagate |
| `test_observability_resilience.py` | **A simulated total Firestore outage neither slows nor fails a request.** Simulate by making the queue consumer raise, or by filling the queue, then assert request handling is unaffected |

Use `pytest` with `monkeypatch` for environment variables. Follow the style of the existing
tests in `tests/` — read two or three first. Never use a real credential in a fixture (R12).

---

## 12. Definition of done

Tick every box before telling Shreyas the branch is ready.

- [ ] `apps/backend/observability/` contains all nine modules from section 5
- [ ] Zero existing files modified — verify with `git diff --name-only main...HEAD`
- [ ] `requirements.txt` untouched; ideally no new dependency at all
- [ ] `apps/backend/observability/INTEGRATION.md` written, with all four edits specified precisely enough to apply without asking you a question
- [ ] `pytest tests/` reports at least 144 passed, 1 skipped
- [ ] All six test files from section 11 exist and pass
- [ ] The thread-handoff test genuinely starts a real thread
- [ ] With `SENTINELSCAN_TELEMETRY_ENABLED=0`, the app behaves identically to `main`
- [ ] With telemetry and stdout on, a full local scan produces correctly-attributed events, and every scan-stage event shares the originating click's `trace_id`
- [ ] No secret-shaped string anywhere in the diff (R12)
- [ ] Nothing under `knowledge/`, `graphify-out/`, `docs/`, or another workstream's paths is in your diff
- [ ] Every public function has a type-hinted signature and a docstring
- [ ] No commit carries a `Co-Authored-By:` trailer

---

## 13. Git workflow

```bash
git checkout main
git pull
git checkout -b workstream-a-recorder

# ... work, committing as often as you like ...
git add apps/backend/observability tests/test_observability_*.py
git commit -m "feat(observability): add non-blocking event emit pipeline"

git push -u origin workstream-a-recorder
```

Commit style: conventional prefixes (`feat(...)`, `fix(...)`, `test(...)`, `docs(...)`), small
and atomic. **No `Co-Authored-By:` trailer, ever.**

Stage your own paths explicitly rather than using `git add -A`, so nothing from `knowledge/`
or `graphify-out/` is swept in accidentally.

When the checklist in section 12 is complete, tell Shreyas. Do not merge anything yourself.

---

## 14. Questions

Anything not answered here — especially anything that would require changing the event schema
(R4), adding a dependency (R3), or touching a file outside your ownership (R1) — goes to
Shreyas before you act on it. A guess that diverges from the frozen contract costs all three
workstreams a rewrite.
