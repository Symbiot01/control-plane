"""Control JWT – issue (RS256), verify, and JWKS from settings."""

import base64
import time
from typing import Any

import jwt as pyjwt
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key

from app.core.config import settings


def _clean_pem_string(s: str, is_private: bool = True) -> bytes:
    import re
    header_match = re.search(r'-----BEGIN.*?-----', s)
    footer_match = re.search(r'-----END.*?-----', s)
    
    if not header_match or not footer_match:
        header_type = "PRIVATE" if is_private else "PUBLIC"
        raise ValueError(f"CRITICAL ERROR: Your {header_type} KEY is missing headers/footers. Starts with: {repr(s[:50])}")
        
    header = header_match.group(0)
    footer = footer_match.group(0)
    
    payload = s[header_match.end():footer_match.start()]
    
    # Strip literal \n (two chars) so 'n' doesn't stay behind as base64
    payload = payload.replace("\\n", "")
    payload = payload.replace("\\r", "")
    
    # Strip everything that is not valid base64
    clean_payload = re.sub(r'[^A-Za-z0-9+/=]', '', payload)
    
    # Rebuild PEM
    lines = [clean_payload[i:i+64] for i in range(0, len(clean_payload), 64)]
    payload_formatted = "\n".join(lines)
    
    perfect_pem = f"{header}\n{payload_formatted}\n{footer}"
    return perfect_pem.encode("utf-8")


def _private_key_bytes() -> bytes:
    """PEM private key as bytes."""
    return _clean_pem_string(settings.JWT_PRIVATE_KEY, is_private=True)


def _public_key_bytes() -> bytes:
    """PEM public key as bytes."""
    return _clean_pem_string(settings.JWT_PUBLIC_KEY, is_private=False)


def _int_to_b64url(n: int) -> str:
    """Encode positive int as base64url (JWK n/e)."""
    by = n.to_bytes((n.bit_length() + 7) // 8 or 1, byteorder="big")
    return base64.urlsafe_b64encode(by).rstrip(b"=").decode("ascii")


def issue_control_jwt(
    sub: str,
    org_id: str | None = None,
    level_of_access: str = "guest",
    *,
    issuer: str | None = None,
    expiration_minutes: int | None = None,
) -> str:
    """
    Issue a Control JWT (RS256).
    sub: member_id (UUID string), org_id: active org (or None), level_of_access: "super_admin", "owner", "member", or "guest".
    """
    issuer = issuer or settings.JWT_ISSUER
    exp_min = expiration_minutes if expiration_minutes is not None else settings.JWT_EXPIRATION_MINUTES
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": sub,
        "iss": issuer,
        "iat": now,
        "exp": now + exp_min * 60,
    }
    if org_id is not None:
        payload["org_id"] = org_id
    payload["level_of_access"] = level_of_access

    key = load_pem_private_key(_private_key_bytes(), password=None)
    return pyjwt.encode(payload, key, algorithm="RS256")


def verify_control_jwt(token: str) -> dict[str, Any]:
    """
    Verify Control JWT and return payload.
    Raises pyjwt.InvalidTokenError on failure.
    """
    key = load_pem_public_key(_public_key_bytes())
    return pyjwt.decode(
        token,
        key,
        algorithms=["RS256"],
        issuer=settings.JWT_ISSUER,
        options={"require": ["sub", "iat", "exp", "iss"]},
    )


def build_jwks() -> dict[str, Any]:
    """Build JWKS document (keys array) from settings.JWT_PUBLIC_KEY."""
    key = load_pem_public_key(_public_key_bytes())
    numbers = key.public_numbers()
    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "n": _int_to_b64url(numbers.n),
                "e": _int_to_b64url(numbers.e),
                "kid": "control-plane-1",
            }
        ]
    }
