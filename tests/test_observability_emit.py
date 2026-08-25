import pytest
import os
import queue
from apps.backend.observability.emit import emit_event, get_stats, drain_for_test, get_queue

def test_emit_never_blocks_or_raises(monkeypatch):
    # Enable telemetry and set a tiny queue size
    monkeypatch.setenv("SENTINELSCAN_TELEMETRY_ENABLED", "1")
    monkeypatch.setenv("SENTINELSCAN_TELEMETRY_QUEUE_SIZE", "2")
    
    # We must reset the lazily-created queue in the module so it picks up the new size
    import apps.backend.observability.emit as emit_mod
    emit_mod._queue = None
    emit_mod._stats = {"emitted": 0, "dropped": 0, "queued": 0, "errors": 0}
    
    # Fill the queue
    q = get_queue()
    event1 = {"test": 1}
    event2 = {"test": 2}
    event3 = {"test": 3}
    
    start_stats = get_stats()
    
    emit_event(event1)
    emit_event(event2)
    
    stats = get_stats()
    assert stats["emitted"] - start_stats["emitted"] == 2
    
    # This should drop the event but not raise or block
    emit_event(event3)
    
    stats = get_stats()
    assert stats["dropped"] - start_stats["dropped"] == 1
    
    # Clean up
    drain_for_test()
