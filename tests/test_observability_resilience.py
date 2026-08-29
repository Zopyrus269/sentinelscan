import queue
from apps.backend.observability.emit import emit_event, get_queue

def test_simulated_total_outage(monkeypatch):
    monkeypatch.setenv("SENTINELSCAN_TELEMETRY_ENABLED", "1")
    monkeypatch.setenv("SENTINELSCAN_TELEMETRY_QUEUE_SIZE", "1")
    
    import apps.backend.observability.emit as emit_module
    from apps.backend.observability.emit import get_stats
    emit_module._queue = None
    emit_module._stats = {"emitted": 0, "dropped": 0, "queued": 0, "errors": 0}
    
    q = get_queue()
    
    # Simulate an outage by completely breaking the queue's put_nowait method
    def broken_put(*args, **kwargs):
        raise RuntimeError("Total Firestore Outage Simulated")
        
    monkeypatch.setattr(q, "put_nowait", broken_put)
    
    # This should swallow the exception, increment errors, and return normally
    emit_event({"message": "test event"})
    
    stats = get_stats()
    assert stats["errors"] == 1
    # Main request handling would be unaffected because emit_event returned instantly
