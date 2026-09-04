"""Teeth for the single-axis rule on a parameter's dated values.

A parameter carries values on exactly one date axis. The resolver requires every
value's axis to be present in the caller's date context, so a parameter that
mixes axes breaks every existing caller of it, not only the one that wanted the
new axis. And the overlap scan groups BY axis, so a cross-axis double match is
invisible to it by construction and would surface at runtime as "expected exactly
one dated value" — a confusing symptom for what is really a declaration defect.

These pin the refusal at load, and pin that the pre-existing same-axis overlap
teeth still bite.
"""

from __future__ import annotations

from datetime import date

import pytest

from .._validate_parameter_temporal import validate_dated_values
from ..schema_formula import DatedValue

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _value(date_axis: str, valid_from: date, valid_to: date | None = None) -> DatedValue:
    """Build one dated value on the named axis."""
    payload: dict[str, object] = {"value": "1", "date_axis": date_axis, "valid_from": valid_from}
    if valid_to is not None:
        payload["valid_to"] = valid_to
    return DatedValue.model_validate(payload)


def test_a_single_axis_parameter_loads_clean() -> None:
    """The ordinary shape: one axis, contiguous non-overlapping windows."""
    assert not validate_dated_values(
        "probe",
        "renta-2024-example",
        [
            _value("filing_period", date(2024, 1, 1), date(2024, 12, 31)),
            _value("filing_period", date(2025, 1, 1), date(2025, 12, 31)),
        ],
    )


def test_a_single_non_filing_axis_parameter_loads_clean() -> None:
    """The rule is single-axis, not filing-axis: an event axis alone is fine."""
    assert not validate_dated_values(
        "probe",
        "iva-bien-inversion-example",
        [_value("transaction_date", date(1993, 1, 1), date(2014, 12, 31))],
    )


def test_a_mixed_axis_parameter_is_refused_at_load() -> None:
    """TEETH: the declaration defect fails at load rather than at resolution."""
    failures = validate_dated_values(
        "probe",
        "mixed-example",
        [
            _value("filing_period", date(2024, 1, 1), date(2024, 12, 31)),
            _value("transaction_date", date(2016, 1, 1), date(2016, 12, 31)),
        ],
    )
    assert len(failures) == 1
    assert "mixes date axes" in failures[0]


def test_a_cross_axis_double_match_is_refused_at_load() -> None:
    """TEETH: the case the axis-grouped overlap scan cannot see.

    Both windows cover their own selected date, so the resolver would find two
    matches and refuse at runtime with a message about match counts rather than
    about the axes. Refusing here names the actual defect.
    """
    failures = validate_dated_values(
        "probe",
        "double-match-example",
        [
            _value("filing_period", date(2000, 1, 1), date(2030, 12, 31)),
            _value("transaction_date", date(2000, 1, 1), date(2030, 12, 31)),
        ],
    )
    assert len(failures) == 1
    assert "mixes date axes" in failures[0]


def test_same_axis_overlap_teeth_survive_the_new_rule() -> None:
    """The pre-existing refusal is unchanged and still fires on its own case."""
    failures = validate_dated_values(
        "probe",
        "overlap-example",
        [
            _value("filing_period", date(2024, 1, 1), date(2024, 12, 31)),
            _value("filing_period", date(2024, 6, 1), date(2025, 12, 31)),
        ],
    )
    assert len(failures) == 1
    assert "overlapping filing_period values" in failures[0]
