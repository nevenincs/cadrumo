"""Contract tests for the unified BaseSeverity primitive.

A single ``BaseSeverity`` enum carries the INFO < WARNING < ERROR
contract across diagnostics, findings, and validation issues. Every
call site imports and uses ``BaseSeverity`` directly; semantic
context lives in the field name (``diagnostic_severity``,
``finding_severity``, ``validation_severity``), not in duplicate
type names.
"""

from __future__ import annotations

import pytest

from ..severity import BaseSeverity

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_base_severity_members_are_closed_strenum_tokens() -> None:
    cases = (
        (BaseSeverity.INFO, "INFO", "info"),
        (BaseSeverity.WARNING, "WARNING", "warning"),
        (BaseSeverity.ERROR, "ERROR", "error"),
    )

    assert tuple(BaseSeverity) == tuple(member for member, _, _ in cases)
    for member, expected_name, expected_value in cases:
        assert member.name == expected_name
        assert member.value == expected_value
        assert member == expected_value


def test_base_severity_lookup_round_trips_and_rejects_unknown_values() -> None:
    for member in BaseSeverity:
        assert BaseSeverity(member.value) is member
        assert BaseSeverity[member.name] is member

    with pytest.raises(ValueError):
        BaseSeverity("HUGE")
