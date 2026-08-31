"""Application tests for previous-filing binding prefill."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from ....adapters.persistence.profile.bienes_inversion import BienesInversionIvaRegisterRepository
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.errors.error_codes import ERROR_REGISTRY, build_error_envelope
from ....core.iva_compensation_provenance import IvaCompensationStateProvenance
from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....core.period import Period
from ....core.result_disposition import derive_result_disposition, result_disposition_casilla_ids
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import (
    RegistryModeloObservation,
    resolve_available_bound_inputs_by_casilla_id,
)
from ....domain.calculations.registry.formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from ....domain.calculations.registry.ledger_iva_bindings import (
    IvaLedgerObservation,
    resolve_ledger_iva_aggregation_binding_values,
)
from ....domain.calculations.registry.relations import materialize_relation_binding_values
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva.flow import IvaFlowDirection
from ....domain.iva.schema import IvaCategory, IvaLedgerObservationRole, IvaRateKind
from ....domain.iva_compensation.carry_forward import IvaCompensationPeriodState
from ....domain.iva_compensation.errors import IvaCompensationCasillaReferenceError
from ....tests.secure_sql import isolated_runtime_profile
from ...aggregation import CalculationSourceContext
from .._bienes_inversion_regularizacion import BienesInversionRegularizacionSourceResolver
from .._binding_prefill import (
    _iva_compensation_history_observation,
    _observation_from_iva_compensation_history,
    _selector_periods,
    _selector_year_delta,
    extract_modelo_303_local_iva_compensation_recurrence,
    resolve_bindings_from_local_store,
)
from .._iva_compensation_annual_partition import IvaCompensationAnnualPartitionSourceResolver
from .._relation_prefill import resolve_relations_from_local_store
from ..errors import BindingPrefillTypeError
from ..iva_compensation_history import IvaCompensationHistoryRepository
from ..observations_repository import CalculationObservationRepository, ResultDispositionProjection

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_M390_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.anual.cuota-devengada-total")
_M390_CUOTA_DEDUCIBLE_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.anual.cuota-deducible-total")
_M390_RESULTADO_REGIMEN_GENERAL_CASILLA: CasillaId = validated_casilla_id("iva.anual.resultado-regimen-general")
_M390_RECONCILIACION_DEVENGADA_303_CASILLA: CasillaId = validated_casilla_id("iva.anual.reconciliacion.devengada-303")
_M390_RECONCILIACION_DEDUCIBLE_303_CASILLA: CasillaId = validated_casilla_id("iva.anual.reconciliacion.deducible-303")
_M390_RECONCILIACION_RESULTADO_303_CASILLA: CasillaId = validated_casilla_id("iva.anual.reconciliacion.resultado-303")
_M303_RESULTADO_CASILLA: CasillaId = validated_casilla_id("iva.resultado")
_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-pendiente-periodos-anteriores"
)
_M303_COMPENSACION_APLICADA_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-aplicada-periodo")
_M303_POSTERIOR_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-pendiente-periodos-posteriores")
_M303_GENERADA_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-generada-periodo")
_M303_DISPONIBLE_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-disponible-fin-periodo")


@cache
def _snapshot(modelo: str, filing_year: int, period: str) -> RegistrySnapshot:
    return bundled_authority().snapshot(modelo, filing_year=filing_year, period=period)


def test_m130_first_year_activity_start_prefills_prior_year_m100_as_no_prior_obligation(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        snapshot = _snapshot("130", 2026, "1T")
        empty_report = resolve_bindings_from_local_store(
            snapshot,
            repository=CalculationObservationRepository(),
        )
        scoped_report = resolve_bindings_from_local_store(
            snapshot,
            repository=CalculationObservationRepository(),
            activity_start_date=date(2026, 1, 1),
        )

    binding_id = "irpf.previous_year_economic_activity_net_income"
    assert binding_id not in empty_report.binding_values
    assert scoped_report.binding_values[binding_id] == Decimal("0")
    prefilled = {item.binding_id: item for item in scoped_report.prefilled}
    assert prefilled[binding_id].source_kind == "pre_activity_no_prior_obligation"
    assert prefilled[binding_id].source_modelo == "100"
    assert prefilled[binding_id].source_filing_year == 2025
    assert prefilled[binding_id].source_periods == ("0A",)


def _observation(
    *,
    ledger_id: str,
    txn_date: date,
    flow: IvaFlowDirection = IvaFlowDirection.REPERCUTIDO,
    iva: Decimal,
) -> IvaLedgerObservation:
    deduction_fact_kind: IvaDeductionFactKind | None = None
    deduction_provenance: IvaDeductionClassificationProvenance | None = None
    if flow is IvaFlowDirection.SOPORTADO:
        deduction_fact_kind = IvaDeductionFactKind.DOMESTIC_CURRENT
        deduction_provenance = IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
            source_locator=f"invoice:{ledger_id}",
            evidence_digest="d" * 64,
        )
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=txn_date,
        category=IvaCategory.DOMESTIC_GENERAL,
        rate_kind=IvaRateKind.GENERAL,
        flow_direction=flow,
        base_amount=Decimal("100.00"),
        iva_amount=iva,
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
        deduction_fact_kind=deduction_fact_kind,
        deduction_provenance=deduction_provenance,
    )


def _calculate_303_from_observations(
    *,
    filing_year: int,
    period: str,
    observations: tuple[IvaLedgerObservation, ...],
) -> RegistryCalculationResult:
    snapshot = _snapshot("303", filing_year, period)
    binding_values = {
        "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        # Autoconsumo (LIVA art. 9) is zero for the standard
        # autónomo path exercised by this prefill comparison test.
        "modelo-303-autoconsumo-promotor-base": Decimal("0"),
        # Common-regime taxpayers receive 100% State attribution (M303 C65
        # binding from derived tax_residence.state_attribution_ratio).
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
        **resolve_ledger_iva_aggregation_binding_values(snapshot.revision, observations),
    }
    inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": observations[-1].transaction_date},
    )


def _registry_observation(
    *,
    filing_year: int,
    period: str,
    result: RegistryCalculationResult,
) -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo="303",
        filing_year=filing_year,
        period=period,
        observations=result.observations,
    )


def _filing_result_disposition(result: RegistryCalculationResult):
    """Use the production result-disposition resolver at this test filing boundary."""
    casilla_ids = result_disposition_casilla_ids("303")
    assert casilla_ids is not None
    disposition = derive_result_disposition(
        "303",
        {casilla_id: Decimal(result.values[casilla_id]) for casilla_id in casilla_ids},
    )
    assert disposition is not None
    return disposition


def test_modelo_390_prefill_compares_annual_totals_to_persisted_periodic_observations(
    tmp_path: Path,
) -> None:
    """M390 ordinary M303 annual-total bindings resolve via the relation path.

    The three M390←M303 annual-total fold bindings migrated from
    ``previous_filing`` to ``relation_prefill`` backed by ``cross_model_output``
    relations.
    This test verifies that persisted 303 quarterly observations
    resolve through :func:`resolve_relations_from_local_store` and that the
    annual reconciliation casillas equal the ledger-derived annual totals.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        quarterly_observations = {
            "1T": (
                _observation(ledger_id="q1-output", txn_date=date(2025, 2, 15), iva=Decimal("21.00")),
                _observation(
                    ledger_id="q1-input",
                    txn_date=date(2025, 3, 1),
                    flow=IvaFlowDirection.SOPORTADO,
                    iva=Decimal("42.00"),
                ),
            ),
            "2T": (
                _observation(ledger_id="q2-output", txn_date=date(2025, 5, 10), iva=Decimal("10.00")),
                _observation(
                    ledger_id="q2-input",
                    txn_date=date(2025, 6, 20),
                    flow=IvaFlowDirection.SOPORTADO,
                    iva=Decimal("30.00"),
                ),
            ),
            "3T": (_observation(ledger_id="q3-output", txn_date=date(2025, 8, 12), iva=Decimal("50.00")),),
            "4T": (
                _observation(ledger_id="q4-output", txn_date=date(2025, 11, 4), iva=Decimal("15.00")),
                _observation(
                    ledger_id="q4-input",
                    txn_date=date(2025, 12, 12),
                    flow=IvaFlowDirection.SOPORTADO,
                    iva=Decimal("45.00"),
                ),
            ),
        }
        quarterly_results = {
            period: _calculate_303_from_observations(
                filing_year=2025,
                period=period,
                observations=observations,
            )
            for period, observations in quarterly_observations.items()
        }
        repository = CalculationObservationRepository()
        for period, result in quarterly_results.items():
            repository.save(
                repository.prepare_observation_envelope(
                    _registry_observation(filing_year=2025, period=period, result=result),
                    source_kind="app_filing",
                    result_disposition=ResultDispositionProjection(
                        disposition=_filing_result_disposition(result),
                        provenance_kind="app_filing",
                        provenance_locator=f"test-local-filing:2025:{period}",
                    ),
                    normalize_m303_carry=True,
                )
            )

        snapshot = _snapshot("390", 2025, "0A")

        # The ordinary M390←M303 annual totals are relation_prefill; the
        # compensation carry partition is owned by iva_compensation_annual_partition.
        relation_vals = resolve_relations_from_local_store(snapshot, repository=repository)
        resolved_relation_ids = {rv.relation for rv in relation_vals.values if rv.value is not None}
        assert resolved_relation_ids == {
            "modelo-390-rel-303-cuota-devengada-total",
            "modelo-390-rel-303-cuota-deducible-total",
            "modelo-390-rel-303-resultado-regimen-general",
        }
        # Provenance: resolved entries carry local_filing provenance.
        assert all(rv.provenance == "local_filing" for rv in relation_vals.values if rv.value is not None)
        relation_values_map = {rv.relation: rv.value for rv in relation_vals.values if rv.value is not None}
        relation_binding_values = materialize_relation_binding_values(
            snapshot.revision,
            relation_values_map,
            period="0A",
        )
        annual_partition = IvaCompensationAnnualPartitionSourceResolver(
            repository=repository,
            registry_snapshot=snapshot,
        ).resolve(
            CalculationSourceContext(
                bucket_id="m390-binding-prefill",
                modelo="390",
                filing_year=2025,
                period=Period.from_year_and_code(2025, "0A"),
                revision=snapshot.revision,
            ),
        )
        assert not annual_partition.unresolved_binding_ids
        # M390 casilla 63 (regularización de bienes de inversión, LIVA arts.
        # 107-110) is a declared binding on the annual revision; with no
        # capital-goods register the live resolver returns its empty-register
        # zero. Enrolling it here mirrors the calculate-path mesh so the
        # annual snapshot has every declared binding fact.
        bienes_resolution = BienesInversionRegularizacionSourceResolver(
            register_repository=BienesInversionIvaRegisterRepository(objects=profile.repository),
            observation_repository=CalculationObservationRepository(objects=profile.repository),
        ).resolve(
            CalculationSourceContext(
                bucket_id=profile.bucket_id,
                modelo="390",
                filing_year=2025,
                period=Period.from_year_and_code(2025, "0A"),
                revision=snapshot.revision,
            ),
        )
        assert not bienes_resolution.unresolved_binding_ids
        annual_ledger_values = resolve_ledger_iva_aggregation_binding_values(
            snapshot.revision,
            tuple(row for rows in quarterly_observations.values() for row in rows),
        )
        binding_values = {
            **annual_ledger_values,
            **relation_binding_values,
            **annual_partition.binding_values,
            **bienes_resolution.binding_values,
        }
        result = calculate_registry_snapshot(
            snapshot,
            inputs=resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
            binding_values=binding_values,
            date_context={"filing_period": date(2025, 12, 31)},
        )

        assert (
            result.values[_M390_CUOTA_DEVENGADA_TOTAL_CASILLA]
            == result.values[_M390_RECONCILIACION_DEVENGADA_303_CASILLA]
        )
        assert (
            result.values[_M390_CUOTA_DEDUCIBLE_TOTAL_CASILLA]
            == result.values[_M390_RECONCILIACION_DEDUCIBLE_303_CASILLA]
        )
        assert (
            result.values[_M390_RESULTADO_REGIMEN_GENERAL_CASILLA]
            == result.values[_M390_RECONCILIACION_RESULTADO_303_CASILLA]
        )


def test_modelo_303_local_iva_recurrence_preserves_filed_history_source_kind(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        iva_history_repository = IvaCompensationHistoryRepository()
        iva_history_repository.save_period(
            IvaCompensationPeriodState(
                provenance=IvaCompensationStateProvenance.AEAT_CAPTURE,
                taxpayer_nif="12345678Z",
                filing_year=2025,
                period=Period.from_year_and_code(2025, "4T"),
                expediente_id="30320254T0000000000",
                status="presentada",
                presented_at=datetime(2026, 1, 20, 10, 0, tzinfo=UTC),
                prior_pending_amount=Decimal("100.00"),
                applied_amount=Decimal("25.00"),
                pending_for_later_amount=Decimal("75.00"),
                period_result_amount=Decimal("0.00"),
                final_result_amount=Decimal("0.00"),
                generated_amount=Decimal("0.00"),
                available_end_amount=Decimal("75.00"),
                source_observation_key="303:2025:4T:history-source",
            ),
        )
        snapshot = _snapshot("303", 2026, "1T")

        recurrence, report = extract_modelo_303_local_iva_compensation_recurrence(
            snapshot,
            repository=CalculationObservationRepository(),
            iva_history_repository=iva_history_repository,
            captured_at=datetime(2026, 4, 1, 8, 0, tzinfo=UTC),
        )

    assert recurrence is not None
    assert recurrence.amount == Decimal("75.00")
    assert recurrence.source_kind == "aeat_sede_iva_compensation_history"
    assert recurrence.source_modelo == "303"
    assert recurrence.source_filing_year == 2025
    assert recurrence.source_periods == (Period.from_year_and_code(2025, "4T"),)
    assert report.prefilled
    assert {item.source_kind for item in report.prefilled} == {"aeat_sede_iva_compensation_history"}


def test_iva_history_observation_refuses_missing_registry_casilla_provenance() -> None:
    """Secure IVA history must not emit an ungrounded casilla observation."""
    snapshot = _snapshot("303", 2025, "4T")
    casillas = {item.id: item for item in snapshot.revision.casillas}
    assert _M303_RESULTADO_CASILLA in casillas, "real M303 registry must declare the oracle casilla"
    casillas_without_resultado = {
        casilla_id: casilla for casilla_id, casilla in casillas.items() if casilla_id != _M303_RESULTADO_CASILLA
    }
    formulas = {item.target_casilla_id: item for item in snapshot.revision.formulas}

    with pytest.raises(IvaCompensationCasillaReferenceError) as excinfo:
        _iva_compensation_history_observation(
            modelo_id="303",
            revision_id=snapshot.revision.id,
            casillas=casillas_without_resultado,
            formulas=formulas,
            casilla_id=_M303_RESULTADO_CASILLA,
            value=Decimal("1.00"),
        )

    assert str(excinfo.value) == "application.calculations.iva_compensation.errors.history_casilla_undeclared"


def test_iva_history_observation_only_claims_formula_provenance_for_exact_casilla_projection() -> None:
    state = IvaCompensationPeriodState(
        provenance=IvaCompensationStateProvenance.AEAT_CAPTURE,
        taxpayer_nif="12345678Z",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "4T"),
        expediente_id="30320254T0000000000",
        status="presentada",
        presented_at=datetime(2026, 1, 20, 10, 0, tzinfo=UTC),
        prior_pending_amount=Decimal("100.00"),
        applied_amount=Decimal("25.00"),
        pending_for_later_amount=Decimal("75.00"),
        period_result_amount=Decimal("-75.00"),
        final_result_amount=Decimal("0.00"),
        generated_amount=Decimal("75.00"),
        available_end_amount=Decimal("150.00"),
        source_observation_key="303:2025:4T:history-source",
    )

    observation = _observation_from_iva_compensation_history(state)
    by_id = {item.casilla_id: item for item in observation.observations}

    posterior = by_id[_M303_POSTERIOR_CASILLA]
    assert posterior.formula_id == "modelo-303-compensacion-pendiente-periodos-posteriores"
    assert posterior.operand_casilla_refs == (
        _M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA,
        _M303_COMPENSACION_APLICADA_CASILLA,
    )
    assert posterior.operand_values == (Decimal("100.00"), Decimal("25.00"))

    generated = by_id[_M303_GENERADA_CASILLA]
    assert generated.formula_id == "modelo-303-compensacion-generada-periodo"
    assert generated.operand_casilla_refs == (_M303_RESULTADO_CASILLA,)
    assert generated.operand_values == (Decimal("-75.00"),)

    available = by_id[_M303_DISPONIBLE_CASILLA]
    assert available.formula_id == "modelo-303-compensacion-disponible-fin-periodo"
    assert available.operand_casilla_refs == (_M303_POSTERIOR_CASILLA, _M303_GENERADA_CASILLA)
    assert available.operand_values == (Decimal("75.00"), Decimal("75.00"))

    assert by_id[_M303_COMPENSACION_APLICADA_CASILLA].formula_id is None


def test_iva_history_observation_rejects_mismatched_formula_operand_projection() -> None:
    snapshot = _snapshot("303", 2025, "4T")
    casillas = {item.id: item for item in snapshot.revision.casillas}
    formulas = {item.target_casilla_id: item for item in snapshot.revision.formulas}

    with pytest.raises(IvaCompensationCasillaReferenceError) as excinfo:
        _iva_compensation_history_observation(
            modelo_id="303",
            revision_id=snapshot.revision.id,
            casillas=casillas,
            formulas=formulas,
            casilla_id=_M303_DISPONIBLE_CASILLA,
            value=Decimal("150.00"),
            operand_refs=(_M303_POSTERIOR_CASILLA, _M303_RESULTADO_CASILLA),
            operand_values=(Decimal("75.00"), Decimal("75.00")),
        )

    assert str(excinfo.value) == (
        "application.calculations.iva_compensation.errors.history_operand_refs_diverge_from_formula"
    )


def test_binding_prefill_type_error_is_registered_in_error_registry() -> None:
    assert "REFUSED_BINDING_PREFILL_TYPE" in ERROR_REGISTRY


def test_binding_prefill_type_error_round_trips_through_build_error_envelope() -> None:
    exc = BindingPrefillTypeError("binding selector 'filing_year_delta' must be int|str, got list")
    envelope = build_error_envelope(exc, trace_id=None)
    assert envelope.code == "REFUSED_BINDING_PREFILL_TYPE"
    assert envelope.retryable is False


def test_selector_year_delta_raises_binding_prefill_type_error_for_invalid_type() -> None:
    with pytest.raises(BindingPrefillTypeError, match="filing_year_delta"):
        _selector_year_delta([])


def test_selector_periods_raises_binding_prefill_type_error_for_invalid_type() -> None:
    with pytest.raises(BindingPrefillTypeError, match="source_periods"):
        _selector_periods(42)
