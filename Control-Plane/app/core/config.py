"""Environment and settings. Values come from the process environment.

Local dev: optional `.env` in the working directory is merged into ``os.environ`` (without
overwriting keys already set) before ``Settings`` is built. Containers (Coolify, k8s, etc.)
typically inject variables only — no `.env` file required.
"""

import ast
import json
import os
import ssl
from functools import lru_cache
from pathlib import Path

from typing import Annotated, Any

from pydantic import BeforeValidator, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    If DATABASE_URL is not set in the environment but POSTGRES_* are, set
    DATABASE_URL so Settings() reads it. Run after _load_env_into_os().
    """
    if os.environ.get("DATABASE_URL"):
        return
    user = os.environ.get("POSTGRES_USER")
    password = os.environ.get("POSTGRES_PASSWORD")
    db = os.environ.get("POSTGRES_DB")
    if not user or not password or not db:
        return
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    os.environ["DATABASE_URL"] = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"


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
    """
    Coolify / pydantic-settings often pass GCP JSON as a dict (decoded from env).
    Local .env uses one JSON string. Normalize to a dict and validate required keys.
    """
    if isinstance(v, dict):
        data = v
    elif isinstance(v, str):
        s = v.strip()
        if not s:
            raise ValueError(
                "GCP_SERVICE_ACCOUNT_JSON is empty; set the full service account JSON."
            )
        
        # Aggressively strip surrounding quotes injected by env loaders like Coolify
        if s.startswith("'") and s.endswith("'"):
            s = s[1:-1]
        elif s.startswith('"') and s.endswith('"'):
            s = s[1:-1]
        
        # Unescape any escaped quotes
        s = s.replace('\\"', '"').replace("\\'", "'")
        
        try:
            data = json.loads(s)
        except json.JSONDecodeError:
            # Coolify / some env loaders may store JSON-like dicts with single quotes.
            # As a fallback, parse them as a Python literal.
            try:
                data = ast.literal_eval(s)
            except (ValueError, SyntaxError) as e:
                raise ValueError(
                    "GCP_SERVICE_ACCOUNT_JSON must be valid JSON (GCP service account object)."
                ) from e
    else:
        raise ValueError(
            "GCP_SERVICE_ACCOUNT_JSON must be a JSON string or object "
            f"(got {type(v).__name__})."
        )
    if not isinstance(data, dict):
        raise ValueError("GCP_SERVICE_ACCOUNT_JSON must be a JSON object.")
    for key in ("type", "project_id", "private_key", "client_email"):
        if key not in data:
            raise ValueError(
                f"GCP_SERVICE_ACCOUNT_JSON must contain '{key}' (GCP service account format)."
            )
    return data


class Settings(BaseSettings):
    """Application settings. Required env vars must be set; missing ones raise validation errors."""

    model_config = SettingsConfigDict(
        extra="ignore",
    )

    # Database – set DATABASE_URL in .env or use POSTGRES_* (we inject DATABASE_URL before Settings() if needed)
    DATABASE_URL: str
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
