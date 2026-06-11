from __future__ import annotations

import pytest
import typer
import typer.main

from ....core.json_contract import OutputSchema
from ....core.redaction import CLI_PROFILE_ID_PLACEHOLDER
from .._common import _emit_envelope

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "123e4567-e89b-12d3-a456-426614174000"


class _EnvelopePayload(OutputSchema):
    profile_id: str


def test_emit_envelope_text_path_redacts_lines_through_common_renderer(capsys: pytest.CaptureFixture[str]) -> None:
    # Create a typer app and get its click command to create a proper typer.Context.
    # The Typer must carry at least one command; the current (vendored-click) typer
    # raises "Could not get a command for this Typer instance" for an empty app.
    app = typer.Typer()

    @app.command()
    def _noop() -> None: ...

    click_cmd = typer.main.get_command(app)
    ctx = typer.Context(click_cmd, obj={"format": "text"})

    _emit_envelope(
        ctx,
        command="app secure audit",
        result=_EnvelopePayload(profile_id=_PROFILE_ID),
        lines=(f"profile={_PROFILE_ID}",),
    )

    output = capsys.readouterr().out
    assert _PROFILE_ID not in output
    assert f"profile={CLI_PROFILE_ID_PLACEHOLDER}" in output
