"""Tests for the PostToolUse faithfulness check."""

from __future__ import annotations

import pytest

from .._faithfulness import faithfulness_check

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_TOOL_JSON = '{"result": {"casilla_03": "1234.56", "casilla_07": "246.91"}, "status": "success"}'


def test_grounded_narration_is_faithful() -> None:
    text = "Your net result (casilla 03) is 1234.56 EUR and the instalment is 246,91."
    result = faithfulness_check(agent_text=text, tool_result_json=_TOOL_JSON)
    assert result.faithful
    assert result.flagged_values == ()
    assert not result.blocks


def test_fabricated_amount_is_flagged_as_advisory() -> None:
    text = "Your instalment is 999.99 EUR."  # not present in the tool JSON
    result = faithfulness_check(agent_text=text, tool_result_json=_TOOL_JSON)
    assert not result.faithful
    assert "999.99" in result.flagged_values
    # Advisory by default: flags but does not block.
    assert result.blocking is False
    assert not result.blocks


def test_fabricated_amount_blocks_on_the_handoff_path() -> None:
    text = "Exporting your declaration with an instalment of 999.99 EUR."
    result = faithfulness_check(agent_text=text, tool_result_json=_TOOL_JSON, blocking=True)
    assert not result.faithful
    assert result.blocks


def test_bare_integers_are_not_flagged() -> None:
    # Casilla numbers (01, 03) and years (2024) are bare integers, not amounts,
    # so they must not be flagged as fabricated values.
    text = "Casilla 03 for filing year 2024 covers period 1."
    result = faithfulness_check(agent_text=text, tool_result_json=_TOOL_JSON)
    assert result.faithful
