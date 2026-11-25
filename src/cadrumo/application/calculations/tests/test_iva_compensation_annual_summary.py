"""Modelo 390 IVA compensation annual summary tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.iva_compensation.carry_forward import (
    IvaCompensationExpiryReviewState,
    build_iva_compensation_carry_forward_report,
    derive_iva_compensation_year_end_carry_partition,
    iva_compensation_period_sort_key,
)
from .iva_compensation_history_support import (
    state,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


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


def test_year_end_carry_partition_keeps_the_last_period_result_apart_from_carried_credit(
    operation: PinnedAuthorityOperation,
) -> None:
    """Box 97 holds the last period's own result; credit of earlier periods carried through it is box 662.

    1T generates 100; 2T applies 30, leaving 70; 4T generates 50, so 120 is
    pending at year end. Manual IVA 2025 p. 278, with 500 generated in 3T and 200
    in 4T: "Casilla 97: 200", "Casilla 662: 500". Here box 97 is 50 and box 662 is
    70, and the two still account for the 120 once.
    """
    states = (
        state(filing_year=2026, period="1T", generated=Decimal("100.00"), available=Decimal("100.00")),
        state(filing_year=2026, period="2T", applied=Decimal("30.00"), available=Decimal("70.00")),
        state(filing_year=2026, period="3T", available=Decimal("70.00")),
        state(filing_year=2026, period="4T", generated=Decimal("50.00"), available=Decimal("120.00")),
    )
    report = build_iva_compensation_carry_forward_report(states, as_of_year=2026, operation=operation)

    partition = derive_iva_compensation_year_end_carry_partition(report, states, filing_year=2026)

    assert partition.last_period_amount == Decimal("50.00")
    assert partition.generated_not_in_last_amount == Decimal("70.00")
    assert partition.total_year_remaining_amount == states[-1].available_end_amount


def test_year_end_carry_partition_uncarried_credit_lands_in_box_662(
    operation: PinnedAuthorityOperation,
) -> None:
    """A year credit NOT carried into the last period lands in box 662, not box 97.

    1T generates 40 that does NOT carry into the 4T autoliquidación (it left the
    chain — e.g. refunded mid-year), so 4T's disponible (100) carries only its
    own credit. The year's total pending is 140; box 97 holds the last period's
    carry (100) and box 662 holds the uncarried year credit (40). This is the
    control where box 97 = last-period carry and box 662 = the rest, and it must
    still satisfy the identity.
    """
    states = (
        state(filing_year=2026, period="1T", generated=Decimal("40.00"), available=Decimal("40.00")),
        state(filing_year=2026, period="4T", generated=Decimal("100.00"), available=Decimal("100.00")),
    )
    report = build_iva_compensation_carry_forward_report(states, as_of_year=2026, operation=operation)

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
