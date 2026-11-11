"""Seed and caller-binding boundary coverage for Modelo 303 IVA wallet decisions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.calculation_observations import (
    CalculationObservationRepository,
    IvaWalletDecisionRepository,
)
from cadrumo.adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from cadrumo.application.calculations.binding_prefill import BindingPrefillReport
from cadrumo.application.calculations.iva_compensation_history import seed_iva_compensation_period
from cadrumo.application.calculations.iva_wallet_reconciliation import reconcile_modelo_303_iva_compensation
from cadrumo.application.calculations.tests.filing_evidence import general_m303_filing_evidence
from cadrumo.application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.iva_wallet_gate import require_persisted_iva_compensation_decision_matches_revision
from cadrumo.application.modelo.iva_wallet_refusal import ModeloIvaWalletReconciliationBlocked
from cadrumo.domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
    bundled_indexed_authority,
)
from cadrumo.domain.iva_compensation.reconciliation import IvaCompensationDecisionReason
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import calculation_ports_for_test
from cadrumo.entrypoints.tests.profile_persistence.iva_wallet_engine_support import (
    BUCKET_ID,
    DECIDED_AT,
    M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA,
    TARGET_PERIOD,
    TARGET_YEAR,
    TAXPAYER_NIF,
    filing_instance_evidence,
    modelo_303_engine_inputs,
    period,
    secure_backend,
    snapshot_303,
    store_operator_profile,
    store_operator_profile_with_tax_id,
    work_unit_repositories_with_modelo_303_work_unit,
)
from cadrumo.entrypoints.tests.profile_persistence.m303_annual_ledger_support import (
    M303_LEDGER_CUOTA,
    seed_m303_period_cuotas,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_no_seed_no_override_303_calculate_blocks_missing_in_scope_prior_history(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """An in-scope prior 303 period must not become a first-period zero from blank local history."""
    with secure_backend(tmp_path):
        store_operator_profile()
        snapshot = snapshot_303()
        work_unit, work_repo, calc_repo, event_repo = work_unit_repositories_with_modelo_303_work_unit(
            snapshot, operation=operation
        )
        with (
            pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info,
            calculation_ports_for_test(
                bucket_id=BUCKET_ID,
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                bucket_event_repository=event_repo,
            ) as _calculation_ports_60,
        ):
            seed_m303_period_cuotas(work_unit.work_unit_id, repercutido=M303_LEDGER_CUOTA)
            calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values=modelo_303_engine_inputs(),
                iva_compensation_decision=None,
                filing_period_date=date(TARGET_YEAR, 6, 30),
                ports=_calculation_ports_60,
                clock=DECIDED_AT,
                filing_instance_evidence=general_m303_filing_evidence(
                    work_unit.period, reference="test:iva-wallet-engine-seed-boundaries", operation=operation
                ),
            )
        assert not hasattr(exc_info.value, "suggestion")
        assert exc_info.value.precondition_failure.scenario_id == "modelo.work.calculate.iva_wallet.no_usable_authority"


def test_in_scope_period_rejects_supplied_first_period_zero_decision(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        taxpayer_nif = "12345678Z"
        with secure_backend(tmp_path):
            store_operator_profile_with_tax_id(taxpayer_nif)
            snapshot = snapshot_303()
            report = reconcile_modelo_303_iva_compensation(
                snapshot,
                taxpayer_nif=taxpayer_nif,
                wallet=None,
                repository=CalculationObservationRepository(),
                decision_repository=IvaWalletDecisionRepository(),
                decided_at=DECIDED_AT,
                treat_absent_recurrence_as_first_period=True,
                local_recurrence=None,
                prefill_report=BindingPrefillReport(prefilled=(), binding_values={}),
                operation=_authority_operation_for_test,
            )

            assert report.decision.selected_authority == "local_recurrence"
            assert report.decision.selected_amount == Decimal("0")
            assert report.decision.divergence == "first_period_zero"
            assert report.decision.blocked is False
            assert {source.source_kind for source in report.decision.authority_sources} == {"local_recurrence"}

            work_unit, work_repo, calc_repo, event_repo = work_unit_repositories_with_modelo_303_work_unit(
                snapshot, operation=operation
            )

            for supplied_decision in (None, report.decision):
                with (
                    pytest.raises(ModeloIvaWalletReconciliationBlocked),
                    calculation_ports_for_test(
                        bucket_id=BUCKET_ID,
                        work_unit_repository=work_repo,
                        calculation_repository=calc_repo,
                        bucket_event_repository=event_repo,
                    ) as _calculation_ports_108,
                ):
                    seed_m303_period_cuotas(work_unit.work_unit_id, repercutido=M303_LEDGER_CUOTA)
                    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                        work_unit.work_unit_id,
                        actor="operator",
                        casilla_inputs={},
                        binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
                        iva_compensation_decision=supplied_decision,
                        filing_period_date=date(TARGET_YEAR, 6, 30),
                        ports=_calculation_ports_108,
                        clock=DECIDED_AT,
                        filing_instance_evidence=general_m303_filing_evidence(
                            work_unit.period, reference="test:iva-wallet-engine-seed-boundaries", operation=operation
                        ),
                    )


def test_persisted_first_period_zero_refreshes_when_later_seeded_history_arrives(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """A later seed must replace a sticky first-period-zero wallet decision."""
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        taxpayer_nif = "12345678Z"
        with secure_backend(tmp_path):
            store_operator_profile_with_tax_id(taxpayer_nif)
            snapshot = snapshot_303(period="1T")
            work_unit, work_repo, calc_repo, event_repo = work_unit_repositories_with_modelo_303_work_unit(
                snapshot, operation=operation
            )
            with calculation_ports_for_test(
                bucket_id=BUCKET_ID,
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                bucket_event_repository=event_repo,
            ) as _calculation_ports_138:
                seed_m303_period_cuotas(work_unit.work_unit_id, repercutido=M303_LEDGER_CUOTA)
                first_revision = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                    work_unit.work_unit_id,
                    actor="operator",
                    casilla_inputs={},
                    binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
                    iva_compensation_decision=None,
                    filing_instance_evidence=filing_instance_evidence(work_unit.period, operation=operation),
                    filing_period_date=date(TARGET_YEAR, 3, 31),
                    ports=_calculation_ports_138,
                    clock=DECIDED_AT,
                ).revision
            assert first_revision.casilla_values[M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA] == Decimal("0")
            first_decision = IvaWalletDecisionRepository().load_decision(
                taxpayer_nif,
                period(TARGET_YEAR, "1T"),
            )
            assert first_decision is not None
            assert first_decision.divergence == "first_period_zero"
            assert first_decision.blocked is False
            assert (
                first_decision.reason_identity
                is IvaCompensationDecisionReason.FIRST_PERIOD_ZERO_ACTIVITY_START_UNCONTRASTED
            )

            seed_iva_compensation_period(
                taxpayer_nif=taxpayer_nif,
                period=period(TARGET_YEAR - 1, "4T"),
                amount=Decimal("450.00"),
                seeded_at=DECIDED_AT,
                repository=IvaCompensationHistoryRepository(),
                operation=_authority_operation_for_test,
            )

            with (
                pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info,
                calculation_ports_for_test(
                    bucket_id=BUCKET_ID,
                    work_unit_repository=work_repo,
                    calculation_repository=calc_repo,
                    bucket_event_repository=event_repo,
                ) as _calculation_ports_175,
            ):
                seed_m303_period_cuotas(work_unit.work_unit_id, repercutido=M303_LEDGER_CUOTA)
                calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                    work_unit.work_unit_id,
                    actor="operator",
                    casilla_inputs={},
                    binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
                    iva_compensation_decision=None,
                    filing_instance_evidence=filing_instance_evidence(work_unit.period, operation=operation),
                    filing_period_date=date(TARGET_YEAR, 3, 31),
                    ports=_calculation_ports_175,
                    clock=DECIDED_AT,
                )

            assert exc_info.value.context is not None
            assert exc_info.value.context["divergence"] == "wallet_missing"
            # The refused calculation writes nothing, so the sticky zero is still
            # stored; checking the revision it fed refreshes and stores the block.
            assert (
                IvaWalletDecisionRepository().load_decision(taxpayer_nif, period(TARGET_YEAR, "1T")) == first_decision
            )
            with pytest.raises(ModeloIvaWalletReconciliationBlocked):
                require_persisted_iva_compensation_decision_matches_revision(
                    work_unit,
                    first_revision,
                    repository=IvaWalletDecisionRepository(),
                    observation_repository=CalculationObservationRepository(),
                    history_repository=IvaCompensationHistoryRepository(),
                    operation=_authority_operation_for_test,
                )
            refreshed = IvaWalletDecisionRepository().load_decision(
                taxpayer_nif,
                period(TARGET_YEAR, "1T"),
            )
            assert refreshed is not None
            assert refreshed.divergence == "wallet_missing"
            assert refreshed.local_recurrence_amount == Decimal("450.00")
            assert refreshed.blocked is True
            assert any(
                source.source_periods == (period(TARGET_YEAR - 1, "4T"),) for source in refreshed.authority_sources
            )


def test_explicit_zero_binding_matches_prior_zero_seed_and_feeds_real_modelo_303_engine(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """A caller explicit zero is allowed only after the local zero seed reconciles it."""
    with bundled_indexed_authority().operation() as _authority_operation_for_test, secure_backend(tmp_path):
        store_operator_profile()
        seed_iva_compensation_period(
            taxpayer_nif=TAXPAYER_NIF,
            period=period(TARGET_YEAR, "1T"),
            amount=Decimal("0"),
            seeded_at=DECIDED_AT,
            repository=IvaCompensationHistoryRepository(),
            operation=_authority_operation_for_test,
        )
        snapshot = snapshot_303()
        work_unit, work_repo, calc_repo, event_repo = work_unit_repositories_with_modelo_303_work_unit(
            snapshot, operation=operation
        )
        with calculation_ports_for_test(
            bucket_id=BUCKET_ID,
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
        ) as _calculation_ports_221:
            revision = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values={
                    **modelo_303_engine_inputs(),
                    "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
                },
                iva_compensation_decision=None,
                filing_period_date=date(TARGET_YEAR, 6, 30),
                ports=_calculation_ports_221,
                clock=DECIDED_AT,
                filing_instance_evidence=general_m303_filing_evidence(
                    work_unit.period, reference="test:iva-wallet-engine-seed-boundaries", operation=operation
                ),
            ).revision

        assert Decimal(revision.binding_overrides["modelo-303-compensacion-pendiente-anteriores"]) == Decimal("0")
        assert revision.casilla_values[M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA] == Decimal("0.00")
        decision = IvaWalletDecisionRepository().load_decision(
            TAXPAYER_NIF,
            period(TARGET_YEAR, TARGET_PERIOD),
        )
        assert decision is not None
        assert decision.selected_amount == Decimal("0")
        assert decision.local_recurrence_amount == Decimal("0")
        assert decision.blocked is False
        assert decision.reason_identity is IvaCompensationDecisionReason.CALLER_ZERO_MATCHES_LOCAL_AUTHORITY
        assert any(
            source.amount == Decimal("0") and source.source_periods == (period(TARGET_YEAR, "1T"),)
            for source in decision.authority_sources
        )


def test_explicit_nonzero_binding_conflicts_with_prior_zero_seed(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """A caller value that differs from the reconciled zero seed is refused."""
    with bundled_indexed_authority().operation() as _authority_operation_for_test, secure_backend(tmp_path):
        store_operator_profile()
        seed_iva_compensation_period(
            taxpayer_nif=TAXPAYER_NIF,
            period=period(TARGET_YEAR, "1T"),
            amount=Decimal("0"),
            seeded_at=DECIDED_AT,
            repository=IvaCompensationHistoryRepository(),
            operation=_authority_operation_for_test,
        )
        snapshot = snapshot_303()
        work_unit, work_repo, calc_repo, event_repo = work_unit_repositories_with_modelo_303_work_unit(
            snapshot, operation=operation
        )

        with (
            pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info,
            calculation_ports_for_test(
                bucket_id=BUCKET_ID,
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                bucket_event_repository=event_repo,
            ) as _calculation_ports_273,
        ):
            calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values={
                    **modelo_303_engine_inputs(),
                    "modelo-303-compensacion-pendiente-anteriores": Decimal("1.00"),
                },
                iva_compensation_decision=None,
                filing_period_date=date(TARGET_YEAR, 6, 30),
                ports=_calculation_ports_273,
                clock=DECIDED_AT,
                filing_instance_evidence=general_m303_filing_evidence(
                    work_unit.period, reference="test:iva-wallet-engine-seed-boundaries", operation=operation
                ),
            )

        assert exc_info.value.translated_message == "application.modelo.errors.iva_wallet_caller_binding_conflict"
        assert len(calc_repo.load()) == 0
