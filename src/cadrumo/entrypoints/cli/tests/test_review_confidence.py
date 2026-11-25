"""Tests for the ``review queue --confidence-below`` CLI gate."""

from __future__ import annotations

from decimal import Decimal

import pytest
import typer

from ....core.config import override_settings
from ..review_commands import resolve_confidence_threshold

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


_ACCEPTED_THRESHOLDS = (
    (None, None),
    ("0", Decimal("0")),
    ("0.25", Decimal("0.25")),
    ("1", Decimal("1")),
)
_REJECTED_THRESHOLDS = ("1.5", "-0.1", "2.0")
_NON_CANONICAL_THRESHOLDS = ("nan", "inf", "1e-1", "0,5", "2.5e-1")


def test_resolve_confidence_threshold_accepts_none_and_in_range_values() -> None:
    failures: list[str] = []
    for value, expected in _ACCEPTED_THRESHOLDS:
        actual = resolve_confidence_threshold(value)
        if actual != expected:
            failures.append(f"{value!r}: expected {expected!r}, got {actual!r}")

    assert not failures, "\n".join(failures)


def test_resolve_confidence_threshold_rejects_out_of_range_naming_bounds() -> None:
    failures: list[str] = []
    for value in _REJECTED_THRESHOLDS:
        with override_settings(cadrumo_output_language="en"):
            try:
                resolve_confidence_threshold(value)
            except typer.BadParameter as exc:
                message = str(exc)
            else:
                failures.append(f"{value!r}: accepted out-of-range value")
                continue
        if "between 0 and 1" not in message:
            failures.append(f"{value!r}: missing bounds text in {message!r}")
        if str(value) not in message:
            failures.append(f"{value!r}: missing offending value in {message!r}")

    assert not failures, "\n".join(failures)


@pytest.mark.parametrize("written", _NON_CANONICAL_THRESHOLDS)
def test_resolve_confidence_threshold_refuses_non_canonical_text(written: str) -> None:
    with pytest.raises(typer.BadParameter) as refused:
        resolve_confidence_threshold(written)

    assert written in str(refused.value)
