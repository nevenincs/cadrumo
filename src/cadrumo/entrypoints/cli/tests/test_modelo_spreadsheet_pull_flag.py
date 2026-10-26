"""Retired remote calculation verbs are absent from the actual CLI parser."""

from __future__ import annotations

import pytest

from .._modelo_spreadsheet_command_specs import MODELO_SPREADSHEET_COMMAND_SPECS
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("verb", ["pull", "calculate", "verify"])
def test_retired_spreadsheet_command_is_not_enrolled_or_executable(verb: str) -> None:
    assert f"app_modelo_spreadsheet_{verb}" not in {spec.key for spec in MODELO_SPREADSHEET_COMMAND_SPECS}
    result = invoke_cached_cli(["--language", "en", "app", "modelo", "spreadsheet", verb, "--help"])
    assert result.exit_code != 0
    assert "No such command" in result.output
    assert "Traceback" not in result.output


def test_remaining_spreadsheet_help_preserves_local_export_without_remote_input_verbs() -> None:
    result = invoke_cached_cli(["--language", "en", "app", "modelo", "spreadsheet", "--help"])
    assert result.exit_code == 0, result.output
    assert "export" in result.output
    for verb in ("pull", "calculate", "verify"):
        assert not any(line.strip().startswith(verb + " ") for line in result.output.splitlines())
