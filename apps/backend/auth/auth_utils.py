"""
Auth verification utilities.

Provides a Flask decorator that verifies a Firebase ID token sent by the
frontend in the Authorization header, and attaches the verified user's
identity to the request for use by route handlers.
"""
import functools
from typing import Callable

from flask import request, jsonify, g
from firebase_admin import auth as firebase_auth


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
            decoded_token = firebase_auth.verify_id_token(id_token)
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
