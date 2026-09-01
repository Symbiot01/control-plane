"""Parse GCP service-account JSON from Coolify/Docker/.env without leaking secrets."""

from __future__ import annotations

import ast
import json
from typing import Any

_REQUIRED_KEYS = ("type", "project_id", "private_key", "client_email")


def _extract_json_object(s: str) -> str:
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        return s[start : end + 1]
    return s.strip()


def _escape_control_chars_in_json_strings(s: str) -> str:
    """Turn raw newlines inside JSON strings into \\n (Coolify/PEM paste)."""
    out: list[str] = []
    in_string = False
    escape = False
    for ch in s:
        if in_string:
            if escape:
                out.append(ch)
                escape = False
            elif ch == "\\":
                out.append(ch)
                escape = True
            elif ch == '"':
                out.append(ch)
                in_string = False
            elif ch == "\n":
                out.append("\\n")
            elif ch == "\r":
                continue
            elif ch == "\t":
                out.append("\\t")
            else:
                out.append(ch)
        else:
            if ch == '"':
                in_string = True
            out.append(ch)
    return "".join(out)


def _try_load_object(s: str) -> dict[str, Any] | None:
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        try:
            data = ast.literal_eval(s)
        except (ValueError, SyntaxError):
            return None
    return data if isinstance(data, dict) else None


def parse_gcp_service_account_json(v: Any) -> dict[str, Any]:
    """
    Normalize Coolify/Docker service-account env values to a dict.

    Try json.loads first. Do not globally unescape \n before parsing — that
    turns a valid private_key escape into a raw newline and breaks JSON.
    """
    if isinstance(v, dict):
        data = v
    elif isinstance(v, str):
        s = v.strip()
        if not s:
            raise ValueError(
                "GCP_SERVICE_ACCOUNT_JSON is empty; set the full service account JSON."
            )
        s = _extract_json_object(s)
        candidates = [
            s,
            _escape_control_chars_in_json_strings(s),
            s.replace('\\"', '"').replace("\\'", "'"),
        ]
        data = None
        for candidate in candidates:
            data = _try_load_object(candidate)
            if data is not None:
                break
            repaired = _escape_control_chars_in_json_strings(candidate)
            if repaired != candidate:
                data = _try_load_object(repaired)
                if data is not None:
                    break
        if data is None:
            raise ValueError(
                "GCP_SERVICE_ACCOUNT_JSON must be valid JSON (GCP service account object)."
            )
    else:
        raise ValueError(
            "GCP_SERVICE_ACCOUNT_JSON must be a JSON string or object "
            f"(got {type(v).__name__})."
        )

    if not isinstance(data, dict):
        raise ValueError("GCP_SERVICE_ACCOUNT_JSON must be a JSON object.")
    for key in _REQUIRED_KEYS:
        if key not in data:
            raise ValueError(
                f"GCP_SERVICE_ACCOUNT_JSON must contain '{key}' (GCP service account format)."
            )
            
    if "private_key" in data and isinstance(data["private_key"], str):
        data["private_key"] = data["private_key"].replace("\\n", "\n")
        
    return data
