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


class TestPeriodConstructionContract:
    @pytest.mark.parametrize(
        ("filing_year", "code", "expected"),
        [
            (2026, "1T", Period.from_year_and_code(2026, "1T")),
            (2026, "4T", Period.from_year_and_code(2026, "4T")),
            (2026, "03", Period.from_year_and_code(2026, "03")),
            (2026, "12", Period.from_year_and_code(2026, "12")),
            (2026, "0A", Period.from_year_and_code(2026, "0A")),
            (2026, "1P", Period.from_year_and_code(2026, "1P")),
            (2026, "2P", Period.from_year_and_code(2026, "2P")),
            (2026, "3P", Period.from_year_and_code(2026, "3P")),
        ],
    )
    def test_bare_tokens_resolve_with_explicit_year(self, filing_year: int, code: str, expected: Period) -> None:
        assert Period.from_year_and_code(filing_year, code) == expected

    @pytest.mark.parametrize("combined", ("2026Q1", "2026-1T", "2026-03", "2026A", "2026", "2026P1"))
    def test_combined_forms_refuse_at_core_period_boundary(self, combined: str) -> None:
        with pytest.raises(ValueError, match=r"invalid period code"):
            Period.from_year_and_code(2026, combined)


class TestQuarterlyAndAnnualBoundaries:
    @pytest.mark.parametrize(
        ("registry_period", "start", "end"),
        [
            ("1T", date(2026, 1, 1), date(2026, 3, 31)),
            ("2T", date(2026, 4, 1), date(2026, 6, 30)),
            ("3T", date(2026, 7, 1), date(2026, 9, 30)),
            ("4T", date(2026, 10, 1), date(2026, 12, 31)),
            ("0A", date(2026, 1, 1), date(2026, 12, 31)),
        ],
    )
    def test_quarterly_and_annual_boundaries(self, registry_period: str, start: date, end: date) -> None:
        assert period_start_date(2026, registry_period) == start
        assert period_end_date(2026, registry_period) == end


class TestPagoFraccionadoBoundaries:
    """The Modelo 202 IS pago-fraccionado instalment claves.

    Per the AEAT Modelo 202 instructions, ``1P`` is the payment made in
    the first twenty calendar days of April, ``2P`` the equivalent
    October payment, and ``3P`` the December payment. The period-boundary
    helpers map each instalment clave to its payment month so the
    calculate path can resolve a ``filing_period`` date context for a
    Modelo 202 work unit. The expected months are read directly from the
    AEAT instruction text, not derived from the helper under test.
    """

    @pytest.mark.parametrize(
        ("registry_period", "start", "end"),
        [
            ("1P", date(2026, 4, 1), date(2026, 4, 30)),
            ("2P", date(2026, 10, 1), date(2026, 10, 31)),
            ("3P", date(2026, 12, 1), date(2026, 12, 31)),
        ],
    )
    def test_pago_fraccionado_boundaries(self, registry_period: str, start: date, end: date) -> None:
        assert period_start_date(2026, registry_period) == start
        assert period_end_date(2026, registry_period) == end

    def test_pago_fraccionado_no_longer_raises_invalid_registry_period(self) -> None:
        """``1P``/``2P``/``3P`` must not fall through to the
        ``invalid registry period`` refusal — the calculate path's
        period-boundary resolution recognises the IS instalment claves.
        """

        for clave in ("1P", "2P", "3P"):
            # Neither boundary helper raises for a valid instalment clave.
            period_start_date(2026, clave)
            period_end_date(2026, clave)


class TestBoundaryRefusals:
    def test_unknown_registry_period_raises(self) -> None:
        with pytest.raises(PeriodValidationError, match=r"invalid registry period"):
            period_end_date(2026, "ZZ")
        with pytest.raises(PeriodValidationError, match=r"invalid registry period"):
            period_start_date(2026, "ZZ")


class TestPagoFraccionadoConstruction:
    """The Modelo 202 IS pago-fraccionado instalment claves are bare tokens."""

    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            ("1P", Period.from_year_and_code(2026, "1P")),
            ("2P", Period.from_year_and_code(2026, "2P")),
            ("3P", Period.from_year_and_code(2026, "3P")),
        ],
    )
    def test_pago_fraccionado_tokens_resolve_with_explicit_year(self, code: str, expected: Period) -> None:
        assert Period.from_year_and_code(2026, code) == expected

    @pytest.mark.parametrize("code", ["1P", "2P", "3P"])
    def test_registry_period_accepted_by_boundary_helpers(self, code: str) -> None:
        """Every valid bare instalment token is accepted by the boundary helpers."""
        start = period_start_date(2026, code)
        end = period_end_date(2026, code)
        assert start <= end
