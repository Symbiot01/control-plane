"""GCP service-account JSON parsing for Coolify-escaped env values."""

import json

from app.core.gcp_credentials import parse_gcp_service_account_json

_MINIMAL = {
    "type": "service_account",
    "project_id": "control-plane-test",
    "private_key": "-----BEGIN PRIVATE KEY-----\\nABC\\n-----END PRIVATE KEY-----\\n",
    "client_email": "sa@test.iam.gserviceaccount.com",
}


def test_valid_json_dumps_with_escaped_newlines() -> None:
    raw = json.dumps(
        {
            "type": "service_account",
            "project_id": "p",
            "private_key": "-----BEGIN PRIVATE KEY-----\nABC\n-----END PRIVATE KEY-----\n",
            "client_email": "sa@test.iam.gserviceaccount.com",
        }
    )
    data = parse_gcp_service_account_json(raw)
    assert data["project_id"] == "p"
    assert "\n" in data["private_key"]
    assert "BEGIN PRIVATE KEY" in data["private_key"]


def test_coolify_real_newlines_inside_private_key() -> None:
    raw = (
        '{"type": "service_account", "project_id": "p", '
        '"private_key": "-----BEGIN PRIVATE KEY-----\nABC\n-----END PRIVATE KEY-----\n", '
        '"client_email": "sa@test.iam.gserviceaccount.com"}'
    )
    data = parse_gcp_service_account_json(raw)
    assert data["project_id"] == "p"
    assert "ABC" in data["private_key"]


def test_already_decoded_dict() -> None:
    data = parse_gcp_service_account_json(dict(_MINIMAL))
    assert data["type"] == "service_account"


def test_wrapped_quotes_and_braces() -> None:
    raw = json.dumps(
        {
            "type": "service_account",
            "project_id": "p",
            "private_key": "k",
            "client_email": "sa@test.iam.gserviceaccount.com",
        }
    )
    data = parse_gcp_service_account_json(f"prefix {raw} suffix")
    assert data["project_id"] == "p"


def test_rejects_empty() -> None:
    try:
        parse_gcp_service_account_json("   ")
        raise AssertionError("expected empty rejection")
    except ValueError as exc:
        assert "empty" in str(exc).lower()
