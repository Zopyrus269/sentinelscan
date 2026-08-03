"""
In-memory scan record store.

Tracks scan status/progress/results, keyed by scan_id. This is
intentionally simple (a thread-safe in-memory dict) rather than a real
database -- sufficient for a single-process Flask dev server, and easy
to swap for a real DB later without changing the API layer above it,
per the "no orchestration/business logic in workers, keep it simple"
project philosophy.
"""

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_lock = threading.Lock()
_SCANS: Dict[str, Dict[str, Any]] = {}


def create_scan(target: str) -> str:
    """Creates a new scan record in PENDING state and returns its scan_id."""
    scan_id = str(uuid.uuid4())
    with _lock:
        _SCANS[scan_id] = {
            "scan_id": scan_id,
            "target": target,
            "status": "PENDING",
            "current_action": None,
            "progress_percent": 0,
            "date": datetime.now(timezone.utc).isoformat(),
            "pdf_path": None,
            "json_path": None,
            "error": None,
            "events": [],
        }
    return scan_id


def update_scan(scan_id: str, **fields: Any) -> None:
    """Updates one or more fields on an existing scan record."""
    with _lock:
        if scan_id in _SCANS:
            _SCANS[scan_id].update(fields)


def add_scan_event(scan_id: str, level: str, message: str, tool_name: Optional[str] = None) -> None:
    """Appends an event to the scan's events list."""
    with _lock:
        if scan_id in _SCANS:
            _SCANS[scan_id]["events"].append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": level,
                "message": message,
                "tool_name": tool_name,
            })


def get_scan(scan_id: str) -> Optional[Dict[str, Any]]:
    """Returns a copy of the scan record, or None if scan_id is unknown."""
    with _lock:
        scan = _SCANS.get(scan_id)
        return dict(scan) if scan else None


def list_scans() -> List[Dict[str, Any]]:
    """Returns a summary (scan_id, target, status, date) of every scan."""
    with _lock:
        return [
            {
                "scan_id": s["scan_id"],
                "target": s["target"],
                "status": s["status"],
                "date": s["date"],
            }
            for s in _SCANS.values()
        ]
