import pytest
import os
import queue
from apps.backend.observability.emit import emit_event, get_stats, drain_for_test, get_queue

def test_emit_never_blocks_or_raises(monkeypatch):
    # Enable telemetry and set a tiny queue size
    monkeypatch.setenv("SENTINELSCAN_TELEMETRY_ENABLED", "1")
    monkeypatch.setenv("SENTINELSCAN_TELEMETRY_QUEUE_SIZE", "2")

    # emit.get_queue() is apps.backend.logstore.pipeline.get_queue() -- the shared queue
    # sink.py's thread drains. Reset pipeline's module state (not emit's own; it no longer
    # owns a queue) so this test's queue picks up the new size.
    import apps.backend.observability.emit as emit_mod
    import apps.backend.logstore.pipeline as pipeline_mod
    pipeline_mod._queue = None
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
    
    # Clean up -- also reset the queue itself, not just its contents, so the tiny
    # maxsize=2 from this test doesn't leak into whichever test runs next.
    drain_for_test()
    pipeline_mod._queue = None
