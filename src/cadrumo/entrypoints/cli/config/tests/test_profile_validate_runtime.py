"""Profile validation reports only issues from the authenticated runtime view."""

from __future__ import annotations

import json
import sys

import pytest
from click.testing import Result

from ...tests.cli_runner import invoke_cached_cli
from .isolated_storage_fixture import CREDENTIAL_INPUT, profile_cli
from .isolated_storage_fixture import live_cli_profile as live_cli_profile
from .isolated_storage_fixture import native_cli_profile_view as native_cli_profile_view

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile runtime"),
]


def _validate(*, named: bool, json_output: bool, language: str | None = None) -> Result:
    args = ["--profile", "Editor", "--profile-secrets-stdin"]
    if json_output:
        args[:0] = ["--format", "json"]
    args.extend(("config", "profile", "validate"))
    if named:
        args.append("Editor")
    if language is not None:
        args.extend(("--language", language))
    return invoke_cached_cli(args, input=json.dumps({"profile_passphrase": CREDENTIAL_INPUT}))


def test_validate_emits_only_canonical_issues_and_keeps_blocking_exit_code(native_cli_profile_view: None) -> None:
    """The report does not release facts and still signals an incomplete profile."""
    result = _validate(named=False, json_output=True)
    assert result.exit_code == 2, result.output
    document = json.loads(result.stdout)
    assert document["command"] == "config.profile.validate"
    payload = document["result"]
    assert payload["display_name"] == "Editor"
    assert payload["setup_state"] == "incomplete"
    assert payload["valid"] is False
    assert payload["issues"]
    assert any(item["severity"] == "error" for item in payload["issues"])
    assert "facts" not in payload
    assert "facts" not in document

    text = _validate(named=True, json_output=False)
    assert text.exit_code == 2, text.output
    assert "readiness\tblocked" in text.stdout
    assert f"profile_id\t{payload['profile_id']}" in text.stdout
    assert "display_name\tEditor" in text.stdout


def test_validate_named_target_uses_profile_preference_and_explicit_language(native_cli_profile_view: None) -> None:
    """The selected profile hint chooses the default; explicit language preserves issue identity."""
    changed = profile_cli("edit", "--quiet", "--output-language", "en")
    assert changed.exit_code == 0, changed.output
    preferred = _validate(named=True, json_output=True)
    english = _validate(named=True, json_output=True, language="en")
    spanish = _validate(named=True, json_output=True, language="es")
    assert preferred.exit_code == english.exit_code == spanish.exit_code == 2
    preferred_result = json.loads(preferred.stdout)["result"]
    en_result = json.loads(english.stdout)["result"]
    es_result = json.loads(spanish.stdout)["result"]
    assert preferred_result["issues"] == en_result["issues"]
    assert en_result["profile_id"] == es_result["profile_id"]
    assert [(item["severity"], item["code"], item["path"]) for item in en_result["issues"]] == [
        (item["severity"], item["code"], item["path"]) for item in es_result["issues"]
    ]
