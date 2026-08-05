"""
REST API routes for completed scan history.

Exposes historical scans fetched from Firestore. These routes are completely
separate from the live scan monitoring routes (scan_routes.py).
"""

import logging
from flask import Blueprint, jsonify, g

from apps.backend.auth.auth_utils import require_auth
from apps.backend.models.history_store import get_user_scan_history, get_scan

logger = logging.getLogger(__name__)

history_bp = Blueprint("history_routes", __name__, url_prefix="/api/v1")

@history_bp.route("/history", methods=["GET"])
@require_auth
def list_history():
    """GET /api/v1/history -- retrieves all completed scans for the authenticated user."""
    uid = g.user.get("uid")
    if not uid:
        return jsonify({"error": "Unauthorized", "message": "User UID not found in session.", "code": 401}), 401

    try:
        scans = get_user_scan_history(uid)
        formatted_scans = []
        for s in scans:
            item = {
                "scan_id": s.get("scan_id"),
                "target": s.get("target"),
                "status": s.get("status"),
                "started_at": s.get("timestamps", {}).get("started_at"),
                "completed_at": s.get("timestamps", {}).get("completed_at"),
            }
            # Attempt to extract summary if it was fetched
            report_data = s.get("report_data")
            if report_data and isinstance(report_data, dict):
                item["summary"] = report_data.get("simple_explanation")
                
            formatted_scans.append(item)
            
        return jsonify(formatted_scans), 200
    except Exception as e:
        logger.error("Failed to retrieve scan history for %s: %s", uid, e, exc_info=True)
        return jsonify({"error": "Internal Server Error", "message": "Failed to retrieve history.", "code": 500}), 500


@history_bp.route("/history/<scan_id>", methods=["GET"])
@require_auth
def get_history_scan(scan_id: str):
    """GET /api/v1/history/<scan_id> -- retrieves a specific completed scan document."""
    uid = g.user.get("uid")
    if not uid:
        return jsonify({"error": "Unauthorized", "message": "User UID not found in session.", "code": 401}), 401

    try:
        scan = get_scan(uid, scan_id)
        if not scan:
            return jsonify({"error": "Not Found", "message": "History item not found or does not belong to user.", "code": 404}), 404
        
        return jsonify(scan), 200
    except Exception as e:
        logger.error("Failed to retrieve scan %s for %s: %s", scan_id, uid, e, exc_info=True)
        return jsonify({"error": "Internal Server Error", "message": "Failed to retrieve history scan.", "code": 500}), 500
