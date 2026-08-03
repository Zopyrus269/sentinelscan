"""
REST API routes per docs/API.md.

Exposes the AI agent's run_scan() function over HTTP for the frontend
to call. Scans run in a background thread so the POST endpoint returns
immediately with a scan_id, rather than blocking for the full scan
duration.
"""

import json
import os
import threading
from datetime import datetime, timezone
from typing import Tuple

from flask import Blueprint, jsonify, request, send_file, Response

from apps.backend.agent.orchestrator import run_scan
from apps.backend.models.scan_store import create_scan, get_scan, list_scans, update_scan, add_scan_event

scan_bp = Blueprint("scan_routes", __name__, url_prefix="/api/v1")

_STATUS_TEXT = {400: "Bad Request", 404: "Not Found", 500: "Internal Server Error"}


def _error(message: str, code: int) -> Tuple[Response, int]:
    """Builds the project-standard error response shape per docs/API.md."""
    return jsonify({
        "error": _STATUS_TEXT.get(code, "Error"),
        "message": message,
        "code": code,
    }), code


def _run_scan_background(scan_id: str, target: str) -> None:
    """Runs the agent scan on a background thread, updating scan_store as it progresses."""
    update_scan(scan_id, status="IN_PROGRESS")

    def on_progress(iteration: int, max_iterations: int, tool_name: str) -> None:
        percent = min(99, round((iteration / max_iterations) * 100))
        update_scan(scan_id, current_action=tool_name, progress_percent=percent)
        add_scan_event(scan_id, level="info", message=f"Running {tool_name}", tool_name=tool_name)

    try:
        result = run_scan(target, on_progress=on_progress)
        if result.get("status") == "complete":
            report = result.get("report", {})
            update_scan(
                scan_id,
                status="COMPLETED",
                current_action=None,
                progress_percent=100,
                completed_at=datetime.now(timezone.utc).isoformat(),
                pdf_path=report.get("pdf_path"),
                json_path=report.get("json_path"),
            )
        else:
            add_scan_event(scan_id, level="error", message=result.get("error", "Scan did not complete"))
            update_scan(
                scan_id,
                status="FAILED",
                current_action=None,
                completed_at=datetime.now(timezone.utc).isoformat(),
                error=result.get("error", "Scan did not complete"),
            )
    except Exception as e:
        add_scan_event(scan_id, level="error", message=str(e))
        update_scan(scan_id, status="FAILED", current_action=None, completed_at=datetime.now(timezone.utc).isoformat(), error=str(e))


@scan_bp.route("/scans", methods=["POST"])
def start_scan():
    """POST /api/v1/scans -- initiates a new scan, returns immediately with PENDING status."""
    data = request.get_json(silent=True) or {}
    raw_target = data.get("target")
    target = raw_target.strip() if isinstance(raw_target, str) else ""

    if not target:
        return _error("Request body must include a non-empty 'target' string.", 400)

    scan_id = create_scan(target)
    thread = threading.Thread(target=_run_scan_background, args=(scan_id, target), daemon=True)
    thread.start()

    return jsonify({"scan_id": scan_id, "status": "PENDING"}), 202


@scan_bp.route("/scans/<scan_id>", methods=["GET"])
def get_scan_status(scan_id: str):
    """GET /api/v1/scans/<scan_id> -- polls the status/progress of a scan."""
    scan = get_scan(scan_id)
    if not scan:
        return _error("The requested scan_id does not exist.", 404)

    return jsonify({
        "scan_id": scan["scan_id"],
        "target": scan["target"],
        "started_at": scan["date"].isoformat() if hasattr(scan["date"], "isoformat") else scan["date"],
        "completed_at": scan.get("completed_at"),
        "events": scan.get("events", []),
        "status": scan["status"],
        "current_action": scan.get("current_action"),
        "progress_percent": scan.get("progress_percent", 0),
    })


@scan_bp.route("/scans", methods=["GET"])
def list_all_scans():
    """GET /api/v1/scans -- lists all scans ever run (historical record)."""
    return jsonify({"scans": list_scans()})


@scan_bp.route("/reports/<scan_id>/json", methods=["GET"])
def get_report_json(scan_id: str):
    """GET /api/v1/reports/<scan_id>/json -- returns the completed scan's JSON report."""
    scan = get_scan(scan_id)
    if not scan:
        return _error("The requested scan_id does not exist.", 404)
    if scan["status"] != "COMPLETED":
        return _error(f"Report not ready. Scan status is '{scan['status']}'.", 404)

    json_path = scan.get("json_path")
    if not json_path or not os.path.exists(json_path):
        return _error("Report file not found on disk.", 404)

    with open(json_path, "r", encoding="utf-8") as f:
        report_data = json.load(f)
    return jsonify(report_data)


@scan_bp.route("/reports/<scan_id>/pdf", methods=["GET"])
def get_report_pdf(scan_id: str):
    """GET /api/v1/reports/<scan_id>/pdf -- downloads the completed scan's PDF report."""
    scan = get_scan(scan_id)
    if not scan:
        return _error("The requested scan_id does not exist.", 404)
    if scan["status"] != "COMPLETED":
        return _error(f"Report not ready. Scan status is '{scan['status']}'.", 404)

    pdf_path = scan.get("pdf_path")
    if not pdf_path or not os.path.exists(pdf_path):
        return _error("Report file not found on disk.", 404)

    return send_file(pdf_path, mimetype="application/pdf", as_attachment=True)
