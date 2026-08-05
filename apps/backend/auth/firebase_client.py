"""
Firebase Admin SDK initialization.

Loads the service account credentials once at import time and exposes
the initialized Firestore client for use by routes and other modules.
"""
import os
import firebase_admin
from firebase_admin import credentials, firestore

_SERVICE_ACCOUNT_PATH = os.environ.get(
    "FIREBASE_SERVICE_ACCOUNT_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "secrets", "firebase-service-account.json"),
)

_cred = credentials.Certificate(_SERVICE_ACCOUNT_PATH)
firebase_app = firebase_admin.initialize_app(_cred)
db = firestore.client()


def get_db():
    """Returns the initialized Firestore client."""
    return db
