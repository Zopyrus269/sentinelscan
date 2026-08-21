"""Local-development sink backend.

Prints each event as one line of JSON instead of writing to Firestore, so telemetry can
be observed while running the app locally without Firebase credentials configured.
"""
import json
import sys
from typing import Any, Dict, List


class StdoutSink:
    """Sink backend that prints each event as one line of JSON to stdout."""

    def write_batch(self, events: List[Dict[str, Any]]) -> None:
        """Prints each event in `events` as its own JSON line."""
        for event in events:
            print(json.dumps(event, default=str), file=sys.stdout, flush=True)
