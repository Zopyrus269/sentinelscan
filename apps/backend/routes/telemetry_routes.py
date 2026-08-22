"""POST /api/v1/telemetry -- the browser client's ingest endpoint.

This is the only publicly-exposed, unauthenticated surface in the whole observability feature,
so it gets the most scrutiny: a hard request-size cap, a per-batch event cap, strict per-event
schema validation with unknown fields dropped, rate limiting, and a server-side-only `uid`
(never trusted from the client). Accepted events are hand off to the sink pipeline
(`apps.backend.logstore.pipeline`) via a non-blocking queue put and the response is returned
immediately -- this must never wait on a write.
"""
import logging
from queue import Full
from typing import Tuple

from flask import Blueprint, Response, jsonify, request

from apps.backend.extensions import limiter
from apps.backend.logstore import pipeline
from apps.backend.logstore.event_validation import (
    MAX_EVENTS_PER_BATCH,
    MAX_REQUEST_BYTES,
    build_frontend_event,
)
from apps.backend.logstore.query import get_write_budget_status

_LOW_VALUE_LEVELS = ("debug", "info")

try:
    from firebase_admin import auth as firebase_auth
except ImportError:
    firebase_auth = None

logger = logging.getLogger(__name__)

telemetry_bp = Blueprint("telemetry_routes", __name__, url_prefix="/api/v1")

_STATUS_TEXT = {400: "Bad Request", 413: "Payload Too Large"}


def _error(message: str, code: int) -> Tuple[Response, int]:
    """Builds the project-standard error response shape per docs/API.md."""
    return jsonify({
        "error": _STATUS_TEXT.get(code, "Error"),
        "message": message,
        "code": code,
    }), code


def _derive_uid() -> None:
    """Optionally verifies a Firebase ID token; never fails the request.

    Returns the verified uid, or None if the header is absent, malformed, or the token is
    invalid/expired -- this endpoint accepts unauthenticated browser events too, so auth
    failure is never an error here, only a missing identity.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer ") or firebase_auth is None:
        return None
    id_token = auth_header.split("Bearer ", 1)[1].strip()
    try:
        decoded = firebase_auth.verify_id_token(id_token)
        return decoded.get("uid")
    except Exception:
        return None


@telemetry_bp.route("/telemetry", methods=["POST"])
@limiter.limit("60 per minute")
def ingest_telemetry():
    """POST /api/v1/telemetry -- accepts a batch of browser-originated events."""
    if not pipeline.is_enabled():
        return "", 204

    raw_body = request.get_data()
    if len(raw_body) > MAX_REQUEST_BYTES:
        return _error("Request body exceeds the maximum allowed size.", 413)

    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get("events"), list) or not body["events"]:
        return _error("Request body must be a JSON object with a non-empty 'events' list.", 400)

    events = body["events"]
    if len(events) > MAX_EVENTS_PER_BATCH:
        return _error(f"A batch may contain at most {MAX_EVENTS_PER_BATCH} events.", 400)

    uid = _derive_uid()
    queue = pipeline.get_queue()
    near_cap = get_write_budget_status()["near_cap"]
    for raw_event in events:
        event = build_frontend_event(raw_event, uid=uid)
        if event is None:
            continue
        if near_cap and event["level"] in _LOW_VALUE_LEVELS:
            # Circuit breaker: as today's Firestore write budget is approached, drop the
            # lowest-value events first (debug/info) so warn/error/fatal and requests keep
            # getting recorded. Still a silent drop, matching every other validation-drop
            # path here -- the client never learns which events made it in.
            continue
        try:
            queue.put_nowait(event)
        except Full:
            logger.warning("telemetry queue full, dropping event")

    return "", 204
