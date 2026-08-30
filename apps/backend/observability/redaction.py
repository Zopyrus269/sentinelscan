import re
import os
import hashlib
from typing import Mapping, Any
from urllib.parse import parse_qs, urlparse

REDACTED: str = "[REDACTED]"

SENSITIVE_HEADERS: frozenset[str] = frozenset({
    "authorization", "cookie", "set-cookie", "x-api-key", "proxy-authorization",
})

SENSITIVE_KEYS: frozenset[str] = frozenset({
    "password", "passwd", "token", "id_token", "access_token", "refresh_token",
    "api_key", "apikey", "secret", "authorization", "credential", "private_key",
    "gemini_api_key", "flask_secret_key", "session", "cookie",
})

_JWT_REGEX = re.compile(r'eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+')
_API_KEY_REGEX = re.compile(r'AIza[0-9A-Za-z_\-]{35}')
_BEARER_REGEX = re.compile(r'(?i)bearer\s+[A-Za-z0-9._\-]+')
_OPAQUE_BLOB_REGEX = re.compile(r'[A-Za-z0-9+/=_-]{40,}')

def scrub_text(text: str) -> str:
    """Removes secret-shaped substrings from free text (messages, stack traces)."""
    if not isinstance(text, str):
        return str(text)
    
    text = _JWT_REGEX.sub(REDACTED, text)
    text = _API_KEY_REGEX.sub(REDACTED, text)
    text = _BEARER_REGEX.sub(REDACTED, text)
    text = _OPAQUE_BLOB_REGEX.sub(REDACTED, text)
    return text

def hash_ip(ip: str | None) -> str | None:
    """Salted SHA-256, first 16 hex characters. Never store a raw IP."""
    if not ip:
        return None
        
    salt = os.environ.get("TELEMETRY_IP_SALT") or \
           os.environ.get("FLASK_SECRET_KEY") or \
           "dev_constant_salt"
           
    salted = f"{salt}:{ip}".encode('utf-8')
    return hashlib.sha256(salted).hexdigest()[:16]

def query_keys(query_string: str) -> list[str]:
    """Returns parameter NAMES only. Values are never recorded."""
    if not query_string:
        return []
    # parse_qs handles the query string optionally without the '?'
    parsed = parse_qs(query_string)
    return list(parsed.keys())

def redact_headers(headers: Mapping[str, str]) -> dict:
    """Redacts sensitive headers."""
    redacted = {}
    for k, v in headers.items():
        if k.lower() in SENSITIVE_HEADERS:
            redacted[k] = REDACTED
        else:
            redacted[k] = scrub_text(str(v))
    return redacted

def redact_mapping(mapping: Mapping[str, Any], depth: int = 0) -> dict:
    """Redacts sensitive keys recursively."""
    if depth > 6:
        return {"_error": "Max depth exceeded"}
        
    redacted = {}
    for k, v in mapping.items():
        k_str = str(k)
        if k_str.lower() in SENSITIVE_KEYS:
            redacted[k_str] = REDACTED
        elif isinstance(v, dict):
            redacted[k_str] = redact_mapping(v, depth + 1)
        elif isinstance(v, (list, tuple)):
            # Basic list redaction, only going 1 level deep for lists to avoid complex depth logic
            new_list = []
            for item in v:
                if isinstance(item, dict):
                    new_list.append(redact_mapping(item, depth + 1))
                else:
                    new_list.append(_truncate_and_scrub(item))
            redacted[k_str] = new_list
        else:
            redacted[k_str] = _truncate_and_scrub(v)
            
    return redacted

def _truncate_and_scrub(val: Any) -> Any:
    if isinstance(val, (int, float, bool, type(None))):
        return val
    
    val_str = str(val)
    val_str = scrub_text(val_str)
    
    if len(val_str) > 2000:
        return val_str[:1988] + "...[truncated]"
    return val_str

def redact_data(data: dict) -> dict:
    """Recursive redaction plus truncation. Depth-limited to 6."""
    return redact_mapping(data, depth=0)
