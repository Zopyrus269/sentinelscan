# Workstream A — Integration Instructions

## Summary
The `apps.backend.observability` package introduces a non-blocking recording layer for the application. It automatically captures HTTP requests, unhandled errors, Gemini token usage, background worker logs, and orchestrator decisions into a bounded, in-memory queue. This system is completely disabled by default and ensures zero performance impact on the main application.

## New dependencies
None. The implementation strictly uses the Python standard library (`logging`, `queue`, `threading`, `contextvars`, `uuid`, `hashlib`, `datetime`, `json`, `re`) and `flask`.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `SENTINELSCAN_TELEMETRY_ENABLED` | `"0"` | Master switch. Off means every hook is a no-op. (Must be set to `1` in Render to enable) |
| `SENTINELSCAN_TELEMETRY_STDOUT` | `"0"` | Also print each event as JSON — standalone mode. |
| `SENTINELSCAN_TELEMETRY_QUEUE_SIZE` | `"10000"` | Bounded queue capacity. |
| `SENTINELSCAN_RELEASE` | `"dev"` | Git SHA, stamped on every event. |
| `SENTINELSCAN_ENV` | `"dev"` | `prod` or `dev`. |
| `TELEMETRY_IP_SALT` | falls back to `FLASK_SECRET_KEY` | Salt for IP hashing. (Set in Render) |

## Edits required

### Edit 1 — apps/backend/app.py
**Anchor:** Around line 30, inside `create_app()`, immediately after `limiter.init_app(app)`.
**Replacement:** Add the import and call `init_app(app)`.
```python
    limiter.init_app(app)
    
    from apps.backend.observability import init_app as init_observability
    init_observability(app)
```
**Why:** Installs request hooks (for HTTP/error events) and the logging bridge (for worker events).

### Edit 2 — apps/backend/agent/gemini_client.py
**Anchor:** In `GeminiClient.generate()`, replace the raw API call and the cache return block (around line 284).
**Replacement:** 
```python
        import time
        from apps.backend.observability.gemini_meter import usage_from_response, record_llm_call
        
        if cached is not None:
            try:
                record_llm_call(model=self.model_name, usage={}, duration_ms=0, cached=True)
            except Exception:
                pass
            return cached

        start_time = time.monotonic()
        try:
            raw_response = self._call_with_backoff(history)
            duration_ms = int((time.monotonic() - start_time) * 1000)
            try:
                usage = usage_from_response(raw_response)
                record_llm_call(model=self.model_name, usage=usage, duration_ms=duration_ms)
            except Exception:
                pass
        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            try:
                record_llm_call(model=self.model_name, usage={}, duration_ms=duration_ms, error=str(e))
            except Exception:
                pass
            raise
```
**Why:** Times the Gemini call and emits an `llm` event with token usage (or cache hit), wrapped defensively.

### Edit 3 — apps/backend/agent/orchestrator.py
**Anchor:** The top of the `run_scan(target, max_iterations=..., on_progress=None)` function.
**Replacement:**
```python
def run_scan(target, max_iterations=..., on_progress=None):
    from apps.backend.observability import wrap_progress_callback
    on_progress = wrap_progress_callback(on_progress)
```
**Why:** Automatically emits `agent` events for every step in the orchestrator.

### Edit 4 — apps/backend/routes/scan_routes.py
**Anchor 1:** In `start_scan`, before `threading.Thread(...)` (around line 236).
**Replacement 1:**
```python
    from apps.backend.observability import snapshot
    ctx = snapshot()
    thread = threading.Thread(target=_run_scan_background, args=(scan_id, target, user_id, ctx))
```
**Anchor 2:** In `_run_scan_background` (line 81).
**Replacement 2:**
```python
def _run_scan_background(scan_id, target, user_id=None, telemetry_ctx=None):
    from apps.backend.observability import restore, set_context
    if telemetry_ctx:
        restore(telemetry_ctx)
    set_context(scan_id=scan_id)
```
**Why:** `contextvars` do not cross thread boundaries natively. This snapshot/restore ensures `trace_id` carries over into the background scan.

## Verification after integration
1. Start the app locally with `SENTINELSCAN_TELEMETRY_ENABLED=1` and `SENTINELSCAN_TELEMETRY_STDOUT=1`.
2. Click through the site and start a scan.
3. Observe the terminal: you should see JSON events for `http`, `agent`, `worker`, and `llm` categories.
4. Verify that the `trace_id` of the initial `http` POST request matches the `trace_id` on the subsequent `agent` and `worker` events.

## Rollback
Set `SENTINELSCAN_TELEMETRY_ENABLED=0` in the environment. All observability hooks become immediate no-ops.

*(Note for integrator: Please remember to update the privacy section on the live site's documentation page to reflect what is being recorded and scrubbed.)*
