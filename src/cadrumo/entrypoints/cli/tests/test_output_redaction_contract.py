from __future__ import annotations

import json

import pytest
import typer
from typer.core import TyperGroup

from ....application.operator_surface.help_models import RootLandingReport
from ....core import STR_KEYED_MAPPING_ADAPTER
from ....core.redaction import (
    CLI_PROFILE_ID_PLACEHOLDER,
)
from ....tests.cli_runner import cadrumo_click_command
from .._common import emit_envelope
from .._root_payloads import RootStatusResult

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "986c0dc9-56dc-422b-9d8f-698661b9eb1e"  # was '123e4567-e89b-12d3-a456-426614174000'


def _context(format_name: str) -> typer.Context:
    # Get the Cadrumo CLI command and narrow it to TyperGroup for compatibility with typer.Context.
    root_cmd = cadrumo_click_command()
    assert isinstance(root_cmd, TyperGroup)
    ctx = typer.Context(root_cmd)
    ctx.ensure_object(dict)["format"] = format_name
    return ctx


def _payload() -> dict[str, object]:
    return STR_KEYED_MAPPING_ADAPTER.validate_python(
        RootLandingReport(
            profile_selected=True,
            active_profile=_PROFILE_ID,
            command="aeat config profile create NAME",
            message="Create a profile before starting tax work.",
        ).model_dump(mode="json"),
    )


def _lines() -> tuple[str, ...]:
    return (
        f"active_profile={_PROFILE_ID}",
        "command=aeat config profile create NAME",
        "message=Create a profile before starting tax work.",
    )


def test_emit_text_redacts_command_output_canary_matrix(capsys: pytest.CaptureFixture[str]) -> None:
    emit_envelope(
        _context("text"),
        command="root.status",
        result=RootStatusResult.model_validate(_payload()),
        lines=_lines(),
    )

    output = capsys.readouterr().out

    assert _PROFILE_ID not in output
    assert f"active_profile={CLI_PROFILE_ID_PLACEHOLDER}" in output


def test_emit_json_redacts_command_output_canary_matrix(capsys: pytest.CaptureFixture[str]) -> None:
    emit_envelope(
        _context("json"),
        command="root.status",
        result=RootStatusResult.model_validate(_payload()),
        lines=_lines(),
    )

    output = capsys.readouterr().out
    envelope = json.loads(output)
    payload = envelope["result"]

    assert _PROFILE_ID not in output
    assert payload == {
        "profile_selected": True,
        "active_profile": CLI_PROFILE_ID_PLACEHOLDER,
        "command": "aeat config profile create NAME",
        "message": "Create a profile before starting tax work.",
    }
    assert envelope["command"] == "root.status"
