"""Tests for filing-period construction and boundary helpers."""

from __future__ import annotations

from datetime import date

import pytest

from ...core import Period
from ..period import (
    PeriodValidationError,
    period_end_date,
    period_start_date,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


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
        assert period.year == filing_year, code
        assert period.registry_token == code, code


def test_period_refusals_stay_at_their_boundaries() -> None:
    for combined in ("2026Q1", "2026-1T", "2026-03", "2026A", "2026", "2026P1"):
        with pytest.raises(ValueError, match=r"invalid period code"):
            Period.from_year_and_code(2026, combined)

    for boundary in (period_start_date, period_end_date):
        with pytest.raises(PeriodValidationError, match=r"invalid registry period"):
            boundary(2026, "ZZ")


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
