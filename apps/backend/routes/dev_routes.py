"""
Developer-only routes for the team secrets bootstrap system.

Lets an allowlisted teammate fetch the shared dev environment secrets
(GEMINI_API_KEY, FLASK_SECRET_KEY, etc.) from Firestore instead of having
them manually copied around. See scripts/bootstrap_env.py for the client
side of this flow.
"""
import logging

from flask import Blueprint, jsonify

from apps.backend.auth.auth_utils import require_auth, require_developer
from apps.backend.auth.firebase_client import get_db

from apps.backend.extensions import limiter

logger = logging.getLogger(__name__)

dev_bp = Blueprint("dev_routes", __name__, url_prefix="/api/v1/dev")


@dev_bp.route("/bootstrap-secrets", methods=["GET"])
@limiter.limit("5 per minute")
@require_auth
@require_developer
def bootstrap_secrets():
    """GET /api/v1/dev/bootstrap-secrets -- returns the shared dev secrets doc."""
    db = get_db()
    if not db:
        return jsonify({
            "error": "Service Unavailable",
            "message": "Secrets bootstrap is disabled without Firebase DB.",
            "code": 503,
        }), 503

    secrets_doc = db.collection("config").document("secrets").get()
    if not secrets_doc.exists:
        return jsonify({
            "error": "Not Found",
            "message": "config/secrets has not been seeded yet. Run scripts/admin_seed_secrets.py.",
            "code": 404,
        }), 404

    return jsonify(secrets_doc.to_dict())
