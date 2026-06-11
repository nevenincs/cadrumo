"""Tests for financial aggregation value models."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from .. import AggregationPeriodError, Period, PeriodKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_period_accepts_quarter_with_dash_and_is_frozen() -> None:
    period = Period.model_validate("2025-Q1")

    assert period.year == 2025
    assert period.kind is PeriodKind.QUARTERLY
    assert period.start == date(2025, 1, 1)
    assert period.end == date(2025, 3, 31)
    with pytest.raises(ValidationError):
        period.year = 2026


def test_aggregation_period_kind_values() -> None:
    assert PeriodKind.QUARTERLY.value == "quarterly"
    assert PeriodKind.MONTHLY.value == "monthly"
    assert PeriodKind.ANNUAL.value == "annual"


def test_period_mapping_accepts_canonical_kind() -> None:
    # ``raw`` is a legacy field that the Mapping branch strips; it must be ignored.
    period = Period.model_validate({"raw": "2025Q1", "year": 2025, "quarter": "Q1", "kind": "quarterly"})
    assert period.kind is PeriodKind.QUARTERLY


def test_period_rejects_ambiguous_text() -> None:
    with pytest.raises(AggregationPeriodError):
        Period.model_validate("2025-Q5")
