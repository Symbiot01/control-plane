"""Auth-related Pydantic schemas."""

from pydantic import BaseModel, Field


class AuthExchangeRequest(BaseModel):
    """Request body for POST /auth/exchange."""

    id_token: str = Field(..., description="Firebase ID token")
    display_name: str | None = Field(default=None, description="Optional display name if missing in token")
    # Optional: org_id to set as active org in JWT (must be member)


class AuthExchangeResponse(BaseModel):
    """Response from POST /auth/exchange."""

    access_token: str = Field(..., description="Control JWT")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_in: int = Field(..., description="Seconds until expiry")
    has_pending_invites: bool = Field(default=False, description="True if user has pending invites")


class TokenPayload(BaseModel):
    """Control JWT payload (for dependency return type)."""

    sub: str  # member_id (UUID string)
    org_id: str | None  # active organization (or None)
    roles: list[str] = Field(default_factory=list)
    iss: str = ""
    iat: int = 0
    exp: int = 0
