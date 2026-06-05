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

from .. import BaseSeverity

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_member_names_are_uppercase() -> None:
    assert BaseSeverity.INFO.name == "INFO"
    assert BaseSeverity.WARNING.name == "WARNING"
    assert BaseSeverity.ERROR.name == "ERROR"


def test_string_values_are_lowercase() -> None:
    assert BaseSeverity.INFO.value == "info"
    assert BaseSeverity.WARNING.value == "warning"
    assert BaseSeverity.ERROR.value == "error"


def test_strenum_equates_to_underlying_string() -> None:
    assert BaseSeverity.ERROR == "error"
    assert BaseSeverity.WARNING == "warning"
    assert BaseSeverity.INFO == "info"


def test_value_lookup_round_trips() -> None:
    assert BaseSeverity("error") is BaseSeverity.ERROR
    assert BaseSeverity("warning") is BaseSeverity.WARNING
    assert BaseSeverity("info") is BaseSeverity.INFO


def test_name_lookup_round_trips() -> None:
    assert BaseSeverity["ERROR"] is BaseSeverity.ERROR
    assert BaseSeverity["WARNING"] is BaseSeverity.WARNING
    assert BaseSeverity["INFO"] is BaseSeverity.INFO


def test_unknown_value_raises() -> None:
    with pytest.raises(ValueError):
        BaseSeverity("HUGE")


def test_set_of_members_is_closed() -> None:
    assert {member.value for member in BaseSeverity} == {"info", "warning", "error"}
