"""
Firebase Admin SDK initialization.

Loads the service account credentials once at import time and exposes
the initialized Firestore client for use by routes and other modules.
"""
import os
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    _FIREBASE_INSTALLED = True
except ImportError:
    _FIREBASE_INSTALLED = False

_SERVICE_ACCOUNT_PATH = os.environ.get(
    "FIREBASE_SERVICE_ACCOUNT_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "secrets", "firebase-service-account.json"),
)

try:
    if not _FIREBASE_INSTALLED:
        raise Exception("firebase_admin package not installed")
    _cred = credentials.Certificate(_SERVICE_ACCOUNT_PATH)
    firebase_app = firebase_admin.initialize_app(_cred)
    db = firestore.client()
except Exception as e:
    import logging
    logging.getLogger(__name__).warning(f"Firebase not configured or failed to initialize: {e}")
    db = None


def get_db():
    """Returns the initialized Firestore client."""
    return db
