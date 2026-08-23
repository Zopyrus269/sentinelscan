import json
from apps.backend.observability.events import build_event, validate_event, fingerprint

def test_event_schema_conformance():
    event = build_event(
        level="info",
        source="backend",
        category="http",
        message="Test event",
        data={"key": "value"},
        duration_ms=100
    )
    
    is_valid, reason = validate_event(event)
    assert is_valid, reason
    
    assert event["level"] == "info"
    assert event["source"] == "backend"
    assert event["category"] == "http"
    assert event["message"] == "Test event"
    assert event["duration_ms"] == 100
    
    # Must have tz-aware UTC
    assert "+00:00" in event["ts"]
    
def test_validate_event_rejects_bad_data():
    event = build_event(
        level="bad_level",
        source="backend",
        category="http",
        message="Test event"
    )
    is_valid, reason = validate_event(event)
    assert not is_valid
    assert "Invalid level" in reason
    
def test_fingerprint_stability():
    fp1 = fingerprint("ValueError", "app.py:do_something")
    fp2 = fingerprint("ValueError", "app.py:do_something")
    fp3 = fingerprint("TypeError", "app.py:do_something")
    
    assert fp1 == fp2
    assert fp1 != fp3
    assert len(fp1) == 8
