"""Environment and settings. Values come from the process environment.

Local dev: optional `.env` in the working directory is merged into ``os.environ`` (without
overwriting keys already set) before ``Settings`` is built. Containers (Coolify, k8s, etc.)
typically inject variables only — no `.env` file required.
"""

import os
import ssl
from functools import lru_cache
from pathlib import Path

from typing import Annotated, Any

from pydantic import BeforeValidator, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.database_url import normalize_database_url, resolve_database_url
from app.core.gcp_credentials import parse_gcp_service_account_json


def _load_env_into_os() -> None:
    """Load .env file into os.environ so POSTGRES_* etc. are available before we inject DATABASE_URL."""
    env_path = Path(".env")
    if not env_path.is_file():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _inject_database_url_from_postgres() -> None:
    """
    Put a SQLAlchemy-asyncpg DATABASE_URL into os.environ before Settings() runs.

    Coolify often injects postgres://, quoted values, POSTGRES_URL, or POSTGRES_*
    parts instead of a clean postgresql+asyncpg URL. Empty/unparseable DATABASE_URL
    is treated as unset so POSTGRES_* can still win.
    """
    resolved = resolve_database_url(os.environ)
    if resolved:
        os.environ["DATABASE_URL"] = resolved


def _parse_database_url_env(v: Any) -> str:
    """Accept Coolify/Docker wrapping and fall back to POSTGRES_* if the URL is junk."""
    try:
        return normalize_database_url(v)
    except ValueError:
        fallback = resolve_database_url(os.environ)
        if fallback:
            return fallback
        raise


def asyncpg_connect_args_for_sslmode(sslmode: str) -> dict[str, Any]:
    """
    Map libpq-style sslmode to asyncpg's ssl= argument.
    Default app behavior matches sslmode=disable (no TLS).
    """
    mode = (sslmode or "disable").strip().lower()
    if mode in ("disable", "allow"):
        return {"ssl": False}
    if mode in ("prefer", "require"):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return {"ssl": ctx}
    if mode == "verify-ca":
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_REQUIRED
        return {"ssl": ctx}
    if mode == "verify-full":
        return {"ssl": ssl.create_default_context()}
    raise ValueError(
        "POSTGRES_SSLMODE must be one of: disable, allow, prefer, require, verify-ca, verify-full "
        f"(got {sslmode!r})"
    )


def _parse_gcp_service_account_env(v: Any) -> dict[str, Any]:
    """Coolify / Docker / local .env service-account JSON → dict."""
    return parse_gcp_service_account_json(v)


class Settings(BaseSettings):
    """Application settings. Required env vars must be set; missing ones raise validation errors."""

    model_config = SettingsConfigDict(
        extra="ignore",
    )

    # Database – DATABASE_URL or POSTGRES_* / Coolify POSTGRES_URL (normalized to postgresql+asyncpg)
    DATABASE_URL: Annotated[str, BeforeValidator(_parse_database_url_env)]
    # libpq-compatible; default matches previous behavior (no TLS). Use require for typical managed Postgres.
    POSTGRES_SSLMODE: str = "disable"

    # Redis
    REDIS_URL: str

    # Env var GCP_SERVICE_ACCOUNT_JSON (JSON string or pre-decoded object)
    # We keep the raw field typed as Any so pydantic-settings does not try to JSON-decode
    # it before our BeforeValidator runs (Coolify formatting can vary).
    GCP_SERVICE_ACCOUNT_JSON: Annotated[Any, BeforeValidator(_parse_gcp_service_account_env)]

    # JWT (RS256) – PEM content directly (use \n for newlines in .env)
    JWT_PRIVATE_KEY: str
    JWT_PUBLIC_KEY: str
    JWT_ISSUER: str
    JWT_EXPIRATION_MINUTES: int

    # Internal API (Product Plane)
    INTERNAL_API_KEY: str

    # Environment
    ENVIRONMENT: str
    
    # Frontend URLs
    ORG_CONSOLE_URL: str

    # Quota reservation hold TTL and in-process reaper
    QUOTA_HOLD_TTL_SECONDS: int = 3600
    QUOTA_REAPER_INTERVAL_SECONDS: int = 60
    QUOTA_REAPER_ENABLED: bool = True

    @field_validator("POSTGRES_SSLMODE")
    @classmethod
    def _validate_postgres_sslmode(cls, v: str) -> str:
        mode = (v or "disable").strip().lower()
        allowed = frozenset(
            ("disable", "allow", "prefer", "require", "verify-ca", "verify-full")
        )
        if mode not in allowed:
            raise ValueError(
                "POSTGRES_SSLMODE must be one of: "
                + ", ".join(sorted(allowed))
                + f" (got {v!r})"
            )
        return mode

    @computed_field
    @property
    def gcp_service_account(self) -> dict[str, Any]:
        """GCP service account dict for Firebase Admin and other GCP clients."""
        # _parse_gcp_service_account_env returns a dict.
        return self.GCP_SERVICE_ACCOUNT_JSON


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance. Loads optional `.env` then reads from the environment."""
    _load_env_into_os()
    _inject_database_url_from_postgres()
    return Settings()


settings = get_settings()
