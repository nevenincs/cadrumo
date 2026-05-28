"""IVA compensation history carry-forward modelling tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import AnyHttpUrl, ValidationError

from ...adapters.outbound.aeat.sede import IVA_COMPENSATION_WALLET_URL
from ...adapters.outbound.aeat.sede._schema import (
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    IvaCompensationWalletObservation,
    IvaCompensationWalletRow,
)
from ...core.errors import ERROR_REGISTRY, build_error_envelope
from ._errors import IvaCompensationModeloError
from ._iva_compensation_history import (
    IvaCompensationCarryForwardLot,
    IvaCompensationCarryForwardPolicyError,
    IvaCompensationExpiryReviewState,
    IvaCompensationPeriodState,
    build_iva_compensation_carry_forward_report,
    enforce_iva_compensation_four_year_window,
    iva_compensation_state_from_filed_observation,
)
from ._iva_wallet_reconciliation import reconcile_iva_compensation_wallet

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_TAXPAYER_REF = "taxpayeralpha"


def _state(
    *,
    filing_year: int,
    period: str,
    generated: Decimal = Decimal("0.00"),
    applied: Decimal = Decimal("0.00"),
    available: Decimal | None = None,
) -> IvaCompensationPeriodState:
    return IvaCompensationPeriodState(
        taxpayer_nif=_TAXPAYER_REF,
        filing_year=filing_year,
        period=period,
        expediente_id=f"EXP-{filing_year}-{period}",
        status="filed",
        presented_at=datetime(filing_year + 1, 1, 20, 12, 0, tzinfo=UTC),
        prior_pending_amount=None,
        applied_amount=applied,
        pending_for_later_amount=None,
        period_result_amount=None,
        final_result_amount=None,
        generated_amount=generated,
        available_end_amount=generated if available is None else available,
        source_observation_key=f"303:{filing_year}:{period}:EXP",
    )


def _wallet(amount: Decimal, *, generation_year: int = 2022) -> IvaCompensationWalletObservation:
    return IvaCompensationWalletObservation(
        taxpayer_nif=_TAXPAYER_REF,
        authenticated_identity=_TAXPAYER_REF,
        target_year=2026,
        target_period="2T",
        rows=(
            IvaCompensationWalletRow(
                generation_year=generation_year,
                generation_period="4T",
                generated_amount=amount,
                applied_amount=Decimal("0"),
                pending_amount=amount,
                raw_label=f"{generation_year} 4T",
            ),
        ),
        total_pending=amount,
        source_url=AnyHttpUrl(IVA_COMPENSATION_WALLET_URL),
        captured_at=datetime(2026, 5, 19, 10, 0, tzinfo=UTC),
        raw_sha256="a" * 64,
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
    assert [(lot.source_filing_year, lot.source_period) for lot in report.lots] == [(2022, "4T"), (2024, "1T")]
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
        (_state(filing_year=2021, period="4T", generated=Decimal("100.00")),),
        as_of_year=2026,
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


def test_iva_compensation_four_year_window_blocks_expired_remaining_lot() -> None:
    report = build_iva_compensation_carry_forward_report(
        (_state(filing_year=2021, period="4T", generated=Decimal("100.00")),),
        as_of_year=2026,
    )

    with pytest.raises(IvaCompensationCarryForwardPolicyError, match="2021/4T"):
        enforce_iva_compensation_four_year_window(report)


def test_iva_compensation_four_year_window_allows_fully_applied_expired_lot() -> None:
    report = build_iva_compensation_carry_forward_report(
        (
            _state(filing_year=2021, period="4T", generated=Decimal("100.00")),
            _state(filing_year=2024, period="1T", applied=Decimal("100.00")),
        ),
        as_of_year=2026,
    )

    assert enforce_iva_compensation_four_year_window(report) is report
    assert report.lots[0].remaining_amount == Decimal("0.00")


def test_multiyear_compensation_flow_covers_expiry_boundary_wallet_divergence_and_blocked_local_fallback() -> None:
    report = build_iva_compensation_carry_forward_report(
        (
            _state(filing_year=2022, period="4T", generated=Decimal("100.00")),
            _state(filing_year=2024, period="2T", applied=Decimal("40.00")),
        ),
        as_of_year=2026,
    )
    enforce_iva_compensation_four_year_window(report)
    source_lot = report.lots[0]
    assert source_lot.source_filing_year == 2022
    assert source_lot.applied_amount == Decimal("40.00")
    assert source_lot.remaining_amount == Decimal("60.00")
    assert source_lot.expiry_review_state is IvaCompensationExpiryReviewState.EXPIRY_REVIEW_DUE

    divergent = reconcile_iva_compensation_wallet(
        taxpayer_nif=_TAXPAYER_REF,
        target_year=2026,
        target_period="2T",
        wallet=_wallet(Decimal("80.00")),
        local_recurrence_amount=source_lot.remaining_amount,
        decided_at=datetime(2026, 5, 19, 10, 0, tzinfo=UTC),
    )
    assert divergent.divergence == "wallet_higher"
    assert divergent.blocked is True

    fallback = reconcile_iva_compensation_wallet(
        taxpayer_nif=_TAXPAYER_REF,
        target_year=2026,
        target_period="2T",
        wallet=None,
        local_recurrence_amount=source_lot.remaining_amount,
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
            source_period="1T",
            generated_amount=Decimal("100.00"),
            applied_amount=Decimal("20.00"),
            remaining_amount=Decimal("90.00"),
            age_years=0,
            expiry_review_state=IvaCompensationExpiryReviewState.ACTIVE,
            source_observation_key="303:2026:1T:EXP",
        )


def _filed_observation(modelo: str) -> FiledDeclaracionObservation:
    """Construct a minimal valid FiledDeclaracionObservation for the given modelo."""
    return FiledDeclaracionObservation(
        modelo=modelo,
        ejercicio=2024,
        period="4T",
        expediente_id="202410013522456T",
        status="filed",
        presented_at=datetime(2025, 1, 20, 12, 0, tzinfo=UTC),
        authenticated_identity=_TAXPAYER_REF,
        artefacts=(
            FiledDeclaracionArtefact(
                kind="register_row",
                source_url=AnyHttpUrl("https://sede.agenciatributaria.gob.es/expedientes/test"),
                content_type="text/html",
                byte_count=0,
                sha256="a" * 64,
                captured_at=datetime(2025, 1, 20, 12, 0, tzinfo=UTC),
            ),
        ),
    )


def test_iva_compensation_modelo_error_is_registered_in_error_registry() -> None:
    assert "REFUSED_IVA_COMPENSATION_MODELO" in ERROR_REGISTRY


def test_iva_compensation_modelo_error_round_trips_through_build_error_envelope() -> None:
    exc = IvaCompensationModeloError(
        "IVA compensation history only accepts Modelo 303 observations"
    )
    envelope = build_error_envelope(exc, trace_id=None)
    assert envelope.code == "REFUSED_IVA_COMPENSATION_MODELO"
    assert envelope.retryable is False
    assert envelope.suggestion == "aeat app live iva-wallet history"


def test_iva_compensation_state_from_filed_observation_raises_for_non_303_modelo() -> None:
    observation = _filed_observation(modelo="130")
    with pytest.raises(IvaCompensationModeloError, match="Modelo 303"):
        iva_compensation_state_from_filed_observation(observation)
