import threading
import time
from apps.backend.observability.context import (
    set_context, get_context, clear_context, snapshot, restore, bound
)

def test_context_survives_thread_handoff():
    clear_context()
    set_context(trace_id="test-trace-123", session_id="test-session-456")
    
    snap = snapshot()
    
    result_trace = []
    
    def worker(ctx_snap):
        restore(ctx_snap)
        ctx = get_context()
        result_trace.append(ctx.get("trace_id"))
        result_trace.append(ctx.get("session_id"))
        
    thread = threading.Thread(target=worker, args=(snap,))
    thread.start()
    thread.join(timeout=2.0)
    
    assert result_trace == ["test-trace-123", "test-session-456"]

def test_bound_context():
    clear_context()
    set_context(trace_id="original")
    
    with bound(trace_id="temporary"):
        ctx = get_context()
        assert ctx.get("trace_id") == "temporary"
        
    ctx = get_context()
    assert ctx.get("trace_id") == "original"
