"""Modelo 390 IVA compensation annual summary tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....domain.iva_compensation.carry_forward import (
    IvaCompensationExpiryReviewState,
    build_iva_compensation_carry_forward_report,
    derive_iva_compensation_year_end_carry_partition,
)
from ..iva_compensation_history import (
    cross_check_iva_compensation_annual_summary,
    iva_compensation_annual_summary_from_filed_observation,
)
from ._iva_compensation_history_support import (
    _M390_COMPENSACION_ULTIMO_PERIODO_CASILLA,
    _filed_390_observation,
    _state,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_modelo_390_annual_summary_cross_checks_multiyear_303_carry_forward() -> None:
    states = (
        _state(filing_year=2025, period="1T", generated=Decimal("50.00")),
        _state(filing_year=2025, period="4T", generated=Decimal("100.00")),
    )
    report = build_iva_compensation_carry_forward_report(states, as_of_year=2025)
    summary = iva_compensation_annual_summary_from_filed_observation(
        _filed_390_observation(
            last_period_compensation=Decimal("100.00"),
            generated_not_in_last_period=Decimal("50.00"),
        ),
    )

    cross_check = cross_check_iva_compensation_annual_summary(report, summary, period_states=states)

    assert summary.last_period_compensation_amount == Decimal("100.00")
    assert summary.generated_not_in_last_period_amount == Decimal("50.00")
    assert summary.total_pending_amount == Decimal("150.00")
    assert cross_check.carry_forward_remaining_amount == Decimal("150.00")
    assert cross_check.modelo_390_total_pending_amount == Decimal("150.00")
    assert cross_check.expected_last_period_compensation_amount == Decimal("100.00")
    assert cross_check.expected_generated_not_in_last_period_amount == Decimal("50.00")
    assert cross_check.difference_amount == Decimal("0.00")
    assert cross_check.last_period_difference_amount == Decimal("0.00")
    assert cross_check.generated_not_in_last_period_difference_amount == Decimal("0.00")
    assert cross_check.mismatched_casilla_ids == ()
    assert cross_check.matches is True
    assert cross_check.summary_source_observation_key == "390:2025:0A:200039000000001Z"


def test_modelo_390_annual_summary_cross_check_flags_303_390_divergence() -> None:
    states = (_state(filing_year=2025, period="4T", generated=Decimal("100.00")),)
    report = build_iva_compensation_carry_forward_report(states, as_of_year=2025)
    summary = iva_compensation_annual_summary_from_filed_observation(
        _filed_390_observation(
            last_period_compensation=Decimal("80.00"),
            generated_not_in_last_period=Decimal("0.00"),
        ),
    )

    cross_check = cross_check_iva_compensation_annual_summary(report, summary, period_states=states)

    assert cross_check.carry_forward_remaining_amount == Decimal("100.00")
    assert cross_check.modelo_390_total_pending_amount == Decimal("80.00")
    assert cross_check.expected_last_period_compensation_amount == Decimal("100.00")
    assert cross_check.expected_generated_not_in_last_period_amount == Decimal("0.00")
    assert cross_check.difference_amount == Decimal("20.00")
    assert cross_check.last_period_difference_amount == Decimal("20.00")
    assert cross_check.generated_not_in_last_period_difference_amount == Decimal("0.00")
    assert cross_check.mismatched_casilla_ids == (_M390_COMPENSACION_ULTIMO_PERIODO_CASILLA,)
    assert cross_check.matches is False


_PRIOR_YEAR_390_CROSS_CHECK_CASES: tuple[
    tuple[int, IvaCompensationExpiryReviewState, tuple[str, ...]],
    ...,
] = (
    (2024, IvaCompensationExpiryReviewState.ACTIVE, ("active", "active")),
    (
        2020,
        IvaCompensationExpiryReviewState.EXPIRED_REVIEW_REQUIRED,
        ("expired_review_required", "active"),
    ),
)


@pytest.mark.parametrize(
    ("prior_year", "prior_year_expiry_state", "expiry_review_states"),
    _PRIOR_YEAR_390_CROSS_CHECK_CASES,
    ids=("active-prior-year", "expired-prior-year"),
)
def test_modelo_390_cross_check_keeps_prior_year_lots_out_of_annual_fields(
    prior_year: int,
    prior_year_expiry_state: IvaCompensationExpiryReviewState,
    expiry_review_states: tuple[str, ...],
) -> None:
    states = (
        _state(filing_year=prior_year, period="4T", generated=Decimal("25.00")),
        _state(filing_year=2025, period="4T", generated=Decimal("100.00")),
    )
    report = build_iva_compensation_carry_forward_report(states, as_of_year=2025)
    summary = iva_compensation_annual_summary_from_filed_observation(
        _filed_390_observation(
            last_period_compensation=Decimal("100.00"),
            generated_not_in_last_period=Decimal("0.00"),
        ),
    )

    cross_check = cross_check_iva_compensation_annual_summary(report, summary, period_states=states)

    assert report.lots[0].expiry_review_state is prior_year_expiry_state
    assert cross_check.carry_forward_remaining_amount == Decimal("100.00")
    assert cross_check.modelo_390_total_pending_amount == Decimal("100.00")
    assert cross_check.expected_last_period_compensation_amount == Decimal("100.00")
    assert cross_check.expected_generated_not_in_last_period_amount == Decimal("0.00")
    assert cross_check.mismatched_casilla_ids == ()
    assert cross_check.matches is True
    assert cross_check.expiry_review_states == expiry_review_states


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


def test_year_end_carry_partition_treats_annual_0a_as_after_periodic_iva_rows() -> None:
    """The annual IVA state is the last filing even though its span starts in January."""
    states = (
        _state(filing_year=2026, period="0A", available=Decimal("70.00")),
        _state(filing_year=2026, period="4T", generated=Decimal("100.00"), available=Decimal("100.00")),
    )
    report = build_iva_compensation_carry_forward_report(states, as_of_year=2026)

    partition = derive_iva_compensation_year_end_carry_partition(report, states, filing_year=2026)

    assert partition.last_period_amount == Decimal("70.00")
    assert partition.generated_not_in_last_amount == Decimal("30.00")
    assert partition.total_year_remaining_amount == Decimal("100.00")
