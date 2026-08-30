"""Tests for financial aggregation value models."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ....core.period import Period, PeriodError, PeriodKind
from ._renta_income_aggregation_support import _period

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_period_constructs_quarter_from_year_and_code_and_is_frozen() -> None:
    period = _period(2025, "1T")

    assert period.filing_year == 2025
    assert period.kind is PeriodKind.QUARTERLY
    assert period.start_date == date(2025, 1, 1)
    assert period.end_date == date(2025, 3, 31)
    with pytest.raises(ValidationError):
        period.__setattr__("filing_year", 2026)


def test_aggregation_period_kind_values() -> None:
    assert PeriodKind.QUARTERLY.value == "quarterly"
    assert PeriodKind.MONTHLY.value == "monthly"
    assert PeriodKind.ANNUAL.value == "annual"


def test_period_mapping_accepts_canonical_core_payload() -> None:
    period = Period.model_validate({"filing_year": 2025, "code": "1T"})
    assert period.kind is PeriodKind.QUARTERLY


def test_period_rejects_combined_code() -> None:
    with pytest.raises(PeriodError):
        Period.from_year_and_code(2025, "2025Q1")
