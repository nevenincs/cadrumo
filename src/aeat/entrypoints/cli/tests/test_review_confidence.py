"""Tests for the ``review queue --confidence-below`` CLI gate."""

from __future__ import annotations

from decimal import Decimal

import pytest
import typer

from ....core.config import override_settings
from .._review import _resolve_confidence_threshold

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_resolve_confidence_threshold_passes_through_none() -> None:
    assert _resolve_confidence_threshold(None) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.0, Decimal("0")),
        (0.25, Decimal("0.25")),
        (1.0, Decimal("1")),
    ],
)
def test_resolve_confidence_threshold_accepts_in_range(value: float, expected: Decimal) -> None:
    assert _resolve_confidence_threshold(value) == expected


@pytest.mark.parametrize("value", [1.5, -0.1, 2.0])
def test_resolve_confidence_threshold_rejects_out_of_range_naming_bounds(value: float) -> None:
    with override_settings(aeat_output_language="en"), pytest.raises(typer.BadParameter) as exc_info:
        _resolve_confidence_threshold(value)
    message = str(exc_info.value)
    assert "between 0 and 1" in message
    assert str(value) in message
