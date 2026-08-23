import time
import uuid
import traceback
from flask import request, g, got_request_exception, Response
from apps.backend.observability.emit import is_enabled, emit
from apps.backend.observability.context import set_context, clear_context, TRACE_HEADER, SESSION_HEADER, new_trace_id
from apps.backend.observability.events import fingerprint
from apps.backend.observability.redaction import hash_ip, query_keys

_SKIP_PATHS = ("/static/", "/health")

def init_app(app: "Flask") -> None:
    """Registers request hooks. No-op when telemetry is disabled."""
    if not is_enabled():
        return

    app.before_request(_before_request)
    app.after_request(_after_request)
    app.teardown_request(_teardown_request)
    got_request_exception.connect(_on_exception, app)

def _is_valid_uuid(val: str | None) -> bool:
    if not val:
        return False
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False

def _before_request():
    if request.path.startswith(_SKIP_PATHS) or request.path == "/health":
        return

    trace_id = request.headers.get(TRACE_HEADER)
    if not _is_valid_uuid(trace_id):
        trace_id = new_trace_id()
        
    session_id = request.headers.get(SESSION_HEADER)
    if not _is_valid_uuid(session_id):
        session_id = None
        
    uid = None
    # If auth_utils verification logic was needed here, we'd mock it or reuse it.
    # For now, it stays None unless verified.
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            from apps.backend.auth.auth_utils import verify_firebase_token
            token = auth_header.split(" ")[1]
            # Need to run this defensively without raising
            decoded = verify_firebase_token(token)
            if decoded and isinstance(decoded, dict):
                uid = decoded.get("uid")
        except Exception:
            pass

    set_context(trace_id=trace_id, session_id=session_id, uid=uid)
    g._observability_start_time = time.monotonic()

def _after_request(response: Response) -> Response:
    if request.path.startswith(_SKIP_PATHS) or request.path == "/health":
        return response

    start_time = getattr(g, "_observability_start_time", None)
    duration_ms = 0
    if start_time is not None:
        duration_ms = int((time.monotonic() - start_time) * 1000)

    route_pattern = request.url_rule.rule if request.url_rule else request.path

    emit(
        level="info" if response.status_code < 400 else ("warn" if response.status_code < 500 else "error"),
        source="backend",
        category="http",
        message=f"{request.method} {route_pattern} -> {response.status_code}",
        duration_ms=duration_ms,
        data={
            "method": request.method,
            "path": request.path,
            "route": route_pattern,
            "status": response.status_code,
            "ip_hash": hash_ip(request.remote_addr),
            "ua": request.headers.get("User-Agent"),
            "query_keys": query_keys(request.query_string.decode('utf-8') if request.query_string else ""),
            "content_length": response.content_length,
        }
    )

    from apps.backend.observability.context import get_context
    ctx = get_context()
    if ctx.get("trace_id"):
        response.headers[TRACE_HEADER] = ctx["trace_id"]

    return response

def _teardown_request(exc=None):
    clear_context()

def _on_exception(sender, exception, **extra):
    route_pattern = request.url_rule.rule if request.url_rule else request.path
    exc_type = type(exception).__name__
    
    tb = traceback.extract_tb(exception.__traceback__)
    # find last in-project frame
    frame_id = "unknown:0"
    for frame in reversed(tb):
        if "apps/backend" in frame.filename:
            frame_id = f"{frame.filename}:{frame.name}"
            break
            
    if frame_id == "unknown:0" and tb:
        frame_id = f"{tb[-1].filename}:{tb[-1].name}"
        
    fp = fingerprint(exc_type, frame_id)
    
    emit(
        level="error",
        source="backend",
        category="error",
        message=f"{exc_type}: {str(exception)}",
        data={
            "type": exc_type,
            "stack": "".join(traceback.format_exception(type(exception), exception, exception.__traceback__)),
            "fingerprint": fp,
            "route": route_pattern
        }
    )
