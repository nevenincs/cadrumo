"""Profile-create choice help must match the values refused at runtime."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ....tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _isolated_env(tmp_path: Path) -> dict[str, str | None]:
    return {
        "AEAT_LOCAL_STORAGE_ROOT": str(tmp_path / "aeat-local"),
        "AEAT_SECRET_PASSPHRASE": "profile-choice-help-passphrase",
        "AEAT_DATABASE_URL": None,
        "COLUMNS": "220",
    }


def _choice_tokens_from_invalid_value(output: str) -> set[str]:
    undecorated = re.sub(r"[┌┐└┘─│]", " ", output)
    flat = re.sub(r"\s+", " ", undecorated)
    match = re.search(r"is not one of (?P<choices>.*?)\.", flat)
    assert match is not None, output
    return set(re.findall(r"'([^']+)'", match.group("choices")))


def test_profile_create_help_advertises_situacion_familiar_runtime_choices(
    tmp_path: Path,
) -> None:
    """The help surface must not hide accepted family-situation tokens.

    This drives the real CLI twice: one invalid invocation asks the runtime
    validator which values it accepts, then the help output must advertise those
    same tokens. The assertion is against the observed runtime contract, not a
    duplicated enum literal.
    """

    env = _isolated_env(tmp_path)
    invalid = invoke_cached_cli(
        [
            "--language",
            "en",
            "config",
            "profile",
            "create",
            "invalid-family-situation",
            "--quiet",
            "--accept-defaults",
            "--tax-id",
            "12345678Z",
            "--entity-type",
            "natural_person",
            "--name",
            "Invalid",
            "--surnames",
            "Operator",
            "--situacion-familiar",
            "1",
        ],
        env=env,
    )
    assert invalid.exit_code != 0, invalid.output
    runtime_choices = _choice_tokens_from_invalid_value(invalid.output)
    assert runtime_choices

    help_result = invoke_cached_cli(
        ["--language", "en", "config", "profile", "create", "--help"],
        env=env,
    )
    assert help_result.exit_code == 0, help_result.output
    compact_help = re.sub(r"\s+", "", help_result.output)

    assert "FUNCTION" not in help_result.output
    missing = sorted(token for token in runtime_choices if token not in compact_help)
    assert not missing, (
        "--situacion-familiar runtime choices are not all visible in profile-create help: "
        f"{missing}"
    )
