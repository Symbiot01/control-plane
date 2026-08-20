"""Normalize Postgres URLs from Coolify/Docker/.env into SQLAlchemy asyncpg URLs.

Never include credentials in error messages. Callers should log describe_database_url().
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.engine.url import URL, make_url
from sqlalchemy.exc import ArgumentError

_ASYNC_DRIVER = "postgresql+asyncpg"
_SYNC_DRIVERS = frozenset(
    {
        "postgres",
        "postgresql",
        "postgresql+psycopg",
        "postgresql+psycopg2",
        "postgresql+psycopg3",
    }
)

_URL_KEYS = ("DATABASE_URL", "POSTGRES_URL", "POSTGRESQL_URL")
_USER_KEYS = (
    "POSTGRES_USER",
    "POSTGRES_USERNAME",
    "POSTGRESQL_USER",
    "POSTGRESQL_USERNAME",
)
_PASSWORD_KEYS = ("POSTGRES_PASSWORD", "POSTGRESQL_PASSWORD")
_DB_KEYS = (
    "POSTGRES_DB",
    "POSTGRES_DATABASE",
    "POSTGRESQL_DB",
    "POSTGRESQL_DATABASE",
)
_HOST_KEYS = ("POSTGRES_HOST", "POSTGRESQL_HOST")
_PORT_KEYS = ("POSTGRES_PORT", "POSTGRESQL_PORT")
_EMPTY_TOKENS = frozenset({"", "none", "null", "undefined", "nil"})

_MISSING_URL_HELP = (
    "Set DATABASE_URL to a Postgres URL "
    "(postgresql+asyncpg://user:pass@host:5432/dbname or postgres://...) "
    "or set POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, and POSTGRES_DB. "
    "In Coolify, mark these as Runtime only (disable Available at Buildtime) "
    "and do not wrap the URL in extra quotes."
)


def strip_env_value(value: Any) -> str:
    """Strip BOM, whitespace, and Coolify/Docker wrapping quotes from an env value."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    if not isinstance(value, str):
        value = str(value)
    s = value.replace("\ufeff", "").strip()
    for _ in range(3):
        if len(s) >= 2 and s[0] == s[-1] and s[0] in {'"', "'"}:
            s = s[1:-1].strip()
            continue
        break
    return s.replace(r":\/\/", "://").strip()


def describe_database_url(raw: Any) -> str:
    """Describe a URL for errors without leaking credentials."""
    s = strip_env_value(raw)
    if not s:
        return "empty"
    if s.lower() in _EMPTY_TOKENS:
        return f"placeholder {s!r}"
    has_scheme = "://" in s
    prefix = s.split("://", 1)[0] if has_scheme else s[:16]
    return f"length={len(s)} scheme_prefix={prefix!r} has_://={has_scheme}"


def _first_env(env: Mapping[str, str], keys: tuple[str, ...]) -> str:
    for key in keys:
        if key not in env:
            continue
        value = strip_env_value(env.get(key))
        if value and value.lower() not in _EMPTY_TOKENS:
            return value
    return ""


def database_url_from_components(env: Mapping[str, str]) -> str | None:
    """Build postgresql+asyncpg://... from POSTGRES_* / Coolify aliases."""
    user = _first_env(env, _USER_KEYS)
    password = _first_env(env, _PASSWORD_KEYS)
    db = _first_env(env, _DB_KEYS)
    if not user or not password or not db:
        return None
    host = _first_env(env, _HOST_KEYS) or "localhost"
    port_raw = _first_env(env, _PORT_KEYS) or "5432"
    try:
        port = int(port_raw)
    except ValueError as e:
        raise ValueError("POSTGRES_PORT must be an integer.") from e
    return URL.create(
        drivername=_ASYNC_DRIVER,
        username=user,
        password=password,
        host=host,
        port=port,
        database=db.lstrip("/"),
    ).render_as_string(hide_password=False)


def normalize_database_url(raw: Any) -> str:
    """Return a postgresql+asyncpg URL, or raise ValueError without echoing secrets."""
    s = strip_env_value(raw)
    if not s or s.lower() in _EMPTY_TOKENS:
        raise ValueError(f"DATABASE_URL is empty. {_MISSING_URL_HELP}")
    try:
        url = make_url(s)
    except ArgumentError as e:
        raise ValueError(
            f"DATABASE_URL is not a valid SQLAlchemy URL ({describe_database_url(s)}). "
            f"{_MISSING_URL_HELP}"
        ) from e
    driver = url.drivername
    if driver in _SYNC_DRIVERS:
        url = url.set(drivername=_ASYNC_DRIVER)
    elif driver != _ASYNC_DRIVER:
        raise ValueError(
            "DATABASE_URL must be a Postgres URL "
            f"(got driver {driver!r}). Use postgresql+asyncpg:// or postgres://."
        )
    if not url.host:
        raise ValueError("DATABASE_URL is missing a host.")
    if not url.database:
        raise ValueError("DATABASE_URL is missing a database name.")
    return url.render_as_string(hide_password=False)


def try_normalize_database_url(raw: Any) -> str | None:
    try:
        return normalize_database_url(raw)
    except ValueError:
        return None


def resolve_database_url(env: Mapping[str, str]) -> str | None:
    """Prefer a usable URL env var, otherwise build from POSTGRES_* parts."""
    for key in _URL_KEYS:
        found = try_normalize_database_url(env.get(key, ""))
        if found:
            return found
    return database_url_from_components(env)
