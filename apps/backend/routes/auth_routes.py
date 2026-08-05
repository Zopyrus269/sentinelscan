"""
Auth routes -- session verification and user profile management.

The frontend calls POST /api/v1/auth/session right after a successful
Firebase Google Sign-In, sending the ID token. This verifies the token,
creates the user's Firestore profile on first login (or fetches it if
it already exists), and returns the profile to the frontend.
"""
from datetime import datetime, timezone

from flask import Blueprint, jsonify, g, request

from apps.backend.auth.auth_utils import require_auth
from apps.backend.auth.firebase_client import get_db

auth_bp = Blueprint("auth_routes", __name__, url_prefix="/api/v1/auth")


@auth_bp.route("/session", methods=["POST"])
@require_auth
def create_session():
    """
    Verifies the caller's Firebase ID token (via @require_auth) and
    ensures a Firestore user profile exists, creating a default one
    (light theme) on first login.
    """
    db = get_db()
    user_ref = db.collection("users").document(g.user["uid"])
    user_doc = user_ref.get()

    if not user_doc.exists:
        profile = {
            "uid": g.user["uid"],
            "email": g.user["email"],
            "name": g.user["name"],
            "theme": "light",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_login_ip": request.remote_addr,
            "last_login_at": datetime.now(timezone.utc).isoformat(),
        }
        user_ref.set(profile)
    else:
        profile = user_doc.to_dict()
        user_ref.update({
            "last_login_ip": request.remote_addr,
            "last_login_at": datetime.now(timezone.utc).isoformat(),
        })
        profile["last_login_ip"] = request.remote_addr

    return jsonify(profile)


@auth_bp.route("/me", methods=["GET"])
@require_auth
def get_current_user():
    """Returns the logged-in user's Firestore profile."""
    db = get_db()
    user_doc = db.collection("users").document(g.user["uid"]).get()
    if not user_doc.exists:
        return jsonify({
            "error": "Not Found",
            "message": "User profile does not exist yet. Call POST /api/v1/auth/session first.",
            "code": 404,
        }), 404
    return jsonify(user_doc.to_dict())


@auth_bp.route("/theme", methods=["PUT"])
@require_auth
def update_theme():
    """Updates the logged-in user's theme preference (light/dark)."""
    data = request.get_json(silent=True) or {}
    theme = data.get("theme")
    if theme not in ("light", "dark"):
        return jsonify({
            "error": "Bad Request",
            "message": "Request body must include 'theme' as either 'light' or 'dark'.",
            "code": 400,
        }), 400

    db = get_db()
    db.collection("users").document(g.user["uid"]).update({"theme": theme})
    return jsonify({"theme": theme})
