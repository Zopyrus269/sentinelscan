"""
Firestore storage module for completed scans.

Provides reusable functions to save and retrieve scan history for authenticated users.
This module is independent of Flask routes, UI logic, and scan execution logic.
"""

import logging
from typing import Any, Dict, List, Optional
from firebase_admin import firestore

from apps.backend.auth.firebase_client import get_db

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
    """
    Stores a completed scan inside Firestore under the authenticated user's UID.
    
    Args:
        uid: The Firebase UID of the user.
        scan_id: The unique identifier of the scan.
        target: The domain or IP that was scanned.
        status: The final status of the scan (e.g., COMPLETED, FAILED).
        started_at: ISO-8601 string of when the scan started.
        completed_at: ISO-8601 string of when the scan completed.
        json_report: The complete JSON report data as a dictionary.
        iterations: The number of AI iterations the scan took.
        completion_reason: The reason the scan completed.
        
    Returns:
        bool: True if successfully saved, False otherwise.
    """
    try:
        db = get_db()
        if not db:
            return False
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
    """
    Returns all scans for the specified user, newest first.
    Only lightweight metadata is returned (the full JSON report is excluded).
    
    Args:
        uid: The Firebase UID of the user.
        
    Returns:
        A list of dictionaries representing the scan history metadata.
    """
    try:
        db = get_db()
        if not db:
            return []
        scans_ref = db.collection("users").document(uid).collection("scans")
        
        # Use .select() to only fetch metadata fields, avoiding the memory overhead of the full JSON payload
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
        return []


def get_scan(uid: str, scan_id: str) -> Optional[Dict[str, Any]]:
    """
    Returns the complete Firestore document for one scan, including the JSON report.
    
    Args:
        uid: The Firebase UID of the user.
        scan_id: The unique identifier of the scan.
        
    Returns:
        The scan document as a dictionary, or None if it doesn't exist.
    """
    try:
        db = get_db()
        if not db:
            return None
        doc_ref = db.collection("users").document(uid).collection("scans").document(scan_id)
        doc = doc_ref.get()
        
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        logger.error("Failed to get scan %s for user %s: %s", scan_id, uid, e, exc_info=True)
        return None


def scan_exists(uid: str, scan_id: str) -> bool:
    """
    Checks whether a specific scan exists for the user.
    
    Args:
        uid: The Firebase UID of the user.
        scan_id: The unique identifier of the scan.
        
    Returns:
        bool: True if the scan exists, False otherwise.
    """
    try:
        db = get_db()
        if not db:
            return False
        doc_ref = db.collection("users").document(uid).collection("scans").document(scan_id)
        # Empty field mask fetches minimum data just to check existence
        doc = doc_ref.get(field_paths=[])
        return doc.exists
    except Exception as e:
        logger.error("Failed to check if scan %s exists for user %s: %s", scan_id, uid, e, exc_info=True)
        return False
