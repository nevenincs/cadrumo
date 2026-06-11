"""IVA compensation history carry-forward modelling tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, ValidationError

from ....adapters.outbound.aeat.sede import IVA_COMPENSATION_WALLET_URL
from ....adapters.outbound.aeat.sede._schema import (
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    IvaCompensationWalletObservation,
    IvaCompensationWalletRow,
    ObservedCasillaValue,
)
from ....core import Period
from ....core.errors import ERROR_REGISTRY, build_error_envelope
from ....core.resources import resources
from ....domain.calculations.registry import CasillaObservation, RegistryModeloObservation
from ....domain.iva_compensation._carry_forward import (
    IvaCompensationCarryForwardLot,
    IvaCompensationExpiryReviewState,
    IvaCompensationPeriodState,
    build_iva_compensation_carry_forward_report,
    enforce_iva_compensation_four_year_window,
)
from ....domain.iva_compensation._errors import (
    IvaCompensationCarryForwardPolicyError,
    IvaCompensationDecimalParseError,
    IvaCompensationSeedConflictError,
    IvaCompensationYearRangeError,
)
from ....tests.secure_sql import isolated_runtime_profile
from .._errors import IvaCompensationModeloError
from .._iva_compensation_history import (
    IvaCompensationHistoryRepository,
    cross_check_iva_compensation_annual_summary,
    iva_compensation_annual_summary_from_filed_observation,
    iva_compensation_period_key,
    iva_compensation_state_from_filed_observation,
    seed_iva_compensation_period,
)
from .._iva_wallet_reconciliation import reconcile_iva_compensation_wallet
from .._observations_repository import CalculationObservationRepository
from .._relation_prefill import resolve_relations_from_local_store

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

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
        period=Period.from_year_and_code(filing_year, period),
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
        target_period=Period.from_year_and_code(2026, "2T"),
        rows=(
            IvaCompensationWalletRow(
                generation_year=generation_year,
                generation_period=Period.from_year_and_code(generation_year, "4T"),
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
        target_period=Period.from_year_and_code(2026, "2T"),
        wallet=_wallet(Decimal("80.00")),
        local_recurrence_amount=source_lot.remaining_amount,
        decided_at=datetime(2026, 5, 19, 10, 0, tzinfo=UTC),
    )
    assert divergent.divergence == "wallet_higher"
    assert divergent.blocked is True

    fallback = reconcile_iva_compensation_wallet(
        taxpayer_nif=_TAXPAYER_REF,
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "2T"),
        wallet=None,
        local_recurrence_amount=source_lot.remaining_amount,
        decided_at=datetime(2026, 5, 19, 10, 0, tzinfo=UTC),
    )
    assert fallback.selected_authority == "local_recurrence"
    assert fallback.selected_amount == Decimal("60.00")
    assert fallback.blocked is True


def test_modelo_390_annual_summary_cross_checks_multiyear_303_carry_forward() -> None:
    report = build_iva_compensation_carry_forward_report(
        (
            _state(filing_year=2026, period="1T", generated=Decimal("50.00")),
            _state(filing_year=2026, period="4T", generated=Decimal("100.00")),
        ),
        as_of_year=2026,
    )
    summary = iva_compensation_annual_summary_from_filed_observation(
        _filed_390_observation(
            last_period_compensation=Decimal("100.00"),
            generated_not_in_last_period=Decimal("50.00"),
        ),
    )

    cross_check = cross_check_iva_compensation_annual_summary(report, summary)

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
    assert cross_check.mismatched_casillas == ()
    assert cross_check.matches is True
    assert cross_check.summary_source_observation_key == "390:2026:0A:200039000000001Z"


def test_modelo_390_annual_summary_cross_check_flags_303_390_divergence() -> None:
    report = build_iva_compensation_carry_forward_report(
        (_state(filing_year=2026, period="4T", generated=Decimal("100.00")),),
        as_of_year=2026,
    )
    summary = iva_compensation_annual_summary_from_filed_observation(
        _filed_390_observation(
            last_period_compensation=Decimal("80.00"),
            generated_not_in_last_period=Decimal("0.00"),
        ),
    )

    cross_check = cross_check_iva_compensation_annual_summary(report, summary)

    assert cross_check.carry_forward_remaining_amount == Decimal("100.00")
    assert cross_check.modelo_390_total_pending_amount == Decimal("80.00")
    assert cross_check.expected_last_period_compensation_amount == Decimal("100.00")
    assert cross_check.expected_generated_not_in_last_period_amount == Decimal("0.00")
    assert cross_check.difference_amount == Decimal("20.00")
    assert cross_check.last_period_difference_amount == Decimal("20.00")
    assert cross_check.generated_not_in_last_period_difference_amount == Decimal("0.00")
    assert cross_check.mismatched_casillas == ("97",)
    assert cross_check.matches is False


def test_modelo_390_cross_check_keeps_active_prior_year_lots_out_of_annual_fields() -> None:
    report = build_iva_compensation_carry_forward_report(
        (
            _state(filing_year=2025, period="4T", generated=Decimal("25.00")),
            _state(filing_year=2026, period="4T", generated=Decimal("100.00")),
        ),
        as_of_year=2026,
    )
    summary = iva_compensation_annual_summary_from_filed_observation(
        _filed_390_observation(
            last_period_compensation=Decimal("100.00"),
            generated_not_in_last_period=Decimal("0.00"),
        ),
    )

    cross_check = cross_check_iva_compensation_annual_summary(report, summary)

    assert report.lots[0].expiry_review_state is IvaCompensationExpiryReviewState.ACTIVE
    assert cross_check.carry_forward_remaining_amount == Decimal("100.00")
    assert cross_check.expected_last_period_compensation_amount == Decimal("100.00")
    assert cross_check.expected_generated_not_in_last_period_amount == Decimal("0.00")
    assert cross_check.mismatched_casillas == ()
    assert cross_check.matches is True


def test_modelo_390_cross_check_keeps_expired_prior_year_lots_out_of_annual_fields() -> None:
    report = build_iva_compensation_carry_forward_report(
        (
            _state(filing_year=2021, period="4T", generated=Decimal("25.00")),
            _state(filing_year=2026, period="4T", generated=Decimal("100.00")),
        ),
        as_of_year=2026,
    )
    summary = iva_compensation_annual_summary_from_filed_observation(
        _filed_390_observation(
            last_period_compensation=Decimal("100.00"),
            generated_not_in_last_period=Decimal("0.00"),
        ),
    )

    cross_check = cross_check_iva_compensation_annual_summary(report, summary)

    assert report.lots[0].expiry_review_state is IvaCompensationExpiryReviewState.EXPIRED_REVIEW_REQUIRED
    assert cross_check.carry_forward_remaining_amount == Decimal("100.00")
    assert cross_check.modelo_390_total_pending_amount == Decimal("100.00")
    assert cross_check.expected_last_period_compensation_amount == Decimal("100.00")
    assert cross_check.expected_generated_not_in_last_period_amount == Decimal("0.00")
    assert cross_check.mismatched_casillas == ()
    assert cross_check.matches is True
    assert "expired_review_required" in cross_check.expiry_review_states


def test_modelo_390_compensation_bindings_resolve_from_secure_iva_history(tmp_path: Path) -> None:
    """M390←M303 bindings are now ``relation_prefill``; resolve via the relation path.

    The five M390←M303 fold bindings migrated from ``previous_filing`` to
    ``relation_prefill`` backed by ``cross_model_output`` relations.
    The compensación bindings (ultimo-periodo + generada-ejercicio-no-97) read
    ``iva.compensacion-generada-periodo`` from M303 casilla observations — not
    from the IVA compensation history repository.  This test verifies the
    relation resolver resolves all five bindings from M303 observations that
    include the compensación casilla.
    """
    # Quarter observations: (period, devengada, deducible, regimen_general, compensacion_generada)
    # The compensacion-generada-periodo casilla must be present so the
    # relation resolver can populate the two compensacion fold bindings.
    quarter_data = [
        ("1T", Decimal("100.00"), Decimal("40.00"), Decimal("60.00"), Decimal("20.00")),
        ("2T", Decimal("80.00"), Decimal("30.00"), Decimal("50.00"), Decimal("10.00")),
        ("3T", Decimal("120.00"), Decimal("50.00"), Decimal("70.00"), Decimal("20.00")),
        ("4T", Decimal("90.00"), Decimal("60.00"), Decimal("30.00"), Decimal("100.00")),
    ]
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="m390-compensation-history"):
        observation_repo = CalculationObservationRepository()
        for period, devengada, deducible, regimen_general, compensacion in quarter_data:
            observation_repo.save_observation(
                RegistryModeloObservation(
                    modelo="303",
                    filing_year=2026,
                    period=period,
                    observations=(
                        CasillaObservation(casilla_id="iva.cuota-devengada-total", value=devengada),
                        CasillaObservation(casilla_id="iva.cuota-deducible-total", value=deducible),
                        CasillaObservation(casilla_id="iva.resultado-regimen-general", value=regimen_general),
                        CasillaObservation(casilla_id="iva.compensacion-generada-periodo", value=compensacion),
                    ),
                ),
                source_kind="app_filing",
                captured_at=datetime(2027, 1, 30, 12, 0, tzinfo=UTC),
            )

        snapshot = resources().modelos.authority.snapshot("390", filing_year=2026, period="0A")
        relation_vals = resolve_relations_from_local_store(
            snapshot,
            repository=observation_repo,
            captured_at=datetime(2027, 1, 30, 12, 0, tzinfo=UTC),
        )

    from ....domain.calculations.registry import materialize_relation_binding_values

    relation_values_map = {rv.relation: rv.value for rv in relation_vals.values if rv.value is not None}
    resolved = materialize_relation_binding_values(snapshot.revision, relation_values_map, period="0A")

    # 100+80+120+90 = 390
    assert resolved["modelo-390-prev-303-cuota-devengada-total"] == Decimal("390.00")
    # 40+30+50+60 = 180
    assert resolved["modelo-390-prev-303-cuota-deducible-total"] == Decimal("180.00")
    # 60+50+70+30 = 210
    assert resolved["modelo-390-prev-303-resultado-regimen-general"] == Decimal("210.00")
    # compensacion-generada-no-97: sum of 1T+2T+3T = 20+10+20 = 50
    assert resolved["modelo-390-prev-303-compensacion-generada-ejercicio-no-97"] == Decimal("50.00")
    # compensacion-ultimo-periodo: copy of 4T = 100
    assert resolved["modelo-390-prev-303-compensacion-ultimo-periodo"] == Decimal("100.00")
    # All five resolved from local_filing provenance (no iva_history fallback needed)
    resolved_rels = {rv.relation for rv in relation_vals.values if rv.value is not None}
    assert resolved_rels >= {
        "modelo-390-rel-303-cuota-devengada-total",
        "modelo-390-rel-303-cuota-deducible-total",
        "modelo-390-rel-303-resultado-regimen-general",
        "modelo-390-rel-303-compensacion-ultimo-periodo",
        "modelo-390-rel-303-compensacion-generada-ejercicio-no-97",
    }
    assert all(rv.provenance == "local_filing" for rv in relation_vals.values if rv.value is not None)


def test_three_year_filed_history_repository_projects_compensation_lots(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="iva-history-three-year"):
        repository = IvaCompensationHistoryRepository()
        observations = (
            _filed_303_compensation_observation(
                filing_year=2024,
                period="4T",
                resultado=Decimal("-100.00"),
            ),
            _filed_303_compensation_observation(
                filing_year=2025,
                period="2T",
                resultado=Decimal("25.00"),
                applied=Decimal("40.00"),
                posterior=Decimal("60.00"),
            ),
            _filed_303_compensation_observation(
                filing_year=2025,
                period="4T",
                resultado=Decimal("-75.00"),
            ),
            _filed_303_compensation_observation(
                filing_year=2026,
                period="1T",
                resultado=Decimal("10.00"),
                applied=Decimal("20.00"),
                posterior=Decimal("115.00"),
            ),
        )

        for observation in observations:
            repository.save_period(iva_compensation_state_from_filed_observation(observation))

        reloaded = IvaCompensationHistoryRepository().list_periods()
        report = build_iva_compensation_carry_forward_report(reloaded, as_of_year=2026)
        enforce_iva_compensation_four_year_window(report)

    assert tuple(state.source_observation_key for state in reloaded) == (
        "303:2024:4T:20243034T000001",
        "303:2025:2T:20253032T000001",
        "303:2025:4T:20253034T000001",
        "303:2026:1T:20263031T000001",
    )
    assert [(state.filing_year, state.period) for state in reloaded] == [
        (2024, Period.from_year_and_code(2024, "4T")),
        (2025, Period.from_year_and_code(2025, "2T")),
        (2025, Period.from_year_and_code(2025, "4T")),
        (2026, Period.from_year_and_code(2026, "1T")),
    ]
    assert [
        (
            lot.source_filing_year,
            lot.source_period,
            lot.generated_amount,
            lot.applied_amount,
            lot.remaining_amount,
            lot.expiry_review_state,
        )
        for lot in report.lots
    ] == [
        (
            2024,
            Period.from_year_and_code(2024, "4T"),
            Decimal("100.00"),
            Decimal("60.00"),
            Decimal("40.00"),
            IvaCompensationExpiryReviewState.ACTIVE,
        ),
        (
            2025,
            Period.from_year_and_code(2025, "4T"),
            Decimal("75.00"),
            Decimal("0"),
            Decimal("75.00"),
            IvaCompensationExpiryReviewState.ACTIVE,
        ),
    ]
    assert report.unallocated_applied_amount == Decimal("0")


def _filed_303_annual_reconciliation_observation(
    *,
    filing_year: int,
    period: str,
    devengada: Decimal,
    deducible: Decimal,
    regimen_general: Decimal,
) -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo="303",
        filing_year=filing_year,
        period=period,
        observations=(
            CasillaObservation(casilla_id="iva.cuota-devengada-total", value=devengada),
            CasillaObservation(casilla_id="iva.cuota-deducible-total", value=deducible),
            CasillaObservation(casilla_id="iva.resultado-regimen-general", value=regimen_general),
        ),
    )


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


def _filed_observation(modelo: str) -> FiledDeclaracionObservation:
    """Construct a minimal valid FiledDeclaracionObservation for the given modelo."""
    return FiledDeclaracionObservation(
        modelo=modelo,
        ejercicio=2024,
        period=Period.from_year_and_code(2024, "4T"),
        expediente_id="202410013522456T",
        status="filed",
        presented_at=datetime(2025, 1, 20, 12, 0, tzinfo=UTC),
        authenticated_identity=_TAXPAYER_REF,
        artefacts=(
            FiledDeclaracionArtefact(
                kind="register_row",
                source_url=AnyHttpUrl("https://example.test/expedientes/test"),
                content_type="text/html",
                byte_count=0,
                sha256="a" * 64,
                captured_at=datetime(2025, 1, 20, 12, 0, tzinfo=UTC),
            ),
        ),
    )


def _filed_303_compensation_observation(
    *,
    filing_year: int,
    period: str,
    resultado: Decimal,
    prior_pending: Decimal = Decimal("0.00"),
    applied: Decimal = Decimal("0.00"),
    posterior: Decimal = Decimal("0.00"),
    final_result: Decimal | None = None,
) -> FiledDeclaracionObservation:
    resolved_final_result = resultado if final_result is None else final_result
    return _filed_observation(modelo="303").model_copy(
        update={
            "ejercicio": filing_year,
            "period": Period.from_year_and_code(filing_year, period),
            "expediente_id": f"{filing_year}303{period}000001",
            "presented_at": datetime(filing_year + 1, 1, 20, 12, 0, tzinfo=UTC),
            "casillas": (
                ObservedCasillaValue(
                    casilla_id="110",
                    value=str(prior_pending),
                    source_artefact_kind="submitted_file",
                    source_locator=f"submitted-file:303:{period}:110",
                    confidence=1.0,
                ),
                ObservedCasillaValue(
                    casilla_id="78",
                    value=str(applied),
                    source_artefact_kind="submitted_file",
                    source_locator=f"submitted-file:303:{period}:78",
                    confidence=1.0,
                ),
                ObservedCasillaValue(
                    casilla_id="69",
                    value=str(resultado),
                    source_artefact_kind="submitted_file",
                    source_locator=f"submitted-file:303:{period}:69",
                    confidence=1.0,
                ),
                ObservedCasillaValue(
                    casilla_id="87",
                    value=str(posterior),
                    source_artefact_kind="submitted_file",
                    source_locator=f"submitted-file:303:{period}:87",
                    confidence=1.0,
                ),
                ObservedCasillaValue(
                    casilla_id="71",
                    value=str(resolved_final_result),
                    source_artefact_kind="submitted_file",
                    source_locator=f"submitted-file:303:{period}:71",
                    confidence=1.0,
                ),
            ),
        },
    )


def _filed_390_observation(
    *,
    last_period_compensation: Decimal,
    generated_not_in_last_period: Decimal,
) -> FiledDeclaracionObservation:
    return FiledDeclaracionObservation(
        modelo="390",
        ejercicio=2026,
        period=Period.from_year_and_code(2026, "0A"),
        expediente_id="200039000000001Z",
        status="filed",
        presented_at=datetime(2027, 1, 30, 12, 0, tzinfo=UTC),
        authenticated_identity=_TAXPAYER_REF,
        artefacts=(
            FiledDeclaracionArtefact(
                kind="submitted_file",
                source_url=AnyHttpUrl("https://example.test/390/submitted-file/test"),
                content_type="text/plain",
                byte_count=0,
                sha256="b" * 64,
                captured_at=datetime(2027, 1, 30, 12, 0, tzinfo=UTC),
            ),
        ),
        casillas=(
            ObservedCasillaValue(
                casilla_id="iva.anual.compensacion-ultimo-periodo-97",
                value=str(last_period_compensation),
                source_artefact_kind="submitted_file",
                source_locator="submitted-file:390:97",
                confidence=1.0,
            ),
            ObservedCasillaValue(
                casilla_id="iva.anual.compensacion-generada-ejercicio-no-97",
                value=str(generated_not_in_last_period),
                source_artefact_kind="submitted_file",
                source_locator="submitted-file:390:662",
                confidence=1.0,
            ),
        ),
    )


def test_iva_compensation_modelo_error_is_registered_in_error_registry() -> None:
    assert "REFUSED_IVA_COMPENSATION_MODELO" in ERROR_REGISTRY


def test_iva_compensation_modelo_error_round_trips_through_build_error_envelope() -> None:
    exc = IvaCompensationModeloError(
        translated_message="application.calculations.iva_compensation.errors.modelo_303_only",
        context={"modelo": "130"},
    )
    envelope = build_error_envelope(exc, trace_id=None)
    assert envelope.code == "REFUSED_IVA_COMPENSATION_MODELO"
    assert envelope.retryable is False
    assert envelope.suggestion == "aeat app live iva-wallet history"
    assert envelope.message != "IVA compensation history only accepts Modelo 303 observations"


def test_iva_compensation_state_from_filed_observation_raises_for_non_303_modelo() -> None:
    observation = _filed_observation(modelo="130")
    with pytest.raises(IvaCompensationModeloError) as excinfo:
        iva_compensation_state_from_filed_observation(observation)

    assert excinfo.value.translated_message == "application.calculations.iva_compensation.errors.modelo_303_only"
    assert excinfo.value.context == {"modelo": "130"}


def test_iva_compensation_period_key_raises_localized_year_range_error() -> None:
    with pytest.raises(IvaCompensationYearRangeError) as excinfo:
        iva_compensation_period_key(Period.from_year_and_code(1999, "1T"))

    assert excinfo.value.translated_message == "errors.refused.refused_iva_compensation_year_range"
    assert excinfo.value.context == {"filing_year": 1999, "min_year": 2000, "max_year": 2099}


def test_iva_compensation_state_from_filed_observation_raises_localized_decimal_parse_error() -> None:
    observation = _filed_observation(modelo="303").model_copy(
        update={
            "casillas": (
                ObservedCasillaValue(
                    casilla_id="69",
                    value="not-decimal",
                    source_artefact_kind="submitted_file",
                    source_locator="submitted-file:casilla-69",
                    confidence=1.0,
                ),
            ),
        },
    )

    with pytest.raises(IvaCompensationDecimalParseError) as excinfo:
        iva_compensation_state_from_filed_observation(observation)

    assert excinfo.value.translated_message == "errors.refused.refused_iva_compensation_decimal_parse"
    assert excinfo.value.context == {"casilla_id": "69"}


def test_seed_iva_compensation_period_raises_localized_conflict_error(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="iva-compensation-conflict"):
        seed_iva_compensation_period(
            taxpayer_nif=_TAXPAYER_REF,
            period=Period.from_year_and_code(2024, "2T"),
            amount=Decimal("100.00"),
        )

        with pytest.raises(IvaCompensationSeedConflictError) as excinfo:
            seed_iva_compensation_period(
                taxpayer_nif=_TAXPAYER_REF,
                period=Period.from_year_and_code(2024, "2T"),
                amount=Decimal("50.00"),
            )

        assert excinfo.value.translated_message == "application.calculations.iva_compensation.errors.seed_conflict"
        assert excinfo.value.context == {"filing_year": 2024, "period": "2T", "existing_status": "seeded"}
