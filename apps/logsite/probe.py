"""
Uptime probe ingest and history reader for the SentinelScan Log Site.

Provides the POST /api/probe endpoint for receiving scheduled uptime check
payloads from the GitHub Actions workflow using HMAC timing-safe secret
comparison.
"""
import hmac
import os
import sys
from typing import Any, Dict, List, Optional
from flask import Blueprint, request, jsonify

probe_bp = Blueprint("probe_routes", __name__, url_prefix="/api")


def _get_query_fn(name: str):
    """Dynamically resolves a query function from apps.backend.logstore.query."""
    mod = sys.modules.get("apps.backend.logstore.query")
    if mod and hasattr(mod, name):
        return getattr(mod, name)
    try:
        from apps.backend.logstore import query as logstore_query
        return getattr(logstore_query, name)
    except (ImportError, AttributeError):
        return None


def get_uptime_history_data(days: int = 90) -> List[Dict[str, Any]]:
    """
    Fetches daily uptime history for the specified number of days.
    
    Returns an empty list if logstore.query is not configured.
    """
    fn = _get_query_fn("get_uptime_history")
    if callable(fn):
        res = fn(days=days)
        if isinstance(res, list):
            return res
    return []


@probe_bp.route("/probe", methods=["POST"])
def record_probe():
    """
    POST /api/probe -- Ingests external uptime probe results.
    
    Gated by X-Probe-Token header matching LOGSITE_PROBE_TOKEN env variable
    using constant-time hmac.compare_digest.
    """
    token_header = request.headers.get("X-Probe-Token", "")
    expected_token = os.environ.get("LOGSITE_PROBE_TOKEN", "")

    if not token_header or not expected_token:
        return jsonify({
            "error": "Unauthorized",
            "message": "Invalid or missing probe token.",
            "code": 401,
        }), 401

    if not hmac.compare_digest(token_header.encode("utf-8"), expected_token.encode("utf-8")):
        return jsonify({
            "error": "Unauthorized",
            "message": "Invalid or missing probe token.",
            "code": 401,
        }), 401

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({
            "error": "Bad Request",
            "message": "Payload must be a JSON object.",
            "code": 400,
        }), 400

    required_keys = {"component", "ok", "status", "latency_ms", "checked_at"}
    if not required_keys.issubset(data.keys()):
        return jsonify({
            "error": "Bad Request",
            "message": f"Missing required probe fields: {required_keys - data.keys()}",
            "code": 400,
        }), 400

    if not isinstance(data["ok"], bool):
        return jsonify({
            "error": "Bad Request",
            "message": "'ok' field must be a boolean.",
            "code": 400,
        }), 400

    if not isinstance(data["status"], int):
        return jsonify({
            "error": "Bad Request",
            "message": "'status' field must be an integer.",
            "code": 400,
        }), 400

    if not isinstance(data["latency_ms"], (int, float)):
        return jsonify({
            "error": "Bad Request",
            "message": "'latency_ms' field must be numeric.",
            "code": 400,
        }), 400

    if not isinstance(data["checked_at"], str):
        return jsonify({
            "error": "Bad Request",
            "message": "'checked_at' field must be a string timestamp.",
            "code": 400,
        }), 400

    fn = _get_query_fn("record_uptime_probe")
    if callable(fn):
        fn(data)

    return "", 204
