"""
Developer-only HTTP API routes for the SentinelScan Log Site.

All endpoints require authentication and developer allowlist verification.
Validates input parameters and delegates data retrieval directly to Workstream B's
logstore query layer.
"""
from datetime import datetime, timezone
import sys
from typing import Any, Callable, Dict, Optional

from flask import Blueprint, jsonify, request

from apps.logsite.auth import require_auth, require_developer

api_bp = Blueprint("logsite_api", __name__, url_prefix="/api")

# Named constants for component and overall states
STATE_OPERATIONAL = "operational"
STATE_DEGRADED = "degraded"
STATE_DOWN = "down"

VALID_LEVELS = {"debug", "info", "warn", "error", "fatal"}
VALID_SOURCES = {"frontend", "backend", "agent", "worker"}
VALID_CATEGORIES = {"http", "auth", "scan", "agent", "worker", "llm", "ui", "error", "health"}
VALID_GROUP_BY = {"day", "hour"}


def _get_query_fn(name: str) -> Optional[Callable]:
    """Dynamically resolves a query function from apps.backend.logstore.query."""
    mod = sys.modules.get("apps.backend.logstore.query")
    if mod and hasattr(mod, name):
        return getattr(mod, name)
    try:
        from apps.backend.logstore import query as logstore_query
        return getattr(logstore_query, name)
    except (ImportError, AttributeError):
        return None


def _error(message: str, code: int = 400, error_type: str = "Bad Request"):
    """Returns standard error shape matching project conventions."""
    return jsonify({
        "error": error_type,
        "message": message,
        "code": code
    }), code


def _parse_iso_date(val: Optional[str], param_name: str) -> Optional[str]:
    """Validates an ISO date/time string parameter."""
    if not val:
        return None
    try:
        # Check standard ISO format parsing
        datetime.fromisoformat(val.replace("Z", "+00:00"))
        return val
    except (ValueError, AttributeError):
        raise ValueError(f"Invalid ISO datetime format for parameter '{param_name}': {val}")


@api_bp.route("/status", methods=["GET"])
@require_auth
@require_developer
def get_status():
    """GET /api/status -- Returns status board component health and overall state."""
    fn_health = _get_query_fn("get_health_snapshot")
    health = fn_health() if callable(fn_health) else {}
    if not isinstance(health, dict):
        health = {}

    fn_uptime = _get_query_fn("get_uptime_history")
    uptime = fn_uptime(days=1) if callable(fn_uptime) else []
    if not isinstance(uptime, list):
        uptime = []

    # Calculate individual component health states
    # Web component
    web_state = STATE_OPERATIONAL
    web_detail = "200 OK"
    if uptime and len(uptime) > 0:
        latest = uptime[0]
        failures = latest.get("failures", 0)
        checks = latest.get("checks", 0)
        if checks > 0 and failures > 0:
            if failures / checks > 0.2:
                web_state = STATE_DOWN
                web_detail = f"{failures}/{checks} checks failed"
            else:
                web_state = STATE_DEGRADED
                web_detail = f"{failures}/{checks} checks failed"

    # Scan API component
    error_rate = health.get("error_rate", 0.0)
    scan_state = STATE_OPERATIONAL
    scan_detail = f"error rate {error_rate * 100:.1f}%"
    if error_rate > 0.25:
        scan_state = STATE_DOWN
    elif error_rate > 0.05:
        scan_state = STATE_DEGRADED

    # Gemini component
    llm_fail_rate = health.get("llm_failure_rate", 0.0)
    gemini_state = STATE_OPERATIONAL
    gemini_detail = f"failure rate {llm_fail_rate * 100:.1f}%"
    if llm_fail_rate > 0.3:
        gemini_state = STATE_DOWN
    elif llm_fail_rate > 0.05:
        gemini_state = STATE_DEGRADED

    # Firestore component
    firestore_state = STATE_OPERATIONAL
    firestore_detail = None

    # Workers component
    workers = health.get("workers", [])
    workers_state = STATE_OPERATIONAL
    total_workers = len(workers)
    failed_workers = sum(1 for w in workers if w.get("success_rate", 1.0) < 0.8)
    if total_workers > 0 and failed_workers > 0:
        if failed_workers / total_workers > 0.5:
            workers_state = STATE_DOWN
        else:
            workers_state = STATE_DEGRADED
        workers_detail = f"{failed_workers}/{total_workers} workers degraded"
    else:
        workers_detail = f"{total_workers} workers operational" if total_workers > 0 else "All workers operational"

    components = [
        {"name": "Web", "state": web_state, "detail": web_detail},
        {"name": "Scan API", "state": scan_state, "detail": scan_detail},
        {"name": "Gemini", "state": gemini_state, "detail": gemini_detail},
        {"name": "Firestore", "state": firestore_state, "detail": firestore_detail},
        {"name": "Workers", "state": workers_state, "detail": workers_detail},
    ]

    states = [c["state"] for c in components]
    if STATE_DOWN in states:
        overall = STATE_DOWN
    elif STATE_DEGRADED in states:
        overall = STATE_DEGRADED
    else:
        overall = STATE_OPERATIONAL

    checked_at = datetime.now(timezone.utc).isoformat()

    return jsonify({
        "overall": overall,
        "checked_at": checked_at,
        "components": components,
    })


@api_bp.route("/uptime", methods=["GET"])
@require_auth
@require_developer
def get_uptime():
    """GET /api/uptime?days=90 -- Returns daily uptime history."""
    days_str = request.args.get("days", "90")
    try:
        days = int(days_str)
        if days <= 0:
            return _error("Parameter 'days' must be a positive integer.")
    except ValueError:
        return _error("Parameter 'days' must be a valid integer.")

    fn = _get_query_fn("get_uptime_history")
    res = fn(days=days) if callable(fn) else []
    return jsonify(res if isinstance(res, list) else [])


@api_bp.route("/active-users", methods=["GET"])
@require_auth
@require_developer
def get_active_users():
    """GET /api/active-users?window=5 -- Returns active user count and sessions."""
    window_str = request.args.get("window", "5")
    try:
        window = int(window_str)
        if window <= 0:
            return _error("Parameter 'window' must be a positive integer.")
    except ValueError:
        return _error("Parameter 'window' must be a valid integer.")

    fn = _get_query_fn("count_active_users")
    res = fn(window_minutes=window) if callable(fn) else {"count": 0, "sessions": []}
    return jsonify(res if isinstance(res, dict) else {"count": 0, "sessions": []})


@api_bp.route("/events", methods=["GET"])
@require_auth
@require_developer
def get_events():
    """GET /api/events -- Queries events with filtering and cursor pagination."""
    limit_str = request.args.get("limit", "200")
    try:
        limit = int(limit_str)
        if limit <= 0:
            return _error("Parameter 'limit' must be a positive integer.")
        if limit > 500:
            return _error("Limit cannot exceed 500.")
    except ValueError:
        return _error("Parameter 'limit' must be a valid integer.")

    level = request.args.get("level")
    if level and level not in VALID_LEVELS:
        return _error(f"Invalid level '{level}'. Must be one of {sorted(VALID_LEVELS)}.")

    source = request.args.get("source")
    if source and source not in VALID_SOURCES:
        return _error(f"Invalid source '{source}'. Must be one of {sorted(VALID_SOURCES)}.")

    category = request.args.get("category")
    if category and category not in VALID_CATEGORIES:
        return _error(f"Invalid category '{category}'. Must be one of {sorted(VALID_CATEGORIES)}.")

    try:
        since = _parse_iso_date(request.args.get("since"), "since")
        until = _parse_iso_date(request.args.get("until"), "until")
    except ValueError as err:
        return _error(str(err))

    session_id = request.args.get("session_id")
    uid = request.args.get("uid")
    trace_id = request.args.get("trace_id")
    scan_id = request.args.get("scan_id")
    cursor = request.args.get("cursor")

    fn = _get_query_fn("query_events")
    if callable(fn):
        res = fn(
            since=since,
            until=until,
            level=level,
            source=source,
            category=category,
            session_id=session_id,
            uid=uid,
            trace_id=trace_id,
            scan_id=scan_id,
            cursor=cursor,
            limit=limit,
        )
    else:
        res = {"events": [], "next_cursor": None}

    return jsonify(res if isinstance(res, dict) else {"events": [], "next_cursor": None})


@api_bp.route("/sessions", methods=["GET"])
@require_auth
@require_developer
def get_sessions():
    """GET /api/sessions?since=&limit=50 -- Lists active or historical user sessions."""
    limit_str = request.args.get("limit", "50")
    try:
        limit = int(limit_str)
        if limit <= 0:
            return _error("Parameter 'limit' must be a positive integer.")
        if limit > 500:
            return _error("Limit cannot exceed 500.")
    except ValueError:
        return _error("Parameter 'limit' must be a valid integer.")

    try:
        since = _parse_iso_date(request.args.get("since"), "since")
    except ValueError as err:
        return _error(str(err))

    fn = _get_query_fn("list_sessions")
    res = fn(since=since, limit=limit) if callable(fn) else []
    return jsonify(res if isinstance(res, list) else [])


@api_bp.route("/sessions/<session_id>", methods=["GET"])
@require_auth
@require_developer
def get_session(session_id: str):
    """GET /api/sessions/<session_id> -- Returns complete session timeline."""
    if not session_id or not session_id.strip():
        return _error("Missing or invalid session_id.")

    fn = _get_query_fn("get_session_timeline")
    res = fn(session_id=session_id) if callable(fn) else {
        "session_id": session_id,
        "uid": None,
        "started_at": None,
        "last_seen": None,
        "events": [],
    }
    return jsonify(res if isinstance(res, dict) else {"session_id": session_id, "events": []})


@api_bp.route("/traces/<trace_id>", methods=["GET"])
@require_auth
@require_developer
def get_trace_events(trace_id: str):
    """GET /api/traces/<trace_id> -- Returns events tied to a single trace."""
    if not trace_id or not trace_id.strip():
        return _error("Missing or invalid trace_id.")

    fn = _get_query_fn("get_trace")
    res = fn(trace_id=trace_id) if callable(fn) else {"trace_id": trace_id, "events": []}
    return jsonify(res if isinstance(res, dict) else {"trace_id": trace_id, "events": []})


@api_bp.route("/llm-usage", methods=["GET"])
@require_auth
@require_developer
def get_llm():
    """GET /api/llm-usage?since=&until=&group_by=day -- Returns Gemini token metrics."""
    group_by = request.args.get("group_by", "day")
    if group_by not in VALID_GROUP_BY:
        return _error(f"Invalid group_by '{group_by}'. Must be one of {sorted(VALID_GROUP_BY)}.")

    try:
        since = _parse_iso_date(request.args.get("since"), "since")
        until = _parse_iso_date(request.args.get("until"), "until")
    except ValueError as err:
        return _error(str(err))

    fn = _get_query_fn("get_llm_usage")
    res = fn(since=since, until=until, group_by=group_by) if callable(fn) else {
        "total_tokens": 0,
        "prompt_tokens": 0,
        "response_tokens": 0,
        "calls": 0,
        "cache_hits": 0,
        "buckets": [],
    }
    return jsonify(res if isinstance(res, dict) else {})


@api_bp.route("/health", methods=["GET"])
@require_auth
@require_developer
def get_health():
    """GET /api/health -- Returns detailed application health snapshot."""
    fn = _get_query_fn("get_health_snapshot")
    res = fn() if callable(fn) else {
        "error_rate": 0.0,
        "p50_ms": 0,
        "p95_ms": 0,
        "requests_1h": 0,
        "workers": [],
        "llm_failure_rate": 0.0,
    }
    return jsonify(res if isinstance(res, dict) else {})


@api_bp.route("/stats/<date>", methods=["GET"])
@require_auth
@require_developer
def get_stats_for_date(date: str):
    """GET /api/stats/<date> -- Returns aggregated daily stats for a YYYY-MM-DD date."""
    if not date or len(date) != 10 or date.count("-") != 2:
        return _error("Date must be in YYYY-MM-DD format.")

    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return _error("Date must be a valid YYYY-MM-DD calendar date.")

    fn = _get_query_fn("get_daily_stats")
    res = fn(date=date) if callable(fn) else {
        "date": date,
        "events": 0,
        "errors": 0,
        "requests": 0,
        "scans": 0,
        "llm_calls": 0,
        "llm_tokens": 0,
        "unique_sessions": 0,
    }
    return jsonify(res if isinstance(res, dict) else {"date": date})
