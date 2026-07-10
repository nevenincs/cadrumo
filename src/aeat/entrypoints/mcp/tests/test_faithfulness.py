"""Tests for the PostToolUse faithfulness check."""

from __future__ import annotations

import pytest

from .._faithfulness import faithfulness_check

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_TOOL_JSON = '{"result": {"casilla_03": "1234.56", "casilla_07": "246.91"}, "status": "success"}'

_GROUNDED_CASES = (
    (
        "tool-values",
        "Your net result (casilla 03) is 1234.56 EUR and the instalment is 246,91.",
        _TOOL_JSON,
        False,
    ),
    (
        "bare-integers",
        "Casilla 03 for filing year 2024 covers period 1.",
        _TOOL_JSON,
        False,
    ),
    (
        "large-grounded",
        "The base is 15.000,00 EUR.",
        '{"result": {"base": "15000.00"}}',
        True,
    ),
)

_FABRICATED_CASES = (
    (
        "advisory-small",
        "Your instalment is 999.99 EUR.",
        _TOOL_JSON,
        False,
        "999.99",
        False,
    ),
    (
        "handoff-small",
        "Exporting your declaration with an instalment of 999.99 EUR.",
        _TOOL_JSON,
        True,
        "999.99",
        True,
    ),
    *(
        (f"advisory-large-{amount}", f"Your result is {amount} EUR.", "{}", False, amount, False)
        for amount in ("9999.99", "12345.67", "15000.00", "999999.99")
    ),
    *(
        (f"handoff-large-{amount}", f"Exporting with {amount} EUR.", "{}", True, amount, True)
        for amount in ("9999.99", "15000.00", "999999.99")
    ),
)


def test_grounded_numbers_are_faithful() -> None:
    failures: list[str] = []
    for label, text, tool_json, blocking in _GROUNDED_CASES:
        result = faithfulness_check(agent_text=text, tool_result_json=tool_json, blocking=blocking)
        if not result.faithful:
            failures.append(f"{label}: flagged {result.flagged_values!r}")
        if result.blocks:
            failures.append(f"{label}: unexpectedly blocked")

    assert not failures, "\n".join(failures)


def test_fabricated_amounts_are_flagged_and_block_only_on_handoff() -> None:
    failures: list[str] = []
    for label, text, tool_json, blocking, expected_value, expected_blocks in _FABRICATED_CASES:
        result = faithfulness_check(agent_text=text, tool_result_json=tool_json, blocking=blocking)
        if result.faithful:
            failures.append(f"{label}: remained faithful")
        if expected_value not in result.flagged_values:
            failures.append(f"{label}: missing {expected_value!r} in {result.flagged_values!r}")
        if result.blocks is not expected_blocks:
            failures.append(f"{label}: blocks={result.blocks!r}, expected {expected_blocks!r}")
        if result.blocking is not blocking:
            failures.append(f"{label}: blocking={result.blocking!r}, expected {blocking!r}")

    assert not failures, "\n".join(failures)
