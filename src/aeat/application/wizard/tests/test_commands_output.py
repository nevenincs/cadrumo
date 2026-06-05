"""Output-boundary tests for wizard command helpers."""

from __future__ import annotations

import pytest

from ....core.redaction import CLI_PROFILE_ID_PLACEHOLDER
from .._commands import _emit_wizard_success

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_wizard_success_text_uses_central_output_redaction(capsys: pytest.CaptureFixture[str]) -> None:
    profile_id_like_label = "123e4567-e89b-12d3-a456-426614174000"

    _emit_wizard_success("create", profile_id_like_label)

    output = capsys.readouterr().out
    assert profile_id_like_label not in output
    assert CLI_PROFILE_ID_PLACEHOLDER in output
    assert "next\taeat app modelo work create" in output
