"""Override behavior for AEAT IVA wallet decisions in Modelo 303."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.calculation_observations import (
    CalculationObservationRepository,
    IvaWalletDecisionRepository,
)
from cadrumo.adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from cadrumo.application.calculations.binding_prefill import extract_modelo_303_local_iva_compensation_recurrence
from cadrumo.application.calculations.iva_wallet_reconciliation import reconcile_modelo_303_iva_compensation
from cadrumo.application.calculations.observations_repository import CalculationObservationPorts
from cadrumo.application.modelo.calculation_actions import calculate_modelo_revision
from cadrumo.application.modelo.iva_wallet_gate import ModeloIvaWalletReconciliationBlocked
from cadrumo.application.modelo.iva_wallet_seed import (
    ModeloIvaWalletOverrideFreshWalletError,
    ModeloIvaWalletOverrideSealedError,
    record_iva_compensation_override_for_bucket,
)
from cadrumo.application.modelo.iva_wallet_seed_ports import ModeloIvaWalletSeedPorts
from cadrumo.core.casilla_id import CasillaId
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from cadrumo.domain.iva_compensation.reconciliation import IvaCompensationOverride
from cadrumo.domain.modelos.calculation_repository import upsert_calculation_revision
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from cadrumo.domain.modelos.repository import upsert_work_unit
from cadrumo.entrypoints.tests.profile_persistence._iva_wallet_engine_support import (
    _BUCKET_ID,
    _DECIDED_AT,
    _M303_COMPENSACION_APLICADA_CASILLA,
    _M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA,
    _M303_RESULTADO_CASILLA,
    _TARGET_PERIOD,
    _TARGET_PERIOD_VALUE,
    _TARGET_YEAR,
    _TAXPAYER_NIF,
    _filing_instance_evidence,
    _modelo_303_engine_inputs,
    _save_wallet_gate_decision,
    _secure_backend,
    _snapshot_303,
    _store_operator_profile,
    _store_prior_303_compensation,
    _work_unit_and_revision_for_wallet_gate,
    _work_unit_repositories_with_modelo_303_work_unit,
)
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import calculation_ports_for_test

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _modelo_iva_wallet_seed_ports() -> ModeloIvaWalletSeedPorts:
    """Compose the real persistence adapters for this adapter-layer test."""
    objects = secure_object_repository_for_bucket(_BUCKET_ID)
    return ModeloIvaWalletSeedPorts(
        work_unit_repository=WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
        calculation_repository=CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
        calculation_observation_ports=CalculationObservationPorts(
            observation_repository=CalculationObservationRepository(objects=objects),
            iva_wallet_decision_repository=IvaWalletDecisionRepository(objects=objects),
        ),
        iva_compensation_history_repository=IvaCompensationHistoryRepository(),
    )


def test_missing_wallet_requires_explicit_override_before_real_modelo_303_engine_prefill(tmp_path: Path) -> None:
    with _secure_backend(tmp_path), bundled_indexed_authority().operation() as operation:
        _store_operator_profile()
        observation_repo = CalculationObservationRepository()
        _store_prior_303_compensation(observation_repo, amount=Decimal("1200.00"))
        snapshot = _snapshot_303()
        local_recurrence, prefill_report = extract_modelo_303_local_iva_compensation_recurrence(
            snapshot,
            repository=observation_repo,
            captured_at=_DECIDED_AT,
            iva_history_repository=IvaCompensationHistoryRepository(),
            operation=operation,
        )
        report = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=_TAXPAYER_NIF,
            wallet=None,
            repository=observation_repo,
            decision_repository=IvaWalletDecisionRepository(),
            override=IvaCompensationOverride(
                amount=Decimal("1200.00"),
                operator_explanation=(
                    "Operator reviewed filed-history evidence while direct wallet/cartera was unavailable."
                ),
                evidence_locator="operator-review:modelo-303-2026-2T-filed-history",
                recorded_at=_DECIDED_AT,
            ),
            decided_at=_DECIDED_AT,
            local_recurrence=local_recurrence,
            prefill_report=prefill_report,
            operation=operation,
        )

        assert report.decision.selected_authority == "taxpayer_override"
        assert report.decision.divergence == "override"
        assert report.decision.blocked is False
        assert {source.source_kind for source in report.decision.authority_sources} == {
            "local_recurrence",
            "filed_history_observation",
            "taxpayer_override",
        }

        work_unit, work_repo, calc_repo, event_repo = _work_unit_repositories_with_modelo_303_work_unit(
            snapshot, operation=operation
        )
        with calculation_ports_for_test(
            bucket_id=_BUCKET_ID,
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
        ) as _calculation_ports_136:
            revision = calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
                backend_binding_values=_modelo_303_engine_inputs(),
                iva_compensation_decision=report.decision,
                filing_instance_evidence=_filing_instance_evidence(work_unit.period, operation=operation),
                filing_period_date=date(2026, 6, 30),
                ports=_calculation_ports_136,
                clock=_DECIDED_AT,
            )

        assert revision.casilla_values[_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA] == Decimal("1200.00")


def test_recorded_override_unblocks_carry_and_reduces_final_result(tmp_path: Path) -> None:
    """Recording an override reduces the FINAL Modelo 303 result, with a negative control.

    A/B: with NO override the in-scope prior period is missing and calculation
    blocks; AFTER recording an override of 450 the carry applies and the FINAL
    result (iva.resultado) drops to 550. This asserts the carry's effect on the
    final figure, not just that the override value plumbs through to casilla 110.
    """
    with _secure_backend(tmp_path), bundled_indexed_authority().operation() as operation:
        _store_operator_profile()
        snapshot = _snapshot_303()
        work_unit, work_repo, calc_repo, event_repo = _work_unit_repositories_with_modelo_303_work_unit(
            snapshot, operation=operation
        )

        def _calculate() -> CalculationRevision:
            with calculation_ports_for_test(
                bucket_id=_BUCKET_ID,
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                bucket_event_repository=event_repo,
            ) as _calculation_ports_171:
                return calculate_modelo_revision(
                    work_unit.work_unit_id,
                    actor="operator",
                    casilla_inputs={},
                    binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
                    backend_binding_values=_modelo_303_engine_inputs(),
                    iva_compensation_decision=None,
                    filing_instance_evidence=_filing_instance_evidence(work_unit.period, operation=operation),
                    filing_period_date=date(2026, 6, 30),
                    ports=_calculation_ports_171,
                    clock=_DECIDED_AT,
                )

        # NEGATIVE CONTROL: no override recorded and no wallet/local recurrence
        # exists for the in-scope prior period, so calculation fails closed.
        with pytest.raises(ModeloIvaWalletReconciliationBlocked):
            _calculate()

        decision = record_iva_compensation_override_for_bucket(
            bucket_id=_BUCKET_ID,
            period=_TARGET_PERIOD_VALUE,
            amount=Decimal("450.00"),
            reason="Operator asserts the prior-quarter cuota a compensar.",
            evidence_locator="operator-review:m303-prior-quarter",
            ports=_modelo_iva_wallet_seed_ports(),
            operation=operation,
        )
        assert decision.selected_authority == "taxpayer_override"
        assert decision.blocked is False

        # AFTER: the recorded override supersedes the first-period decision and the
        # FINAL result drops by the applied compensación.
        applied = _calculate()
        assert applied.casilla_values[_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA] == Decimal("450.00")
        assert applied.casilla_values[_M303_COMPENSACION_APLICADA_CASILLA] == Decimal("450.00")
        assert applied.casilla_values[_M303_RESULTADO_CASILLA] == Decimal("550.00")


def test_override_refused_when_sealed_303_consumed_the_basis(tmp_path: Path) -> None:
    """Filed-immutability guard: an override is refused when a sealed Modelo 303 at or
    after the period has already consumed that period's compensación basis."""
    with _secure_backend(tmp_path), bundled_indexed_authority().operation() as operation:
        _store_operator_profile()
        work_unit, _ = _work_unit_and_revision_for_wallet_gate(
            compensation_amount=Decimal("450.00"), operation=operation
        )
        casilla_values: dict[CasillaId, Decimal] = {
            _M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA: Decimal("450.00"),
        }
        sealed_filing_instance_evidence = _filing_instance_evidence(work_unit.period, operation=operation)
        sealed_revision = CalculationRevision.model_validate(
            {
                "calculation_revision_id": derive_calculation_revision_id(
                    work_unit_id=work_unit.work_unit_id,
                    input_values_by_casilla_id={},
                    binding_overrides={},
                    casilla_values=casilla_values,
                    filing_instance_evidence=sealed_filing_instance_evidence,
                    source_provenance=(),
                ),
                "work_unit_id": work_unit.work_unit_id,
                "registry_snapshot_ref": RegistrySnapshotRef(
                    modelo=work_unit.modelo,
                    revision_id=work_unit.revision_id,
                    modelo_year=work_unit.filing_year,
                    period=work_unit.period.registry_token,
                ),
                "state": CalculationRevisionState.VERIFICADO_COMPLETO,
                "input_values_by_casilla_id": {},
                "binding_overrides": {},
                "casilla_values": casilla_values,
                "source_provenance": (),
                "observations": registry_grounded_observations(
                    modelo="303",
                    filing_year=_TARGET_YEAR,
                    period=_TARGET_PERIOD,
                    casilla_values=casilla_values,
                ),
                "created_at": _DECIDED_AT,
                "updated_at": _DECIDED_AT,
                "verified_at": _DECIDED_AT,
                "verified_by": "tester",
                "filing_instance_evidence": sealed_filing_instance_evidence,
            },
        )
        wu_repo = WorkUnitCatalogueRepository()
        wu_repo.save(upsert_work_unit(wu_repo.load(), work_unit))
        rev_repo = CalculationRevisionCatalogueRepository()
        rev_repo.save(upsert_calculation_revision(rev_repo.load(), sealed_revision))

        with pytest.raises(ModeloIvaWalletOverrideSealedError):
            record_iva_compensation_override_for_bucket(
                bucket_id=_BUCKET_ID,
                period=_TARGET_PERIOD_VALUE,
                amount=Decimal("450.00"),
                reason="x",
                evidence_locator="y",
                ports=_modelo_iva_wallet_seed_ports(),
                operation=operation,
            )


def test_override_refused_when_fresh_wallet_decision_exists(tmp_path: Path) -> None:
    """No override of fresh AEAT evidence: an override is refused when a non-blocked
    aeat_wallet decision already resolves the period."""
    with _secure_backend(tmp_path), bundled_indexed_authority().operation() as operation:
        _store_operator_profile()
        _save_wallet_gate_decision(amount=Decimal("450.00"), blocked=False)

        with pytest.raises(ModeloIvaWalletOverrideFreshWalletError):
            record_iva_compensation_override_for_bucket(
                bucket_id=_BUCKET_ID,
                period=_TARGET_PERIOD_VALUE,
                amount=Decimal("999.00"),
                reason="x",
                evidence_locator="y",
                ports=_modelo_iva_wallet_seed_ports(),
                operation=operation,
            )
