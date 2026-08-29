import uuid
from contextvars import ContextVar
from contextlib import contextmanager

_trace_id: ContextVar[str | None] = ContextVar("_trace_id", default=None)
_session_id: ContextVar[str | None] = ContextVar("_session_id", default=None)
_uid: ContextVar[str | None] = ContextVar("_uid", default=None)
_scan_id: ContextVar[str | None] = ContextVar("_scan_id", default=None)

TRACE_HEADER: str = "X-SentinelScan-Trace"
SESSION_HEADER: str = "X-SentinelScan-Session"

def new_trace_id() -> str:
    """Generate a new UUIDv4 trace ID."""
    return str(uuid.uuid4())

def set_context(*, trace_id: str | None = None, session_id: str | None = None,
                uid: str | None = None, scan_id: str | None = None) -> None:
    """Set the current context values if provided."""
    if trace_id is not None:
        _trace_id.set(trace_id)
    if session_id is not None:
        _session_id.set(session_id)
    if uid is not None:
        _uid.set(uid)
    if scan_id is not None:
        _scan_id.set(scan_id)

def get_context() -> dict:
    """Get the current context values as a dictionary."""
    return {
        "trace_id": _trace_id.get(),
        "session_id": _session_id.get(),
        "uid": _uid.get(),
        "scan_id": _scan_id.get(),
    }

def clear_context() -> None:
    """Clear all context variables."""
    _trace_id.set(None)
    _session_id.set(None)
    _uid.set(None)
    _scan_id.set(None)

def snapshot() -> dict:
    """Captures the current context as a plain dict, for handing to a new thread."""
    return get_context()

def restore(snap: dict) -> None:
    """Re-binds a snapshot inside a new thread."""
    set_context(
        trace_id=snap.get("trace_id"),
        session_id=snap.get("session_id"),
        uid=snap.get("uid"),
        scan_id=snap.get("scan_id"),
    )

@contextmanager
def bound(**kwargs):
    """Temporarily sets context, restoring the previous values on exit."""
    prev = get_context()
    set_context(**kwargs)
    try:
        yield
    finally:
        restore(prev)
