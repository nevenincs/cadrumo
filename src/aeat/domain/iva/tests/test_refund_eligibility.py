"""Multi-persona verification of the Modelo 303 refund (devolución) eligibility gate.

The gate is the law-determined core of the REDEME company refund schema: a
negative-result refund (``D``) is available only to a REDEME-inscribed taxpayer
(art. 30 RD 1624/1992, every period) or in the last filing period of the year
(Ley 37/1992 art. 116); otherwise only compensación (``C``) is lawful. These tests
run the gate across the affected personas — REDEME company (monthly), last-period
autónomo, ordinary mid-period (refused), and cross-entity — asserting both the
boolean availability and the machine reason code.
"""

from __future__ import annotations

import pytest

from ....core import Period
from .. import (
    RefundEligibilityReason,
    is_last_filing_period_of_year,
    refund_disposition_available,
    refund_eligibility_reason,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _p(code: str, year: int = 2024) -> Period:
    return Period.from_year_and_code(year, code)


class TestRedemeCompanyMonthlyRefund:
    """Persona 1 — REDEME-inscribed company filing monthly: refund available every period."""

    @pytest.mark.parametrize("code", ["01", "02", "03", "06", "11", "12"])
    def test_redeme_refund_available_in_every_monthly_period(self, code: str) -> None:
        assert refund_disposition_available(redeme_enrolled=True, period=_p(code)) is True
        assert (
            refund_eligibility_reason(redeme_enrolled=True, period=_p(code))
            is RefundEligibilityReason.REDEME_INSCRIBED
        )

    def test_redeme_refund_available_even_in_an_early_quarter(self) -> None:
        assert refund_disposition_available(redeme_enrolled=True, period=_p("1T")) is True
        assert (
            refund_eligibility_reason(redeme_enrolled=True, period=_p("1T"))
            is RefundEligibilityReason.REDEME_INSCRIBED
        )


class TestLastPeriodRefund:
    """Persona 2 — non-REDEME autónomo: refund available only in the last period of the year."""

    @pytest.mark.parametrize("code", ["4T", "12", "0A"])
    def test_refund_available_in_last_period_without_redeme(self, code: str) -> None:
        assert is_last_filing_period_of_year(_p(code)) is True
        assert refund_disposition_available(redeme_enrolled=False, period=_p(code)) is True
        assert (
            refund_eligibility_reason(redeme_enrolled=False, period=_p(code))
            is RefundEligibilityReason.LAST_PERIOD_OF_YEAR
        )

    @pytest.mark.parametrize("code", ["1T", "2T", "3T", "01", "06", "11"])
    def test_non_last_period_is_not_last(self, code: str) -> None:
        assert is_last_filing_period_of_year(_p(code)) is False


class TestOrdinaryMidPeriodRefused:
    """Persona 3 (regression control) — ordinary non-REDEME mid-period: refund unavailable, only carry-forward."""

    @pytest.mark.parametrize("code", ["1T", "2T", "3T", "01", "05", "11"])
    def test_refund_unavailable(self, code: str) -> None:
        assert refund_disposition_available(redeme_enrolled=False, period=_p(code)) is False
        assert (
            refund_eligibility_reason(redeme_enrolled=False, period=_p(code)) is RefundEligibilityReason.NOT_ELIGIBLE
        )


class TestCrossEntityAndInvariants:
    """Persona 4 — the gate is entity-agnostic: REDEME eligibility is open to every entity type,
    decided solely by the redeme axis and the period (no entity-type input)."""

    def test_gate_depends_only_on_redeme_and_period(self) -> None:
        # Identical inputs -> identical verdict, regardless of which entity type's
        # profile supplied `redeme_enrolled` (natural_person / legal_entity /
        # attribution_entity all flow the same boolean here).
        assert refund_disposition_available(redeme_enrolled=True, period=_p("1T")) is True
        assert refund_disposition_available(redeme_enrolled=False, period=_p("1T")) is False

    def test_redeme_takes_precedence_over_last_period_reason(self) -> None:
        # A REDEME taxpayer in the last period is eligible; REDEME is the reported reason.
        assert refund_disposition_available(redeme_enrolled=True, period=_p("4T")) is True
        assert (
            refund_eligibility_reason(redeme_enrolled=True, period=_p("4T")) is RefundEligibilityReason.REDEME_INSCRIBED
        )
