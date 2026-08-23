import os
import uuid
import json
import hashlib
from datetime import datetime, timezone
from apps.backend.observability.context import get_context, new_trace_id
from apps.backend.observability.redaction import redact_data, scrub_text

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
    """Builds a schema-conformant event."""
    ctx = get_context()
    
    _trace_id = trace_id if trace_id is not None else ctx.get("trace_id")
    _session_id = session_id if session_id is not None else ctx.get("session_id")
    _uid = uid if uid is not None else ctx.get("uid")
    _scan_id = scan_id if scan_id is not None else ctx.get("scan_id")
    
    # Redact and truncate data
    _data = redact_data(data) if data is not None else {}
    
    # Ensure data doesn't exceed MAX_DATA_BYTES
    try:
        if len(json.dumps(_data).encode('utf-8')) > MAX_DATA_BYTES:
            _data = {"_error": "Data exceeded MAX_DATA_BYTES and was dropped."}
    except Exception:
        _data = {"_error": "Data was not JSON serializable."}
        
    _message = message
    if isinstance(_message, str):
        _message = scrub_text(_message)
        if len(_message) > MAX_STRING_CHARS:
            _message = _message[:MAX_STRING_CHARS - 12] + "...[truncated]"
    else:
        _message = str(_message)
        
    return {
        "event_id": str(uuid.uuid4()),
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "source": source,
        "category": category,
        "message": _message,
        "trace_id": _trace_id,
        "session_id": _session_id,
        "uid": _uid,
        "scan_id": _scan_id,
        "duration_ms": duration_ms,
        "data": _data,
        "release": os.environ.get("SENTINELSCAN_RELEASE", "dev"),
        "env": os.environ.get("SENTINELSCAN_ENV", "dev")
    }

def validate_event(event: dict) -> tuple[bool, str]:
    """Returns (True, "") or (False, reason)."""
    required_keys = {
        "event_id", "ts", "level", "source", "category", "message",
        "trace_id", "session_id", "uid", "scan_id", "duration_ms",
        "data", "release", "env"
    }
    
    missing = required_keys - set(event.keys())
    if missing:
        return False, f"Missing keys: {', '.join(missing)}"
        
    if event["level"] not in LEVELS:
        return False, f"Invalid level: {event['level']}"
        
    if event["source"] not in SOURCES:
        return False, f"Invalid source: {event['source']}"
        
    if event["category"] not in CATEGORIES:
        return False, f"Invalid category: {event['category']}"
        
    return True, ""

def fingerprint(exc_type: str, frame_id: str) -> str:
    """First 8 hex characters of sha256 over the exception type and frame id."""
    data = f"{exc_type}:{frame_id}".encode('utf-8')
    return hashlib.sha256(data).hexdigest()[:8]
