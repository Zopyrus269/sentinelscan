---
type: code-review
date: 2026-08-29
session: 26
branch: workstream-c-
reviewed_by: claude-code
status: resolved-2026-08-29-pr-18-merged
---

# Workstream C — Phase 1 branch cleanup (`apps/logsite/`)

Part of the three-way branch integration effort (Phase 1: clean up each of the three workstream
branches independently before combining them). Done **by hand** — no `/code-review` skill, no
subagents. See [[2026-08-29]] for why, and [[workstream-a-code-review-2026-08-29]] for the
companion review.

**Scope:** the complete diff against `main` — 24 files / 4,692 insertions. The worktree was
refreshed mid-session to `36b9579` after discovering Danny had pushed 3 more commits
(`4c5cd72`, `c610493`, `36b9579`) days earlier that a stale local fetch hadn't picked up.

## Findings

1. **`.github/workflows/uptime-probe.yml` produced invalid JSON on a real connection failure.**
   The workflow runs under bash's `set -e`. On a genuine connection failure, `curl -w
   "%{http_code}"` already prints `"000"` before exiting non-zero — but the existing `||
   echo "000"` sat *inside* the `$(...)` command substitution, so it concatenated onto that
   output instead of replacing it, producing `"000000"` (an invalid JSON number literal) in the
   payload posted to `/api/probe`. This is exactly the failure case the probe exists to catch —
   verified empirically (`curl ... --max-time 2 "http://127.0.0.1:1/health"`) before and after
   the fix. Fix: move the fallback outside the substitution (`HTTP_STATUS=$(curl ...) ||
   HTTP_STATUS="000"`) so it replaces rather than appends.
2. **`live.js` and `sessions.js` accumulate duplicate event listeners** if
   `onLogsiteAuthStateChanged` fires more than once (it fires on every auth transition, not just
   the first). Both re-run their filter/search/copy `addEventListener` setup inside `init()`,
   which is re-invoked on every auth change. A developer who signs out and back in within one
   page load would get duplicate listeners and redundant network calls thereafter. Fix: gate the
   one-time listener setup behind an `initialized` flag; the per-load data fetch still runs on
   every auth change as before. `health.js`, `llm.js`, and `status.js` don't have this issue —
   confirmed by cross-checking all five frontend pages' auth-callback wiring.

## What checked out clean (verified, not assumed)

- All 10 routes in `api.py` correctly stack `@require_auth` then `@require_developer` in that
  exact order (confirmed against `require_developer`'s own docstring requirement and Python's
  decorator execution order — outermost decorator runs first).
- `probe.py`'s token check uses `hmac.compare_digest` (constant-time), correctly rejects
  malformed/missing tokens before any payload parsing.
- The frontend's catch-all static-file route (`app.py`'s `serve_frontend_file`) looks exploitable
  for path traversal at a glance (a naive `os.path.exists` pre-check on a raw joined path), but
  isn't — `send_from_directory` uses Werkzeug's `safe_join` internally, which rejects `../`
  sequences. Verified directly: `werkzeug.utils.safe_join(...)` returns `None` for a traversal
  attempt rather than a path. Flagged and ruled out rather than reported as a false positive.
- The seeded-demo-data timestamp fix (workstream B's finding C3, which Workstream C's
  `seed_fake_logs.py` usage depends on) is correctly implemented on Workstream B's side —
  cross-checked, not re-fixed here since it isn't Workstream C's own code.

## Deliberately not touched

`api.py` and `probe.py` use an unusual one-argument-per-line formatting style throughout
(~1,200 lines). It's valid Python, doesn't affect behavior, and reformatting it would produce a
huge whitespace-dominated diff that would bury the two real fixes above. Flagged here for
awareness, not acted on unilaterally.

## Test results

`pytest tests/`: 161 passed, 1 skipped — unchanged before and after (both on the pre-refresh and
post-refresh worktree state, and again after the fix).

## Links

- PR: [#18](https://github.com/Zopyrus269/sentinelscan/pull/18) (`cabd841`), merged 2026-08-29
- Session log: [[2026-08-29]] (session 26)
