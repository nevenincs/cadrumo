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


@pytest.mark.parametrize("amount", ["9999.99", "12345.67", "15000.00", "999999.99"])
def test_large_ungrouped_fabricated_amount_is_flagged_advisory(amount: str) -> None:
    # HIGH-1 regression: an amount >=1000 written WITHOUT a thousands separator
    # (the common machine / en-locale output shape) and absent from the tool
    # result must be flagged. Before the fix the amount regex capped the
    # integer part at 3 digits, so these slipped the gate entirely.
    result = faithfulness_check(agent_text=f"Your result is {amount} EUR.", tool_result_json="{}")
    assert not result.faithful
    assert amount in result.flagged_values


@pytest.mark.parametrize("amount", ["9999.99", "15000.00", "999999.99"])
def test_large_ungrouped_fabricated_amount_hard_blocks_at_handoff(amount: str) -> None:
    # HIGH-1 regression on the primary safety invariant: the same fabricated
    # large amount on the export / record-marker handoff path must HARD-BLOCK,
    # not merely advise.
    result = faithfulness_check(agent_text=f"Exporting with {amount} EUR.", tool_result_json="{}", blocking=True)
    assert result.blocks
    assert amount in result.flagged_values


def test_large_ungrouped_amount_that_is_grounded_passes() -> None:
    # The fix must not over-flag: a large amount that IS present in the tool
    # result (separator-agnostic) stays faithful.
    tool_json = '{"result": {"base": "15000.00"}}'
    result = faithfulness_check(agent_text="The base is 15.000,00 EUR.", tool_result_json=tool_json, blocking=True)
    assert result.faithful
    assert not result.blocks
