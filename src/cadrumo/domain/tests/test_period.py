"""Tests for filing-period construction and boundary helpers."""

from __future__ import annotations

from datetime import date

import pytest

from ...core.period import Period
from ..period import (
    PeriodValidationError,
    RegistryPeriodError,
    calculation_filing_date,
    period_end_date,
    period_start_date,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CONTIGUOUS_REGISTRY_PERIODS = (
    "1T",
    "2T",
    "3T",
    "4T",
    "0A",
    *(f"{month:02d}" for month in range(1, 13)),
)


def test_bare_tokens_resolve_with_explicit_year() -> None:
    for filing_year, code in (
        (2026, "1T"),
        (2026, "4T"),
        (2026, "03"),
        (2026, "12"),
        (2026, "0A"),
        (2026, "1P"),
        (2026, "2P"),
        (2026, "3P"),
    ):
        period = Period.from_year_and_code(filing_year, code)
        assert period.filing_year == filing_year, code
        assert period.registry_token == code, code


def test_period_refusals_stay_at_their_boundaries() -> None:
    for combined in ("2026Q1", "2026-1T", "2026-03", "2026A", "2026", "2026P1"):
        with pytest.raises(ValueError, match=r"invalid period code"):
            Period.from_year_and_code(2026, combined)

    for boundary in (period_start_date, period_end_date):
        with pytest.raises(RegistryPeriodError, match=r"invalid registry period") as exc_info:
            boundary(2026, "ZZ")
        assert type(exc_info.value) is PeriodValidationError


def test_registry_period_boundaries() -> None:
    """Boundary helpers return literal AEAT calendar windows.

    The Modelo 202 IS pago-fraccionado instalment claves map to their
    AEAT instruction payment months, not to derived quarter ranges.
    """

    for registry_period, start, end in (
        ("1T", date(2026, 1, 1), date(2026, 3, 31)),
        ("2T", date(2026, 4, 1), date(2026, 6, 30)),
        ("3T", date(2026, 7, 1), date(2026, 9, 30)),
        ("4T", date(2026, 10, 1), date(2026, 12, 31)),
        ("0A", date(2026, 1, 1), date(2026, 12, 31)),
        ("1P", date(2026, 4, 1), date(2026, 4, 30)),
        ("2P", date(2026, 10, 1), date(2026, 10, 31)),
        ("3P", date(2026, 12, 1), date(2026, 12, 31)),
    ):
        assert period_start_date(2026, registry_period) == start, registry_period
        assert period_end_date(2026, registry_period) == end, registry_period


@pytest.mark.parametrize("registry_period", _CONTIGUOUS_REGISTRY_PERIODS)
def test_contiguous_helper_boundaries_match_canonical_period(registry_period: str) -> None:
    """All contiguous calculation-date paths must end on the typed period end."""
    period = Period.from_year_and_code(2026, registry_period)

    assert period_start_date(2026, registry_period) == period.start_date
    assert period_end_date(2026, registry_period) == period.end_date
    assert calculation_filing_date(period) == period.end_date


@pytest.mark.parametrize(
    ("registry_period", "expected"),
    (
        ("4P", date(2026, 12, 31)),
        ("AD-HOC", date(2026, 12, 31)),
        ("EVENT-1", date(2026, 12, 31)),
        ("EVENT-42", date(2026, 12, 31)),
    ),
)
def test_calculation_filing_date_keeps_explicit_non_span_fallback_and_strict_refusal(
    registry_period: str,
    expected: date,
) -> None:
    """Calculation-only periods use the declared fallback without gaining a range."""
    period = Period.from_year_and_code(2026, registry_period)

    assert calculation_filing_date(period) == expected
    for boundary in (period_start_date, period_end_date):
        with pytest.raises(PeriodValidationError, match=r"invalid registry period"):
            boundary(2026, registry_period)
