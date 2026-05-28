from __future__ import annotations

import click
import pytest

from aeat.core.json_contract import OutputSchema
from aeat.core.redaction import CLI_PROFILE_ID_PLACEHOLDER
from aeat.entrypoints.cli._common import _emit_envelope

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_PROFILE_ID = "123e4567-e89b-12d3-a456-426614174000"


class _EnvelopePayload(OutputSchema):
    profile_id: str


def test_emit_envelope_text_path_redacts_lines_through_common_renderer(capsys: pytest.CaptureFixture[str]) -> None:
    ctx = click.Context(click.Command("root"), obj={"format": "text"})

    _emit_envelope(
        ctx,
        command="app secure audit",
        result=_EnvelopePayload(profile_id=_PROFILE_ID),
        lines=(f"profile={_PROFILE_ID}",),
    )

    output = capsys.readouterr().out
    assert _PROFILE_ID not in output
    assert f"profile={CLI_PROFILE_ID_PLACEHOLDER}" in output
