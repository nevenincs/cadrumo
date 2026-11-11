"""Tests for financial aggregation value models."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ....core.period import Period, PeriodError, PeriodKind
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .renta_income_aggregation_support import renta_income_aggregation_period

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_period_constructs_quarter_from_year_and_code_and_is_frozen() -> None:
    period = renta_income_aggregation_period(_YEAR, "1T")

    assert period.filing_year == _YEAR
    assert period.kind is PeriodKind.QUARTERLY
    assert period.start_date == date(_YEAR, 1, 1)
    assert period.end_date == date(_YEAR, 3, 31)
    with pytest.raises(ValidationError):
        period.__setattr__("filing_year", 2026)


def test_aggregation_period_kind_values() -> None:
    assert PeriodKind.QUARTERLY.value == "quarterly"
    assert PeriodKind.MONTHLY.value == "monthly"
    assert PeriodKind.ANNUAL.value == "annual"


def test_period_mapping_accepts_canonical_core_payload() -> None:
    period = Period.model_validate({"filing_year": _YEAR, "code": "1T"})
    assert period.kind is PeriodKind.QUARTERLY


def test_period_rejects_combined_code() -> None:
    with pytest.raises(PeriodError):
        Period.from_year_and_code(_YEAR, f"{_YEAR}Q1")
