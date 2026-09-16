"""Modelo 390 IVA compensation annual summary tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.period import Period
from ....domain.iva_compensation.carry_forward import (
    IvaCompensationExpiryReviewState,
    build_iva_compensation_carry_forward_report,
    derive_iva_compensation_year_end_carry_partition,
    iva_compensation_period_sort_key,
)
from ._iva_compensation_history_support import (
    _state,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_PRIOR_YEAR_390_CROSS_CHECK_CASES: tuple[
    tuple[int, int, IvaCompensationExpiryReviewState, tuple[str, ...]],
    ...,
] = (
    (2024, 2025, IvaCompensationExpiryReviewState.ACTIVE, ("active", "active")),
    (
        2022,
        2027,
        IvaCompensationExpiryReviewState.EXPIRED_REVIEW_REQUIRED,
        ("expired_review_required", "active"),
    ),
)


def test_year_end_carry_partition_carried_pending_satisfies_aeat_identity_no_double_count() -> None:
    """Carried-pending FIFO scenario: box 97 + box 662 = total pending, counted once.

    The case both pre-fix relations get wrong. 1T generates 100 carried forward;
    2T applies 30 of it (70 remains, carries on); 4T generates 50. Everything
    still pending (70 + 50 = 120) carries into 4T's autoliquidación, so the FIFO
    partition puts ALL of it in box 97 and box 662 is zero.

    Non-tautological oracle: the per-period relations would emit box 97 = 4T
    generada = 50 and box 662 = sum(1T-3T generada) = 100 → 150, which both
    DOUBLE-COUNTS the 30 already applied and mis-splits the carry. The AEAT
    identity demands box 97 + box 662 == the year's total pending remaining
    (120), counted once. This asserts that identity against the FIFO total, not
    a per-period sum.
    """
    states = (
        _state(filing_year=2026, period="1T", generated=Decimal("100.00"), available=Decimal("100.00")),
        _state(filing_year=2026, period="2T", applied=Decimal("30.00"), available=Decimal("70.00")),
        _state(filing_year=2026, period="3T", available=Decimal("70.00")),
        _state(filing_year=2026, period="4T", generated=Decimal("50.00"), available=Decimal("120.00")),
    )
    report = build_iva_compensation_carry_forward_report(states, as_of_year=2026)

    partition = derive_iva_compensation_year_end_carry_partition(report, states, filing_year=2026)

    total_pending = sum((lot.remaining_amount for lot in report.lots if lot.source_filing_year == 2026), Decimal("0"))
    assert total_pending == states[-1].available_end_amount
    assert partition.last_period_amount + partition.generated_not_in_last_amount == total_pending
    assert partition.last_period_amount == total_pending
    assert partition.generated_not_in_last_amount == Decimal("0.00")
    naive_per_period = Decimal("50.00") + Decimal("100.00")
    assert partition.last_period_amount + partition.generated_not_in_last_amount != naive_per_period


def test_year_end_carry_partition_uncarried_credit_lands_in_box_662() -> None:
    """A year credit NOT carried into the last period lands in box 662, not box 97.

    1T generates 40 that does NOT carry into the 4T autoliquidación (it left the
    chain — e.g. refunded mid-year), so 4T's disponible (100) carries only its
    own credit. The year's total pending is 140; box 97 holds the last period's
    carry (100) and box 662 holds the uncarried year credit (40). This is the
    control where box 97 = last-period carry and box 662 = the rest, and it must
    still satisfy the identity.
    """
    states = (
        _state(filing_year=2026, period="1T", generated=Decimal("40.00"), available=Decimal("40.00")),
        _state(filing_year=2026, period="4T", generated=Decimal("100.00"), available=Decimal("100.00")),
    )
    report = build_iva_compensation_carry_forward_report(states, as_of_year=2026)

    partition = derive_iva_compensation_year_end_carry_partition(report, states, filing_year=2026)

    total_pending = sum((lot.remaining_amount for lot in report.lots if lot.source_filing_year == 2026), Decimal("0"))
    assert partition.last_period_amount == states[1].available_end_amount
    assert partition.generated_not_in_last_amount == states[0].generated_amount
    assert partition.last_period_amount + partition.generated_not_in_last_amount == total_pending


def test_iva_period_sort_key_places_annual_0a_after_periodic_rows() -> None:
    """The generic annual period sorts last even though its span starts in January."""
    annual = Period.from_year_and_code(2026, "0A")
    fourth_quarter = Period.from_year_and_code(2026, "4T")
    december = Period.from_year_and_code(2026, "12")

    assert iva_compensation_period_sort_key(annual) > iva_compensation_period_sort_key(fourth_quarter)
    assert iva_compensation_period_sort_key(annual) > iva_compensation_period_sort_key(december)
