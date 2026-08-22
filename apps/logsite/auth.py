"""
Developer authentication wrapper for the SentinelScan Log Site.

Re-exports the require_auth and require_developer decorators from
apps.backend.auth.auth_utils to enforce Firebase ID token verification and
Firestore developer allowlist gating.
"""
from apps.backend.auth.auth_utils import require_auth, require_developer

__all__ = ["require_auth", "require_developer"]
