import logging
from apps.backend.observability.logging_bridge import TelemetryHandler
from apps.backend.observability.emit import drain_for_test

def test_logging_bridge(monkeypatch):
    monkeypatch.setenv("SENTINELSCAN_TELEMETRY_ENABLED", "1")
    
    handler = TelemetryHandler()
    logger = logging.getLogger("test_apps.backend.workers.test")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    
    drain_for_test()
    
    # Should create worker event
    record = logging.LogRecord("apps.backend.workers.ssl", logging.WARNING, "ssl.py", 142, "SSL timeout", None, None)
    handler.emit(record)
    
    events = drain_for_test()
    assert len(events) == 1
    assert events[0]["source"] == "worker"
    assert events[0]["category"] == "worker"
    assert events[0]["level"] == "warn"
    
def test_logging_bridge_prevents_recursion(monkeypatch):
    monkeypatch.setenv("SENTINELSCAN_TELEMETRY_ENABLED", "1")
    handler = TelemetryHandler()
    
    record = logging.LogRecord("apps.backend.observability.test", logging.INFO, "test.py", 1, "test", None, None)
    handler.emit(record)
    
    events = drain_for_test()
    assert len(events) == 0
    
def test_handler_does_not_raise(monkeypatch):
    monkeypatch.setenv("SENTINELSCAN_TELEMETRY_ENABLED", "1")
    handler = TelemetryHandler()
    
    # Create a record that causes exception when formatted/processed
    class BadRecord:
        name = "apps.backend.test"
        levelno = logging.INFO
        exc_info = None
        funcName = "test"
        lineno = 1
        def getMessage(self):
            raise ValueError("bad message")
            
    handler.emit(BadRecord())
    # Should not raise exception
