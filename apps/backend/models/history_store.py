"""
Firestore storage module for completed scans.

Provides reusable functions to save and retrieve scan history for authenticated users.
This module has been updated with a local in-memory fallback for local development.
"""

import logging
from typing import Any, Dict, List, Optional
import os
import json

try:
    from firebase_admin import firestore
except ImportError:
    firestore = None

from apps.backend.auth.firebase_client import get_db
from apps.backend.models.scan_store import list_scans, get_scan as get_memory_scan

logger = logging.getLogger(__name__)


def save_completed_scan(
    uid: str,
    scan_id: str,
    target: str,
    status: str,
    started_at: str,
    completed_at: str,
    json_report: Dict[str, Any],
    iterations: int,
    completion_reason: str,
) -> bool:
    db = get_db()
    if not db:
        # Local dev fallback: pretend it saved successfully
        # The history will be read from scan_store.py in-memory state
        return True
    try:
        doc_ref = db.collection("users").document(uid).collection("scans").document(scan_id)
        
        data = {
            "scan_id": scan_id,
            "target": target,
            "status": status,
            "timestamps": {
                "started_at": started_at,
                "completed_at": completed_at,
            },
            "report_data": json_report,
            "metadata": {
                "iterations": iterations,
                "completion_reason": completion_reason,
            }
        }
        
        doc_ref.set(data)
        return True
    except Exception as e:
        logger.error("Failed to save completed scan %s for user %s: %s", scan_id, uid, e, exc_info=True)
        return False


def get_user_scan_history(uid: str) -> List[Dict[str, Any]]:
    db = get_db()
    if db:
        try:
            scans_ref = db.collection("users").document(uid).collection("scans")
            query = scans_ref.select(
                ["scan_id", "target", "status", "timestamps", "metadata"]
            ).order_by(
                "timestamps.started_at", direction=firestore.Query.DESCENDING
            )
            
            results = []
            for doc in query.stream():
                data = doc.to_dict()
                if data:
                    results.append(data)
                
            return results
        except Exception as e:
            logger.error("Failed to get scan history for user %s: %s", uid, e, exc_info=True)
    
    # LOCAL FALLBACK
    results = []
    for s in list_scans():
        if s["status"] != "COMPLETED":
            continue
        mem_s = get_memory_scan(s["scan_id"])
        if not mem_s:
            continue
        
        results.append({
            "scan_id": mem_s["scan_id"],
            "target": mem_s["target"],
            "status": mem_s["status"],
            "timestamps": {
                "started_at": mem_s.get("date"),
                "completed_at": mem_s.get("date"),
            },
            "metadata": {
                "iterations": 0,
                "completion_reason": "Local fallback",
            }
        })
    results.sort(key=lambda x: x.get("timestamps", {}).get("started_at", ""), reverse=True)
    return results


def get_scan(uid: str, scan_id: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    if db:
        try:
            doc_ref = db.collection("users").document(uid).collection("scans").document(scan_id)
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict()
        except Exception as e:
            logger.error("Failed to get scan %s for user %s: %s", scan_id, uid, e, exc_info=True)

    # LOCAL FALLBACK
    mem_s = get_memory_scan(scan_id)
    if not mem_s:
        return None
        
    json_path = mem_s.get("json_path")
    report_data = {}
    if json_path:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        abs_json_path = os.path.join(project_root, json_path)
        if os.path.exists(abs_json_path):
            with open(abs_json_path, 'r', encoding='utf-8') as f:
                report_data = json.load(f)
                
    return {
        "scan_id": mem_s["scan_id"],
        "target": mem_s["target"],
        "status": mem_s["status"],
        "timestamps": {
            "started_at": mem_s.get("date"),
            "completed_at": mem_s.get("date"),
        },
        "report_data": report_data,
        "metadata": {
            "iterations": 0,
            "completion_reason": "Local fallback",
        }
    }


def scan_exists(uid: str, scan_id: str) -> bool:
    db = get_db()
    if db:
        try:
            doc_ref = db.collection("users").document(uid).collection("scans").document(scan_id)
            doc = doc_ref.get(field_paths=[])
            return doc.exists
        except Exception as e:
            logger.error("Failed to check if scan %s exists for user %s: %s", scan_id, uid, e, exc_info=True)
            return False
            
    # LOCAL FALLBACK
    return get_memory_scan(scan_id) is not None
