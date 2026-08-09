"""
REST API routes per docs/API.md.

Exposes the AI agent's run_scan() function over HTTP for the frontend
to call. Scans run in a background thread so the POST endpoint returns
immediately with a scan_id, rather than blocking for the full scan
duration.
"""

import json
import logging
import os
import threading
import traceback
from datetime import datetime, timezone
from typing import Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

from flask import Blueprint, jsonify, request, send_file, Response

from apps.backend.agent.orchestrator import run_scan
from apps.backend.models.scan_store import create_scan, get_scan, list_scans, update_scan, add_scan_event
try:
    from firebase_admin import auth as firebase_auth
except ImportError:
    firebase_auth = None
from apps.backend.models.history_store import get_scan as get_history_scan
import tempfile

scan_bp = Blueprint("scan_routes", __name__, url_prefix="/api/v1")

def _verify_token_inline():
    """Helper to verify Firebase auth inline for fallback routes."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    id_token = auth_header.split("Bearer ", 1)[1].strip()
    try:
        decoded = firebase_auth.verify_id_token(id_token)
        return decoded.get("uid")
    except Exception:
        return None

_STATUS_TEXT = {400: "Bad Request", 404: "Not Found", 500: "Internal Server Error"}


def _error(message: str, code: int) -> Tuple[Response, int]:
    """Builds the project-standard error response shape per docs/API.md."""
    return jsonify({
        "error": _STATUS_TEXT.get(code, "Error"),
        "message": message,
        "code": code,
    }), code


# Load and clean the blocklist from the environment
env_domains = os.getenv("BLOCKED_DOMAINS", "google.com,youtube.com,facebook.com")
BLOCKED_DOMAINS = [d.strip().lower() for d in env_domains.split(",") if d.strip()]

def is_domain_blocked(target_url: str) -> bool:
    if not target_url:
        return False
        
    clean_target = target_url.lower()
    for prefix in ["https://", "http://", "www."]:
        clean_target = clean_target.replace(prefix, "")
        
    clean_target = clean_target.split('/')[0].split(':')[0]
    
    for blocked in BLOCKED_DOMAINS:
        if clean_target == blocked or clean_target.endswith(f".{blocked}"):
            return True
            
    return False


def _run_scan_background(scan_id: str, target: str, uid: str = None) -> None:
    """Runs the agent scan on a background thread, updating scan_store as it progresses."""
    update_scan(scan_id, status="IN_PROGRESS")

    evidence_tools = {
        "dns_lookup", "reverse_dns_lookup", "whois_lookup", "ssl_check",
        "http_headers", "cookie_analysis", "robots_txt_parse", "sitemap_parse",
        "port_scan", "ddos_resilience_check",
    }
    completed_evidence = set()

    def on_progress(
        iteration: int,
        max_iterations: int,
        tool_name: str,
        reasoning: str = "",
        phase: str = "selected",
        action: str = "",
        summary: str = "",
        status: str = "",
        duration: float = 0.0,
        **_: object,
    ) -> None:
        """Translate agent stages into monotonic UI progress and reasoning logs."""
        if phase == "completed" and tool_name in evidence_tools:
            completed_evidence.add(tool_name)

        if tool_name in evidence_tools:
            # 5-80% is reserved for the ten evidence categories.
            percent = 5 + int(round((len(completed_evidence) / 10.0) * 75))
            if phase == "selected" and not completed_evidence:
                percent = 5
        elif tool_name == "calculate_cvss":
            percent = 90 if phase == "selected" else 96
        elif tool_name == "generate_report":
            percent = 97 if phase == "selected" else 99
        else:
            percent = 5

        current = "Complete" if phase == "completed" and tool_name == "generate_report" else tool_name
        update_scan(scan_id, current_action=current, progress_percent=min(99, percent))

        if phase == "selected":
            message = f"AI selected {tool_name}."
            if action:
                message += f" Action: {action}"
            add_scan_event(
                scan_id,
                level="info",
                message=message,
                tool_name=tool_name,
                reasoning=reasoning,
                phase="selected",
                worker_status="RUNNING",
                action=action,
            )
        else:
            result_text = summary or f"{tool_name} finished with status {status or 'COMPLETED'}."
            add_scan_event(
                scan_id,
                level="info" if str(status).upper() not in {"FAILED", "TIMEOUT", "UNREACHABLE"} else "warning",
                message=f"{tool_name} {str(status or 'COMPLETED').lower()}: {result_text}",
                tool_name=tool_name,
                reasoning=reasoning,
                phase="completed",
                worker_status=str(status or "COMPLETED").upper(),
                action=action,
            )

    try:
        result = run_scan(target, on_progress=on_progress)
        if result.get("status") == "complete":
            report = result.get("report", {})
            update_scan(
                scan_id,
                status="COMPLETED",
                current_action="Complete",
                progress_percent=100,
                completed_at=datetime.now(timezone.utc).isoformat(),
                pdf_path=report.get("pdf_path"),
                json_path=report.get("json_path"),
            )
            
            # Extract JSON report from disk
            try:
                json_path = report.get("json_path")
                if json_path:
                    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
                    abs_json_path = os.path.join(project_root, json_path)
                    if os.path.exists(abs_json_path):
                        with open(abs_json_path, 'r', encoding='utf-8') as f:
                            json_report = json.load(f)
                            
                        if uid:
                            from apps.backend.models.history_store import save_completed_scan
                            save_completed_scan(
                                uid=uid,
                                scan_id=scan_id,
                                target=target,
                                status="COMPLETED",
                                started_at=get_scan(scan_id).get("date"),
                                completed_at=datetime.now(timezone.utc).isoformat(),
                                json_report=json_report,
                                iterations=result.get("iterations", 0),
                                completion_reason=result.get("reason", "generate_report called")
                            )
            except Exception as hist_err:
                logger.error(f"Failed to persist scan history: {hist_err}", exc_info=True)
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
        logger.error("Scan %s failed: %s", scan_id, e, exc_info=True)
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

    if is_domain_blocked(target):
        return jsonify({"error": f"Security Policy: Scanning '{target}' is restricted and not permitted."}), 403

    # Attempt to extract UID using the existing authentication flow
    uid = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        id_token = auth_header.split("Bearer ", 1)[1].strip()
        try:
            from firebase_admin import auth as firebase_auth
            decoded_token = firebase_auth.verify_id_token(id_token)
            uid = decoded_token.get("uid")
        except Exception as e:
            logging.warning(f"Error encountered: {e}")

    scan_id = create_scan(target)
    thread = threading.Thread(target=_run_scan_background, args=(scan_id, target, uid), daemon=True)
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
    if scan:
        if scan["status"] != "COMPLETED":
            return _error(f"Report not ready. Scan status is '{scan['status']}'.", 404)

        json_path = scan.get("json_path")
        if json_path:
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
            absolute_json_path = os.path.join(project_root, json_path)
            
            if os.path.exists(absolute_json_path):
                with open(absolute_json_path, "r", encoding="utf-8") as f:
                    report_data = json.load(f)
                return jsonify(report_data)

    # Fallback to Firestore for historical scans
    uid = _verify_token_inline()
    if not uid:
        return _error("Unauthorized. Historical scans require authentication.", 401)
    
    historical_scan = get_history_scan(uid, scan_id)
    if not historical_scan:
        return _error("The requested scan_id does not exist or does not belong to you.", 404)
        
    report_data = historical_scan.get("report_data")
    if not report_data:
        return _error("No report data found for this historical scan.", 404)
        
    return jsonify(report_data)


@scan_bp.route("/reports/<scan_id>/pdf", methods=["GET"])
def get_report_pdf(scan_id: str):
    """GET /api/v1/reports/<scan_id>/pdf -- downloads the completed scan's PDF report."""
    scan = get_scan(scan_id)
    if scan:
        if scan["status"] != "COMPLETED":
            return _error(f"Report not ready. Scan status is '{scan['status']}'.", 404)

        pdf_path = scan.get("pdf_path")
        if pdf_path:
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
            absolute_pdf_path = os.path.join(project_root, pdf_path)
            
            if os.path.exists(absolute_pdf_path):
                return send_file(absolute_pdf_path, mimetype="application/pdf", as_attachment=True)

    # Fallback to Firestore for historical scans
    uid = _verify_token_inline()
    if not uid:
        return _error("Unauthorized. Historical scans require authentication.", 401)
        
    historical_scan = get_history_scan(uid, scan_id)
    if not historical_scan:
        return _error("The requested scan_id does not exist or does not belong to you.", 404)
        
    report_data = historical_scan.get("report_data")
    if not report_data:
        return _error("No report data found for this historical scan.", 404)
        
    # Regenerate PDF from historical JSON
    from apps.backend.workers.report_worker import (
        _generate_pdf, _risk_label, _severity_for_cvss, security_score_from_cvss,
    )
    
    tmp_dir = tempfile.gettempdir()
    tmp_pdf_path = os.path.join(tmp_dir, f"sentinelscan_{scan_id}.pdf")
    
    try:
        maximum_cvss = report_data.get("maximum_cvss")
        try:
            maximum_cvss = float(maximum_cvss) if maximum_cvss is not None else None
        except (TypeError, ValueError):
            maximum_cvss = None

        security_score = int(
            report_data.get("security_score")
            if report_data.get("security_score") is not None
            else security_score_from_cvss(maximum_cvss)
        )
        maximum_cvss_severity = str(
            report_data.get("maximum_cvss_severity")
            or _severity_for_cvss(maximum_cvss)
        )
        risk_label = str(
            report_data.get("risk_label")
            or _risk_label(maximum_cvss)
        )

        _generate_pdf(
            pdf_path=tmp_pdf_path,
            target=report_data.get("target", "Unknown"),
            timestamp=report_data.get("scan_timestamp", ""),
            scan_id=scan_id,
            risk_summary=report_data.get("overall_risk_summary", {}),
            findings=report_data.get("findings", []),
            cvss_scores=report_data.get("cvss_scores", []),
            worker_coverage=report_data.get("worker_coverage", []),
            scan_duration=report_data.get("scan_duration", 0.0),
            security_score=security_score,
            maximum_cvss=maximum_cvss,
            maximum_cvss_severity=maximum_cvss_severity,
            risk_label=risk_label,
        )
        return send_file(tmp_pdf_path, mimetype="application/pdf", as_attachment=True)
    except Exception as e:
        logger.error(f"Failed to regenerate PDF for {scan_id}: {e}", exc_info=True)
        return _error("Failed to generate PDF from historical data.", 500)
