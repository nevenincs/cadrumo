"""Tests for financial aggregation value models."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from aeat.application.aggregation import AggregationPeriodError, Period, PeriodKind

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_period_accepts_quarter_with_dash_and_is_frozen() -> None:
    period = Period.model_validate("2025-Q1")

    assert period.raw == "2025Q1"
    assert period.start == date(2025, 1, 1)
    assert period.end == date(2025, 3, 31)
    with pytest.raises(ValidationError):
        period.year = 2026  # type: ignore[misc]


def test_aggregation_period_kind_values() -> None:
    assert PeriodKind.QUARTERLY.value == "quarterly"
    assert PeriodKind.MONTHLY.value == "monthly"
    assert PeriodKind.ANNUAL.value == "annual"


def test_period_mapping_accepts_canonical_kind() -> None:
    period = Period.model_validate({"raw": "2025Q1", "year": 2025, "quarter": "Q1", "kind": "quarterly"})
    assert period.kind is PeriodKind.QUARTERLY


def test_period_rejects_ambiguous_text() -> None:
    with pytest.raises(AggregationPeriodError):
        Period.model_validate("2025-Q5")
