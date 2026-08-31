"""Shared privacy assertions for CLI output tests."""

from __future__ import annotations

import json

from ....core.redaction.rules import CLI_PROFILE_ID_PLACEHOLDER
from ....tests.cli_envelope import unwrap_schema_envelope


def assert_public_profile_id_redacted(output: str, raw_profile_id: str) -> None:
    """Assert a public output names the profile-id placeholder, never the raw id."""
    assert CLI_PROFILE_ID_PLACEHOLDER in output
    assert raw_profile_id not in output


def assert_public_profile_id_not_leaked(output: str, raw_profile_id: str) -> None:
    """Assert a public output does not contain the raw profile id."""
    assert raw_profile_id not in output


def assert_public_profile_payload_redacted(output: str, raw_profile_id: str) -> dict[str, object]:
    """Return a JSON envelope payload after asserting profile-id redaction."""
    raw_payload = unwrap_schema_envelope(output)
    payload: dict[str, object] = {}
    for key, value in raw_payload.items():
        if not isinstance(key, str):
            raise TypeError("CLI payload keys must be strings")
        payload[key] = value
    assert payload["profile_id"] == CLI_PROFILE_ID_PLACEHOLDER
    assert raw_profile_id not in json.dumps(payload, sort_keys=True)
    return payload
