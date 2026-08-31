from __future__ import annotations

import pytest
import typer
import typer.main

from ....core.json_contract import OutputSchema
from ....core.redaction.rules import CLI_PROFILE_ID_PLACEHOLDER
from .._command_suggestions import INVOCATION_REMAINDER_META_KEY
from .._common import _is_metadata_invocation, emit_envelope

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "986c0dc9-56dc-422b-9d8f-698661b9eb1e"  # was '123e4567-e89b-12d3-a456-426614174000'


class _EnvelopePayload(OutputSchema):
    profile_id: str


def test_envelope_text_path_redacts_lines_through_common_renderer(capsys: pytest.CaptureFixture[str]) -> None:
    # Create a typer app and get its click command to create a proper typer.Context.
    # The Typer must carry at least one command; the current (vendored-click) typer
    # raises "Could not get a command for this Typer instance" for an empty app.
    app = typer.Typer()

    @app.command()
    def _noop() -> None: ...

    click_cmd = typer.main.get_command(app)
    ctx = typer.Context(click_cmd, obj={"format": "text"})

    emit_envelope(
        ctx,
        command="app secure audit",
        result=_EnvelopePayload(profile_id=_PROFILE_ID),
        lines=(f"profile={_PROFILE_ID}",),
    )

    output = capsys.readouterr().out
    assert _PROFILE_ID not in output
    assert f"profile={CLI_PROFILE_ID_PLACEHOLDER}" in output


def test_common_reads_metadata_posture_from_the_cli_context() -> None:
    """Output metadata posture comes from this invocation, never ambient argv."""
    app = typer.Typer()

    @app.command()
    def _noop() -> None: ...

    click_cmd = typer.main.get_command(app)
    ctx = typer.Context(click_cmd)
    ctx.meta[INVOCATION_REMAINDER_META_KEY] = ["app", "overview", "--help"]

    assert _is_metadata_invocation(ctx) is True


def test_operator_progress_banner_goes_to_stderr_not_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    """The Cl@ve auth-wait banner (carrying the verification code) is the
    operator channel the CLI arms; it must land on stderr so the stdout JSON
    envelope stays pure. Exercises the exact sink the ``cadrumo`` entry point
    installs via ``operator_progress_sink``."""

    from ....core.operator_progress import OperatorProgress
    from .. import _emit_operator_progress

    _emit_operator_progress(
        OperatorProgress(message="AEAT page verification code: YLL", timeout_seconds=120),
    )

    captured = capsys.readouterr()
    assert "YLL" in captured.err
    assert "Time remaining 2:00" in captured.err
    assert "YLL" not in captured.out
