"""
Auth verification utilities.

Provides a Flask decorator that verifies a Firebase ID token sent by the
frontend in the Authorization header, and attaches the verified user's
identity to the request for use by route handlers.
"""
import functools
from typing import Callable

from flask import request, jsonify, g
try:
    from firebase_admin import auth as firebase_auth
except ImportError:
    firebase_auth = None

from apps.backend.auth.firebase_client import get_db


def require_auth(f: Callable) -> Callable:
    """
    Decorator for Flask routes that require a logged-in user.

    Expects an "Authorization: Bearer <firebase_id_token>" header.
    On success, attaches g.user = {"uid": ..., "email": ..., "name": ...}
    before calling the wrapped view. On failure, returns a 401 JSON error.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({
                "error": "Unauthorized",
                "message": "Missing or malformed Authorization header. Expected 'Bearer <token>'.",
                "code": 401,
            }), 401

        id_token = auth_header.split("Bearer ", 1)[1].strip()

        try:
            if firebase_auth:
                decoded_token = firebase_auth.verify_id_token(id_token)
            else:
                return jsonify({
                    "error": "Service Unavailable",
                    "message": "Authentication verification is disabled on the server.",
                    "code": 503,
                }), 503
        except Exception as e:
            if "default Firebase app does not exist" in str(e) or "FirebaseApp" in str(e):
                return jsonify({
                    "error": "Service Unavailable",
                    "message": "Authentication is disabled on the server.",
                    "code": 503,
                }), 503
            return jsonify({
                "error": "Unauthorized",
                "message": f"Invalid or expired authentication token: {e}",
                "code": 401,
            }), 401

        g.user = {
            "uid": decoded_token.get("uid"),
            "email": decoded_token.get("email"),
            "name": decoded_token.get("name", decoded_token.get("email", "Unknown")),
        }
        return f(*args, **kwargs)

    return wrapper


def require_developer(f: Callable) -> Callable:
    """
    Decorator for Flask routes restricted to allowlisted project developers.

    Must be applied *after* @require_auth (i.e. @require_auth above this
    decorator in the stack) so that g.user is already populated. Checks
    for a Firestore document at developers/{uid}; the document's content
    is not used, its existence is the allowlist entry.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        db = get_db()
        if not db:
            return jsonify({
                "error": "Service Unavailable",
                "message": "Developer allowlist is disabled without Firebase DB.",
                "code": 503,
            }), 503

        uid = g.user.get("uid")
        developer_doc = db.collection("developers").document(uid).get()
        if not developer_doc.exists:
            return jsonify({
                "error": "Forbidden",
                "message": "This account is not on the developer allowlist.",
                "code": 403,
            }), 403

        return f(*args, **kwargs)

    return wrapper
