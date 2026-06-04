"""Firebase Admin – initialize and verify ID tokens."""

from typing import Any

from firebase_admin import auth, credentials, get_app, initialize_app

from app.core.config import settings


def ensure_firebase_initialized() -> None:
    """Initialize Firebase App once from settings.gcp_service_account."""
    try:
        get_app()
    except ValueError:
        cred = credentials.Certificate(settings.gcp_service_account)
        initialize_app(cred)


def verify_id_token(id_token: str) -> dict[str, Any]:
    """
    Verify Firebase ID token and return decoded claims.
    Raises firebase_admin.auth.InvalidIdTokenError or ExpiredIdTokenError on failure.
    """
    ensure_firebase_initialized()
    decoded = auth.verify_id_token(id_token)
    return decoded


def delete_firebase_user(uid: str) -> None:
    """
    Delete a user from Firebase Auth by their UID.
    """
    ensure_firebase_initialized()
    auth.delete_user(uid)
