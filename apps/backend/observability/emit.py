import os
import queue
import json
import threading
from apps.backend.observability.events import build_event

DEFAULT_QUEUE_SIZE: int = 10_000

_queue: "queue.Queue[dict] | None" = None
_stats_lock = threading.Lock()
_stats = {
    "emitted": 0,
    "dropped": 0,
    "queued": 0,
    "errors": 0
}

def is_enabled() -> bool:
    """True when SENTINELSCAN_TELEMETRY_ENABLED is one of 1/true/yes/on."""
    val = os.environ.get("SENTINELSCAN_TELEMETRY_ENABLED", "0").lower()
    return val in ("1", "true", "yes", "on")

def get_queue() -> "queue.Queue[dict]":
    """The bounded queue Workstream B's sink thread drains. Created lazily."""
    global _queue
    if _queue is None:
        try:
            size_str = os.environ.get("SENTINELSCAN_TELEMETRY_QUEUE_SIZE", str(DEFAULT_QUEUE_SIZE))
            size = int(size_str)
        except ValueError:
            size = DEFAULT_QUEUE_SIZE
        _queue = queue.Queue(maxsize=size)
    return _queue

def emit_event(event: dict) -> None:
    """Enqueues one event. Never blocks. Never raises. Never retries."""
    if not is_enabled():
        return

    try:
        q = get_queue()
        q.put_nowait(event)
        with _stats_lock:
            _stats["emitted"] += 1
            _stats["queued"] = q.qsize()
        
        # Standalone mode printing
        if os.environ.get("SENTINELSCAN_TELEMETRY_STDOUT", "0").lower() in ("1", "true", "yes", "on"):
            try:
                print(json.dumps(event))
            except Exception:
                pass
                
    except queue.Full:
        with _stats_lock:
            _stats["dropped"] += 1
    except Exception:
        with _stats_lock:
            _stats["errors"] += 1

def emit(*, level: str, source: str, category: str, message: str, **kwargs) -> None:
    """Convenience: build_event(...) then emit_event(...)."""
    if not is_enabled():
        return
        
    try:
        event = build_event(level=level, source=source, category=category, message=message, **kwargs)
        emit_event(event)
    except Exception:
        with _stats_lock:
            _stats["errors"] += 1

def get_stats() -> dict:
    """{'emitted': int, 'dropped': int, 'queued': int, 'errors': int}"""
    with _stats_lock:
        if _queue is not None:
            _stats["queued"] = _queue.qsize()
        return dict(_stats)

def drain_for_test(max_items: int = 1000) -> list[dict]:
    """Test helper. Empties the queue and returns its contents."""
    if _queue is None:
        return []
        
    items = []
    try:
        for _ in range(max_items):
            items.append(_queue.get_nowait())
    except queue.Empty:
        pass
    
    with _stats_lock:
        _stats["queued"] = _queue.qsize()
    return items
