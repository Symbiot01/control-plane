"""DATABASE_URL normalization for Coolify/Docker env injection."""

from sqlalchemy.engine.url import make_url

from app.core.database_url import (
    database_url_from_components,
    describe_database_url,
    normalize_database_url,
    resolve_database_url,
    strip_env_value,
    try_normalize_database_url,
)


def test_strip_wrapping_quotes_and_bom() -> None:
    assert strip_env_value('  "postgresql+asyncpg://u:p@h:5432/db"  ') == (
        "postgresql+asyncpg://u:p@h:5432/db"
    )
    assert strip_env_value("\ufeff'postgres://u:p@h:5432/db'") == "postgres://u:p@h:5432/db"


def test_normalize_converts_postgres_scheme() -> None:
    url = normalize_database_url("postgres://app:s3cret@db.internal:5432/control_plane")
    parsed = make_url(url)
    assert parsed.drivername == "postgresql+asyncpg"
    assert parsed.host == "db.internal"
    assert parsed.database == "control_plane"
    assert parsed.username == "app"
    assert parsed.password == "s3cret"


def test_normalize_preserves_percent_encoded_password() -> None:
    url = normalize_database_url("postgresql://app:p%40ss@db.internal:5432/control_plane")
    parsed = make_url(url)
    assert parsed.password == "p@ss"
    assert parsed.host == "db.internal"


def test_normalize_rejects_empty_and_http() -> None:
    for raw in ("", "null", "undefined", '""'):
        try:
            normalize_database_url(raw)
            raise AssertionError(f"expected empty rejection for {raw!r}")
        except ValueError as exc:
            assert "empty" in str(exc).lower() or "DATABASE_URL" in str(exc)
    try:
        normalize_database_url("https://control-plane-backend.example")
        raise AssertionError("expected http rejection")
    except ValueError as exc:
        assert "Postgres" in str(exc)
        assert "example.com" not in str(exc)


def test_describe_does_not_include_password() -> None:
    described = describe_database_url(
        "postgresql+asyncpg://app:super-secret@db.internal:5432/control_plane"
    )
    assert "super-secret" not in described
    assert "has_://=True" in described


def test_components_use_coolify_aliases_and_quote_password() -> None:
    url = database_url_from_components(
        {
            "POSTGRES_USERNAME": "app",
            "POSTGRES_PASSWORD": "p@ss:word",
            "POSTGRES_HOST": "10.0.0.8",
            "POSTGRES_DATABASE": "control_plane",
        }
    )
    assert url is not None
    parsed = make_url(url)
    assert parsed.drivername == "postgresql+asyncpg"
    assert parsed.username == "app"
    assert parsed.password == "p@ss:word"
    assert parsed.host == "10.0.0.8"
    assert parsed.database == "control_plane"


def test_resolve_falls_back_when_database_url_is_garbage() -> None:
    env = {
        "DATABASE_URL": "",
        "POSTGRES_URL": "not-a-url",
        "POSTGRES_USER": "app",
        "POSTGRES_PASSWORD": "secret",
        "POSTGRES_HOST": "postgres",
        "POSTGRES_DB": "control_plane",
    }
    url = resolve_database_url(env)
    assert url is not None
    parsed = make_url(url)
    assert parsed.host == "postgres"
    assert parsed.database == "control_plane"


def test_try_normalize_returns_none_for_invalid() -> None:
    assert try_normalize_database_url("-----BEGIN PRIVATE KEY-----") is None
    assert try_normalize_database_url("postgres://u:p@h:5432/db") is not None
