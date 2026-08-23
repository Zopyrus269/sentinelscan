from apps.backend.observability.redaction import (
    redact_headers, redact_data, scrub_text, hash_ip, query_keys
)

def test_scrub_text():
    # Test JWT
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    text = f"User logged in with token {jwt} successfully"
    assert "eyJ" not in scrub_text(text)
    assert "[REDACTED]" in scrub_text(text)
    
    # Test API Key
    api_key = "AIzaSyCXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
    text = f"Using {api_key} for maps"
    assert "AIzaSy" not in scrub_text(text)
    
    # Test Bearer
    bearer = "Bearer abcdef12345"
    text = f"Auth: {bearer}"
    assert "abcdef" not in scrub_text(text)
    
    # Test Opaque Blob
    blob = "a" * 45
    assert "[REDACTED]" in scrub_text(blob)
    
def test_hash_ip(monkeypatch):
    monkeypatch.setenv("TELEMETRY_IP_SALT", "test_salt")
    hashed1 = hash_ip("192.168.1.1")
    hashed2 = hash_ip("192.168.1.1")
    assert hashed1 == hashed2
    assert "192" not in hashed1
    assert len(hashed1) == 16
    
def test_query_keys():
    q = "foo=bar&baz=qux&foo=baz"
    keys = query_keys(q)
    assert "foo" in keys
    assert "baz" in keys
    assert "bar" not in keys
    
def test_redact_headers():
    headers = {
        "Authorization": "Bearer secret",
        "X-Custom": "public info",
        "Cookie": "session=123"
    }
    redacted = redact_headers(headers)
    assert redacted["Authorization"] == "[REDACTED]"
    assert redacted["Cookie"] == "[REDACTED]"
    assert redacted["X-Custom"] == "public info"
    
def test_redact_data():
    data = {
        "public": "info",
        "password": "super_secret",
        "nested": {
            "token": "api_token",
            "safe": "data",
            "list": [
                {"secret": "hidden", "visible": "shown"}
            ]
        },
        "long_string": "A " * 1500
    }
    
    redacted = redact_data(data)
    assert redacted["public"] == "info"
    assert redacted["password"] == "[REDACTED]"
    assert redacted["nested"]["token"] == "[REDACTED]"
    assert redacted["nested"]["safe"] == "data"
    assert redacted["nested"]["list"][0]["secret"] == "[REDACTED]"
    assert redacted["nested"]["list"][0]["visible"] == "shown"
    assert redacted["long_string"].endswith("[truncated]")
    assert len(redacted["long_string"]) < 2050
