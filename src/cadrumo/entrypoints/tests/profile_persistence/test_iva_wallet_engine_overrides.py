"""Override behavior for AEAT IVA wallet decisions in Modelo 303."""

from __future__ import annotations

from datetime import date, timedelta
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
from cadrumo.application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.iva_wallet_refusal import ModeloIvaWalletReconciliationBlocked
from cadrumo.application.modelo.iva_wallet_seed import (
    ModeloIvaWalletOverrideFreshWalletError,
    ModeloIvaWalletOverrideSealedError,
    record_iva_compensation_override_for_bucket,
)
from cadrumo.application.modelo.iva_wallet_seed_ports import ModeloIvaWalletSeedPorts
from cadrumo.core.casilla_id import CasillaId
from cadrumo.core.time.clock import frozen_clock
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
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import calculation_ports_for_test
from cadrumo.entrypoints.tests.profile_persistence.iva_wallet_engine_support import (
    BUCKET_ID,
    DECIDED_AT,
    M303_COMPENSACION_APLICADA_CASILLA,
    M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA,
    M303_RESULTADO_CASILLA,
    TARGET_PERIOD,
    TARGET_PERIOD_VALUE,
    TARGET_YEAR,
    TAXPAYER_NIF,
    filing_instance_evidence,
    save_wallet_gate_decision,
    secure_backend,
    snapshot_303,
    store_operator_profile,
    store_prior_303_compensation,
    work_unit_and_revision_for_wallet_gate,
    work_unit_repositories_with_modelo_303_work_unit,
)
from cadrumo.entrypoints.tests.profile_persistence.m303_annual_ledger_support import (
    M303_LEDGER_CUOTA,
    seed_m303_period_cuotas,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _modelo_iva_wallet_seed_ports() -> ModeloIvaWalletSeedPorts:
    """Compose the real persistence adapters for this adapter-layer test."""
    objects = secure_object_repository_for_bucket(BUCKET_ID)
    return ModeloIvaWalletSeedPorts(
        work_unit_repository=WorkUnitCatalogueRepository(bucket_id=BUCKET_ID, objects=objects),
        calculation_repository=CalculationRevisionCatalogueRepository(bucket_id=BUCKET_ID, objects=objects),
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
        calculation_observation_ports=CalculationObservationPorts(
            observation_repository=CalculationObservationRepository(objects=objects),
            iva_wallet_decision_repository=IvaWalletDecisionRepository(objects=objects),
        ),
        iva_compensation_history_repository=IvaCompensationHistoryRepository(),
    )


def test_oversized_override_locator_refuses_before_decision_or_audit_write(tmp_path: Path) -> None:
    """An event-incompatible locator cannot leave a decision without its audit event."""
    with frozen_clock(DECIDED_AT), secure_backend(tmp_path), bundled_indexed_authority().operation() as operation:
        store_operator_profile()
        ports = _modelo_iva_wallet_seed_ports()
        existing_events = ports.bucket_event_repository.load().events

        with pytest.raises(ValueError, match="evidence_locator exceeds the bucket-event payload limit"):
            record_iva_compensation_override_for_bucket(
                bucket_id=BUCKET_ID,
                period=TARGET_PERIOD_VALUE,
                amount=Decimal("450.00"),
                reason="operator reviewed the prior balance",
                evidence_locator="x" * 501,
                ports=ports,
                operation=operation,
            )

        assert (
            ports.calculation_observation_ports.iva_wallet_decision_repository.load_decision(
                TAXPAYER_NIF, TARGET_PERIOD_VALUE
            )
            is None
        )
        assert ports.bucket_event_repository.load().events == existing_events


def test_missing_wallet_requires_explicit_override_before_real_modelo_303_engine_prefill(tmp_path: Path) -> None:
    with frozen_clock(DECIDED_AT), secure_backend(tmp_path), bundled_indexed_authority().operation() as operation:
        store_operator_profile()
        observation_repo = CalculationObservationRepository()
        store_prior_303_compensation(observation_repo, amount=Decimal("1200.00"))
        snapshot = snapshot_303()
        local_recurrence, prefill_report = extract_modelo_303_local_iva_compensation_recurrence(
            snapshot,
            repository=observation_repo,
            captured_at=DECIDED_AT,
            iva_history_repository=IvaCompensationHistoryRepository(),
            operation=operation,
        )
        report = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=TAXPAYER_NIF,
            wallet=None,
            repository=observation_repo,
            decision_repository=IvaWalletDecisionRepository(),
            override=IvaCompensationOverride(
                amount=Decimal("1200.00"),
                operator_explanation=(
                    "Operator reviewed filed-history evidence while direct wallet/cartera was unavailable."
                ),
                evidence_locator="operator-review:modelo-303-2026-2T-filed-history",
                recorded_at=DECIDED_AT,
            ),
            decided_at=DECIDED_AT,
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

        work_unit, work_repo, calc_repo, event_repo = work_unit_repositories_with_modelo_303_work_unit(
            snapshot, operation=operation
        )
        with calculation_ports_for_test(
            bucket_id=BUCKET_ID,
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
        ) as _calculation_ports_136:
            seed_m303_period_cuotas(work_unit.work_unit_id, repercutido=M303_LEDGER_CUOTA)
            revision = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
                iva_compensation_decision=report.decision,
                filing_instance_evidence=filing_instance_evidence(work_unit.period, operation=operation),
                filing_period_date=date(2026, 6, 30),
                ports=_calculation_ports_136,
                clock=DECIDED_AT,
            ).revision

        assert revision.casilla_values[M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA] == Decimal("1200.00")


def test_recorded_override_unblocks_carry_and_reduces_final_result(tmp_path: Path) -> None:
    """Recording an override reduces the FINAL Modelo 303 result, with a negative control.

    A/B: with NO override the in-scope prior period is missing and calculation
    blocks; AFTER recording an override of 450 the carry applies and the FINAL
    result (iva.resultado) drops to 550. This asserts the carry's effect on the
    final figure, not just that the override value plumbs through to casilla 110.
    """
    with frozen_clock(DECIDED_AT), secure_backend(tmp_path), bundled_indexed_authority().operation() as operation:
        store_operator_profile()
        snapshot = snapshot_303()
        work_unit, work_repo, calc_repo, event_repo = work_unit_repositories_with_modelo_303_work_unit(
            snapshot, operation=operation
        )

        def _calculate() -> CalculationRevision:
            with calculation_ports_for_test(
                bucket_id=BUCKET_ID,
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                bucket_event_repository=event_repo,
            ) as _calculation_ports_171:
                seed_m303_period_cuotas(work_unit.work_unit_id, repercutido=M303_LEDGER_CUOTA)
                return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                    work_unit.work_unit_id,
                    actor="operator",
                    casilla_inputs={},
                    binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
                    iva_compensation_decision=None,
                    filing_instance_evidence=filing_instance_evidence(work_unit.period, operation=operation),
                    filing_period_date=date(2026, 6, 30),
                    ports=_calculation_ports_171,
                    clock=DECIDED_AT,
                ).revision

        # NEGATIVE CONTROL: no override recorded and no wallet/local recurrence
        # exists for the in-scope prior period, so calculation fails closed.
        with pytest.raises(ModeloIvaWalletReconciliationBlocked):
            _calculate()

        decision = record_iva_compensation_override_for_bucket(
            bucket_id=BUCKET_ID,
            period=TARGET_PERIOD_VALUE,
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
        assert applied.casilla_values[M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA] == Decimal("450.00")
        assert applied.casilla_values[M303_COMPENSACION_APLICADA_CASILLA] == Decimal("450.00")
        assert applied.casilla_values[M303_RESULTADO_CASILLA] == Decimal("550.00")


def test_override_refused_when_sealed_303_consumed_the_basis(tmp_path: Path) -> None:
    """Filed-immutability guard: an override is refused when a sealed Modelo 303 at or
    after the period has already consumed that period's compensación basis."""
    with frozen_clock(DECIDED_AT), secure_backend(tmp_path), bundled_indexed_authority().operation() as operation:
        store_operator_profile()
        work_unit, _ = work_unit_and_revision_for_wallet_gate(
            compensation_amount=Decimal("450.00"), operation=operation
        )
        casilla_values: dict[CasillaId, Decimal] = {
            M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA: Decimal("450.00"),
        }
        sealed_filing_instance_evidence = filing_instance_evidence(work_unit.period, operation=operation)
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
                    filing_year=TARGET_YEAR,
                    period=TARGET_PERIOD,
                    casilla_values=casilla_values,
                ),
                "created_at": DECIDED_AT,
                "updated_at": DECIDED_AT,
                "verified_at": DECIDED_AT,
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
                bucket_id=BUCKET_ID,
                period=TARGET_PERIOD_VALUE,
                amount=Decimal("450.00"),
                reason="x",
                evidence_locator="y",
                ports=_modelo_iva_wallet_seed_ports(),
                operation=operation,
            )


def test_override_refused_when_fresh_wallet_decision_exists(tmp_path: Path) -> None:
    """No override of fresh AEAT evidence: an override is refused when a non-blocked
    aeat_wallet decision already resolves the period."""
    with frozen_clock(DECIDED_AT), secure_backend(tmp_path), bundled_indexed_authority().operation() as operation:
        store_operator_profile()
        save_wallet_gate_decision(amount=Decimal("450.00"), blocked=False)

        with pytest.raises(ModeloIvaWalletOverrideFreshWalletError):
            record_iva_compensation_override_for_bucket(
                bucket_id=BUCKET_ID,
                period=TARGET_PERIOD_VALUE,
                amount=Decimal("999.00"),
                reason="x",
                evidence_locator="y",
                ports=_modelo_iva_wallet_seed_ports(),
                operation=operation,
            )


def test_expired_wallet_allows_explicit_override(tmp_path: Path) -> None:
    with (
        frozen_clock(DECIDED_AT + timedelta(days=32)),
        secure_backend(tmp_path),
        bundled_indexed_authority().operation() as operation,
    ):
        store_operator_profile()
        save_wallet_gate_decision(amount=Decimal("1200"))
        decision = record_iva_compensation_override_for_bucket(
            bucket_id=BUCKET_ID,
            period=TARGET_PERIOD_VALUE,
            amount=Decimal("800"),
            reason="reviewed expired wallet",
            evidence_locator="test://reviewed-wallet",
            ports=_modelo_iva_wallet_seed_ports(),
            operation=operation,
        )
        assert decision.selected_authority == "taxpayer_override"
        assert decision.selected_amount == Decimal("800")
