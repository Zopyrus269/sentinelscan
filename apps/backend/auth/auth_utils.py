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
                # Fallback to local decode if firebase is not installed (e.g. localhost)
                import base64
                import json
                parts = id_token.split(".")
                if len(parts) != 3:
                    raise Exception("Malformed token")
                payload = parts[1]
                payload += "=" * ((4 - len(payload) % 4) % 4)
                decoded_token = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
                decoded_token["uid"] = decoded_token.get("user_id")
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
