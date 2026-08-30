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

from ....core.period import Period
from ..refund_eligibility import (
    RefundEligibilityReason,
    is_last_filing_period_of_year,
    refund_disposition_available,
    refund_eligibility_reason,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _p(code: str, year: int = 2024) -> Period:
    return Period.from_year_and_code(year, code)


def test_refund_eligibility_reason_matrix() -> None:
    """REDEME wins every period; otherwise only last periods can refund."""
    cases: tuple[tuple[str, bool, str, bool, bool, RefundEligibilityReason], ...] = (
        ("redeme-month-01", True, "01", False, True, RefundEligibilityReason.REDEME_INSCRIBED),
        ("redeme-month-02", True, "02", False, True, RefundEligibilityReason.REDEME_INSCRIBED),
        ("redeme-month-03", True, "03", False, True, RefundEligibilityReason.REDEME_INSCRIBED),
        ("redeme-month-06", True, "06", False, True, RefundEligibilityReason.REDEME_INSCRIBED),
        ("redeme-month-11", True, "11", False, True, RefundEligibilityReason.REDEME_INSCRIBED),
        ("redeme-month-12", True, "12", True, True, RefundEligibilityReason.REDEME_INSCRIBED),
        ("redeme-early-quarter", True, "1T", False, True, RefundEligibilityReason.REDEME_INSCRIBED),
        ("redeme-last-quarter", True, "4T", True, True, RefundEligibilityReason.REDEME_INSCRIBED),
        ("ordinary-last-quarter", False, "4T", True, True, RefundEligibilityReason.LAST_PERIOD_OF_YEAR),
        ("ordinary-last-month", False, "12", True, True, RefundEligibilityReason.LAST_PERIOD_OF_YEAR),
        ("ordinary-annual", False, "0A", True, True, RefundEligibilityReason.LAST_PERIOD_OF_YEAR),
        ("ordinary-quarter-1", False, "1T", False, False, RefundEligibilityReason.NOT_ELIGIBLE),
        ("ordinary-quarter-2", False, "2T", False, False, RefundEligibilityReason.NOT_ELIGIBLE),
        ("ordinary-quarter-3", False, "3T", False, False, RefundEligibilityReason.NOT_ELIGIBLE),
        ("ordinary-month-01", False, "01", False, False, RefundEligibilityReason.NOT_ELIGIBLE),
        ("ordinary-month-05", False, "05", False, False, RefundEligibilityReason.NOT_ELIGIBLE),
        ("ordinary-month-06", False, "06", False, False, RefundEligibilityReason.NOT_ELIGIBLE),
        ("ordinary-month-11", False, "11", False, False, RefundEligibilityReason.NOT_ELIGIBLE),
    )

    for label, redeme_enrolled, period_code, expected_last, expected_available, expected_reason in cases:
        period = _p(period_code)
        assert is_last_filing_period_of_year(period) is expected_last, label
        assert refund_disposition_available(redeme_enrolled=redeme_enrolled, period=period) is expected_available, label
        assert refund_eligibility_reason(redeme_enrolled=redeme_enrolled, period=period) is expected_reason, label
