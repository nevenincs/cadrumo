"""IVA compensation carry-forward modelling tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.period import Period
from ....domain.iva_compensation.carry_forward import (
    IvaCompensationCarryForwardLot,
    IvaCompensationExpiryReviewState,
    IvaCompensationPeriodState,
    build_iva_compensation_carry_forward_report,
    iva_compensation_year_opening_balance,
)
from ....domain.iva_compensation.reconciliation import IvaCompensationAuthoritySource, reconcile_iva_compensation_wallet
from ._iva_compensation_history_support import _TAXPAYER_REF, _state, _wallet, m303_registry_snapshot_ref

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_HISTORY_BUCKET_ID = "30330300-0000-4000-8000-000000000305"


def _local_recurrence_source_for_test(
    amount: Decimal,
    *,
    source_filing_year: int,
    source_period: str,
) -> IvaCompensationAuthoritySource:
    return IvaCompensationAuthoritySource(
        source_kind="local_recurrence",
        amount=amount,
        source_locator="local-recurrence:modelo-303-compensacion-pendiente-anteriores",
        captured_at=datetime(2026, 5, 19, 10, 0, tzinfo=UTC),
        source_modelo="303",
        source_filing_year=source_filing_year,
        source_periods=(Period.from_year_and_code(source_filing_year, source_period),),
        registry_snapshot_refs=(m303_registry_snapshot_ref(source_filing_year, source_period),),
    )


def test_iva_compensation_carry_forward_report_tracks_source_age_application_and_remaining_balance() -> None:
    report = build_iva_compensation_carry_forward_report(
        (
            _state(filing_year=2022, period="4T", generated=Decimal("113.00")),
            _state(filing_year=2023, period="2T", applied=Decimal("31.00")),
            _state(filing_year=2024, period="1T", generated=Decimal("47.00")),
        ),
        as_of_year=2026,
    )

    assert report.unallocated_applied_amount == Decimal("0")
    assert [(lot.source_filing_year, lot.source_period) for lot in report.lots] == [
        (2022, Period.from_year_and_code(2022, "4T")),
        (2024, Period.from_year_and_code(2024, "1T")),
    ]
    first, second = report.lots
    assert first.applied_amount == Decimal("31.00")
    assert first.remaining_amount == Decimal("82.00")
    assert first.age_years == 4
    assert first.expiry_review_state is IvaCompensationExpiryReviewState.EXPIRY_REVIEW_DUE
    assert second.applied_amount == Decimal("0")
    assert second.remaining_amount == Decimal("47.00")
    assert second.age_years == 2
    assert second.expiry_review_state is IvaCompensationExpiryReviewState.ACTIVE


def test_iva_compensation_carry_forward_report_marks_expired_review_required() -> None:
    report = build_iva_compensation_carry_forward_report(
        (_state(filing_year=2022, period="4T", generated=Decimal("100.00")),),
        as_of_year=2027,
    )

    assert report.lots[0].age_years == 5
    assert report.lots[0].expiry_review_state is IvaCompensationExpiryReviewState.EXPIRED_REVIEW_REQUIRED


def test_iva_compensation_carry_forward_report_preserves_unallocated_applications() -> None:
    report = build_iva_compensation_carry_forward_report(
        (_state(filing_year=2025, period="2T", applied=Decimal("25.00")),),
        as_of_year=2026,
    )

    assert report.lots == ()
    assert report.unallocated_applied_amount == Decimal("25.00")


def _year_with_opening_credit() -> tuple[IvaCompensationPeriodState, ...]:
    """A year that opens on 1000.00 of earlier credit.

    1T and 2T apply 105 and 630, 3T generates 420 and 4T applies 630.
    """
    return (
        _state(filing_year=2025, period="1T", applied=Decimal("105.00")),
        _state(filing_year=2025, period="2T", applied=Decimal("630.00")),
        _state(filing_year=2025, period="3T", generated=Decimal("420.00")),
        _state(filing_year=2025, period="4T", applied=Decimal("630.00")),
    )


def test_carry_forward_report_consumes_the_opening_balance_before_the_years_own_credit() -> None:
    report = build_iva_compensation_carry_forward_report(
        _year_with_opening_credit(),
        as_of_year=2025,
        opening_balance=Decimal("1000.00"),
    )

    # 105 + 630 + the first 265 of the 4T application.
    assert report.opening_applied_amount == Decimal("1000.00")
    assert report.unallocated_applied_amount == Decimal("0")
    (lot,) = report.lots
    assert lot.source_period == Period.from_year_and_code(2025, "3T")
    assert lot.applied_amount == Decimal("365.00")
    assert lot.remaining_amount == Decimal("55.00")


def test_carry_forward_report_without_an_opening_balance_charges_the_years_own_credit() -> None:
    report = build_iva_compensation_carry_forward_report(_year_with_opening_credit(), as_of_year=2025)

    assert report.opening_applied_amount == Decimal("0")
    # 105 + 630 find no lot; of the 4T 630, 420 exhausts the 3T lot and 210 finds none.
    assert report.unallocated_applied_amount == Decimal("945.00")
    (lot,) = report.lots
    assert lot.remaining_amount == Decimal("0")


def test_carry_forward_report_leaves_an_unconsumed_opening_balance_out_of_the_applied_amount() -> None:
    report = build_iva_compensation_carry_forward_report(
        (_state(filing_year=2025, period="1T", applied=Decimal("105.00")),),
        as_of_year=2025,
        opening_balance=Decimal("1000.00"),
    )

    assert report.opening_applied_amount == Decimal("105.00")
    assert report.unallocated_applied_amount == Decimal("0")


def test_year_opening_balance_reads_the_first_periods_pending_credit() -> None:
    states = (
        _state(filing_year=2024, period="4T", generated=Decimal("300.00")),
        _state(filing_year=2025, period="2T", applied=Decimal("50.00")),
        _state(filing_year=2025, period="1T", applied=Decimal("105.00"), prior_pending=Decimal("1000.00")),
    )

    assert iva_compensation_year_opening_balance(states, filing_year=2025) == Decimal("1000.00")


def test_year_opening_balance_rebuilds_box_110_from_boxes_87_and_78() -> None:
    first = _state(filing_year=2025, period="1T", applied=Decimal("105.00"), pending_for_later=Decimal("895.00"))

    assert iva_compensation_year_opening_balance((first,), filing_year=2025) == Decimal("1000.00")


def test_year_opening_balance_is_a_proven_zero_when_the_first_period_had_no_credit() -> None:
    first = _state(filing_year=2025, period="01", prior_pending=Decimal("0.00"))

    assert iva_compensation_year_opening_balance((first,), filing_year=2025) == Decimal("0.00")


@pytest.mark.parametrize(
    ("first_period", "prior_pending"),
    [
        pytest.param(None, None, id="no-state-for-the-year"),
        pytest.param("2T", Decimal("400.00"), id="first-period-missing"),
        pytest.param("1T", None, id="no-carry-captured"),
        pytest.param("1T", Decimal("-10.00"), id="negative-pending"),
    ],
)
def test_year_opening_balance_is_unknown_rather_than_zero(
    first_period: str | None,
    prior_pending: Decimal | None,
) -> None:
    states = (
        () if first_period is None else (_state(filing_year=2025, period=first_period, prior_pending=prior_pending),)
    )

    assert iva_compensation_year_opening_balance(states, filing_year=2025) is None


def test_multiyear_compensation_flow_covers_expiry_boundary_wallet_divergence_and_blocked_local_fallback() -> None:
    report = build_iva_compensation_carry_forward_report(
        (
            _state(filing_year=2022, period="4T", generated=Decimal("100.00")),
            _state(filing_year=2024, period="2T", applied=Decimal("40.00")),
        ),
        as_of_year=2026,
    )
    source_lot = report.lots[0]
    assert source_lot.source_filing_year == 2022
    assert source_lot.applied_amount == Decimal("40.00")
    assert source_lot.remaining_amount == Decimal("60.00")
    assert source_lot.expiry_review_state is IvaCompensationExpiryReviewState.EXPIRY_REVIEW_DUE

    divergent = reconcile_iva_compensation_wallet(
        taxpayer_nif=_TAXPAYER_REF,
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "2T"),
        target_registry_snapshot_ref=m303_registry_snapshot_ref(2026, "2T"),
        wallet=_wallet(Decimal("80.00")),
        local_recurrence_amount=source_lot.remaining_amount,
        local_recurrence_source=_local_recurrence_source_for_test(
            source_lot.remaining_amount,
            source_filing_year=source_lot.source_filing_year,
            source_period=source_lot.source_period.registry_token,
        ),
        decided_at=datetime(2026, 5, 19, 10, 0, tzinfo=UTC),
    )
    assert divergent.divergence == "wallet_higher"
    assert divergent.blocked is True

    fallback = reconcile_iva_compensation_wallet(
        taxpayer_nif=_TAXPAYER_REF,
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "2T"),
        target_registry_snapshot_ref=m303_registry_snapshot_ref(2026, "2T"),
        wallet=None,
        local_recurrence_amount=source_lot.remaining_amount,
        local_recurrence_source=_local_recurrence_source_for_test(
            source_lot.remaining_amount,
            source_filing_year=source_lot.source_filing_year,
            source_period=source_lot.source_period.registry_token,
        ),
        decided_at=datetime(2026, 5, 19, 10, 0, tzinfo=UTC),
    )
    assert fallback.selected_authority == "local_recurrence"
    assert fallback.selected_amount == Decimal("60.00")
    assert fallback.blocked is True


def test_iva_compensation_carry_forward_lot_rejects_unbalanced_amounts() -> None:
    with pytest.raises(ValidationError, match="must equal generated_amount"):
        IvaCompensationCarryForwardLot(
            taxpayer_nif=_TAXPAYER_REF,
            source_filing_year=2026,
            source_period=Period.from_year_and_code(2026, "1T"),
            generated_amount=Decimal("100.00"),
            applied_amount=Decimal("20.00"),
            remaining_amount=Decimal("90.00"),
            age_years=0,
            expiry_review_state=IvaCompensationExpiryReviewState.ACTIVE,
            source_observation_key="303:2026:1T:EXP",
        )
