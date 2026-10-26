"""Lifecycle-gate coverage for AEAT IVA wallet decisions in Modelo 303."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from cadrumo.adapters.persistence.profile.calculation_observations import (
    CalculationObservationRepository,
    IvaWalletDecisionRepository,
)
from cadrumo.adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.application.calculations.binding_prefill import BindingPrefillReport
from cadrumo.application.calculations.iva_wallet_reconciliation import reconcile_modelo_303_iva_compensation
from cadrumo.application.calculations.tests.filing_evidence import general_m303_filing_evidence
from cadrumo.application.modelo.calculation_actions import calculate_modelo_revision
from cadrumo.application.modelo.filing_actions import file_modelo_revision
from cadrumo.application.modelo.iva_wallet_gate import (
    ModeloIvaWalletReconciliationBlocked,
    require_persisted_iva_compensation_decision_matches_revision,
    resolve_iva_compensation_decision_for_calculation,
)
from cadrumo.application.modelo.lifecycle_clock_gate import ModeloLifecycleClockPrecedesError
from cadrumo.application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from cadrumo.core.time.clock import frozen_clock
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.iva_compensation.reconciliation import IvaCompensationReconciliationDecision
from cadrumo.entrypoints.adapter_composition import build_calculation_action_ports, build_filing_action_ports
from cadrumo.entrypoints.tests.profile_persistence._iva_wallet_engine_support import (
    _DECIDED_AT,
    _M303_COMPENSACION_APLICADA_CASILLA,
    _M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA,
    _M303_POSTERIOR_CASILLA,
    _M303_RESULTADO_CASILLA,
    _TAXPAYER_NIF,
    _modelo_303_engine_inputs,
    _save_wallet_gate_decision,
    _secure_backend,
    _snapshot_303,
    _store_operator_profile,
    _store_operator_profile_with_tax_id,
    _wallet_observation,
    _work_unit_and_revision_for_wallet_gate,
    _work_unit_repositories_with_modelo_303_work_unit,
    workflow_profile,
)
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)
from cadrumo.tests.env_scope import ready_clave_settings

from ....adapters.persistence.profile.tests.wallet_history import load_decision_history

_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()


pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _reconcile_modelo_303_iva_compensation(snapshot: Any, **kwargs: Any) -> Any:
    kwargs.setdefault("decision_repository", IvaWalletDecisionRepository())
    with bundled_indexed_authority().operation() as operation:
        return reconcile_modelo_303_iva_compensation(snapshot, operation=operation, **kwargs)


def _calculate_modelo_revision(work_unit_id: str, **kwargs: Any) -> Any:
    repository = kwargs.pop("work_unit_repository", None)
    for key in ("calculation_repository", "bucket_event_repository"):
        kwargs.pop(key, None)
    with bundled_indexed_authority().operation() as operation:
        return calculate_modelo_revision(
            work_unit_id,
            ports=build_calculation_action_ports(bucket_id=repository.bucket_id, operation=operation),
            **kwargs,
        )


def _verify_modelo_revision(calculation_revision_id: str, **kwargs: Any) -> Any:
    for key in ("work_unit_repository", "calculation_repository", "filing_repository", "bucket_event_repository"):
        kwargs.pop(key, None)
    with bundled_indexed_authority().operation() as operation:
        kwargs.setdefault("certificate_secret_backend_factory", build_test_certificate_secret_backend_factory())
        kwargs.setdefault("verification_repositories", build_test_verification_repository_bundle())
        return verify_modelo_revision_with_preconditions(calculation_revision_id, operation=operation, **kwargs).report


def _require_persisted_iva_compensation_decision_matches_revision(work_unit: Any, revision: Any, **kwargs: Any) -> Any:
    kwargs.setdefault("repository", IvaWalletDecisionRepository())
    with bundled_indexed_authority().operation() as operation:
        return require_persisted_iva_compensation_decision_matches_revision(
            work_unit,
            revision,
            operation=operation,
            observation_repository=CalculationObservationRepository(),
            history_repository=IvaCompensationHistoryRepository(),
            **kwargs,
        )


def test_grounded_first_period_zero_decision_feeds_real_modelo_303_engine_and_lifecycle_gate(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    taxpayer_nif = "12345678Z"
    with frozen_clock(_DECIDED_AT), _secure_backend(tmp_path):
        _store_operator_profile_with_tax_id(taxpayer_nif)
        snapshot = _snapshot_303(period="1T")
        report = _reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=taxpayer_nif,
            wallet=None,
            repository=CalculationObservationRepository(),
            decided_at=_DECIDED_AT,
            treat_absent_recurrence_as_first_period=True,
            local_recurrence=None,
            prefill_report=BindingPrefillReport(prefilled=(), binding_values={}),
        )

        assert report.decision.selected_authority == "local_recurrence"
        assert report.decision.selected_amount == Decimal("0")
        assert report.decision.divergence == "first_period_zero"
        assert report.decision.blocked is False
        assert {source.source_kind for source in report.decision.authority_sources} == {"local_recurrence"}

        work_unit, work_repo, calc_repo, event_repo = _work_unit_repositories_with_modelo_303_work_unit(
            snapshot, operation=operation
        )
        revision = _calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator",
            casilla_inputs={},
            binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
            backend_binding_values=_modelo_303_engine_inputs(),
            iva_compensation_decision=report.decision,
            filing_period_date=date(2026, 3, 31),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=_DECIDED_AT,
            filing_instance_evidence=general_m303_filing_evidence(
                work_unit.period, reference="test:iva-wallet-engine-lifecycle-gate", operation=operation
            ),
        )
        assert Decimal(revision.binding_overrides["modelo-303-compensacion-pendiente-anteriores"]) == Decimal("0")
        assert revision.casilla_values[_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA] == Decimal("0.00")
        assert revision.casilla_values[_M303_COMPENSACION_APLICADA_CASILLA] == Decimal("0.00")
        decision = _require_persisted_iva_compensation_decision_matches_revision(work_unit, revision)
        assert decision is not None
        assert decision.divergence == "first_period_zero"
        verification = _verify_modelo_revision(
            revision.calculation_revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=build_test_verification_repository_bundle(),
            actor="operator",
            workflow_profile=workflow_profile(taxpayer_nif).model_copy(
                update={"activity_start_date": date(2026, 1, 1)},
            ),
            settings=ready_clave_settings(taxpayer_nif),
            clock=_DECIDED_AT,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )
        assert verification.granted_verificado_completo is True
        assert not any(finding.kind.value == "cross_period_dependency_unclean" for finding in verification.findings)


def test_modelo_303_lifecycle_gate_requires_persisted_wallet_authority(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    with frozen_clock(_DECIDED_AT), _secure_backend(tmp_path):
        _store_operator_profile()
        work_unit, revision = _work_unit_and_revision_for_wallet_gate(
            compensation_amount=Decimal("1200.00"), operation=operation
        )

        with pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info:
            _require_persisted_iva_compensation_decision_matches_revision(work_unit, revision)

        assert exc_info.value.translated_message == "application.modelo.errors.iva_wallet_not_seeded"


def test_modelo_303_lifecycle_gate_rejects_wallet_authority_amount_drift(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    with frozen_clock(_DECIDED_AT), _secure_backend(tmp_path):
        _store_operator_profile()
        _save_wallet_gate_decision(amount=Decimal("800.00"))
        work_unit, revision = _work_unit_and_revision_for_wallet_gate(
            compensation_amount=Decimal("1200.00"), operation=operation
        )

        with pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info:
            _require_persisted_iva_compensation_decision_matches_revision(work_unit, revision)
        assert exc_info.value.translated_message == "application.modelo.errors.iva_wallet_amount_mismatch"
        assert exc_info.value.context is not None
        assert exc_info.value.context["divergence"] == "authority_amount_mismatch"


def test_modelo_303_lifecycle_gate_accepts_matching_wallet_authority(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    with frozen_clock(_DECIDED_AT), _secure_backend(tmp_path):
        _store_operator_profile()
        _save_wallet_gate_decision(amount=Decimal("1200.00"))
        work_unit, revision = _work_unit_and_revision_for_wallet_gate(
            compensation_amount=Decimal("1200.00"), operation=operation
        )

        decision = _require_persisted_iva_compensation_decision_matches_revision(work_unit, revision)

        assert decision is not None
        assert decision.selected_authority == "aeat_wallet"


def test_wallet_only_decision_feeds_real_modelo_303_engine_and_lifecycle_gate(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    with frozen_clock(_DECIDED_AT), _secure_backend(tmp_path):
        _store_operator_profile()
        snapshot = _snapshot_303()
        report = _reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=_TAXPAYER_NIF,
            wallet=_wallet_observation(pending=Decimal("1200.00")),
            repository=CalculationObservationRepository(),
            decided_at=_DECIDED_AT,
            local_recurrence=None,
            prefill_report=BindingPrefillReport(prefilled=(), binding_values={}),
        )

        assert report.decision.selected_authority == "aeat_wallet"
        assert report.decision.divergence == "wallet_only"
        assert report.decision.blocked is False
        assert {source.source_kind for source in report.decision.authority_sources} == {"aeat_wallet"}

        work_unit, work_repo, calc_repo, event_repo = _work_unit_repositories_with_modelo_303_work_unit(
            snapshot, operation=operation
        )
        revision = _calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator",
            casilla_inputs={},
            binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
            backend_binding_values=_modelo_303_engine_inputs(),
            iva_compensation_decision=report.decision,
            filing_period_date=date(2026, 6, 30),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=_DECIDED_AT,
            filing_instance_evidence=general_m303_filing_evidence(
                work_unit.period, reference="test:iva-wallet-engine-lifecycle-gate", operation=operation
            ),
        )

        assert revision.casilla_values[_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA] == Decimal("1200.00")
        assert revision.casilla_values[_M303_COMPENSACION_APLICADA_CASILLA] == Decimal("1000.00")
        assert revision.casilla_values[_M303_POSTERIOR_CASILLA] == Decimal("200.00")
        assert revision.casilla_values[_M303_RESULTADO_CASILLA] == Decimal("0.00")
        decision = _require_persisted_iva_compensation_decision_matches_revision(work_unit, revision)
        assert decision is not None
        assert decision.divergence == "wallet_only"


@pytest.mark.parametrize("age_days", [31, 32])
def test_persisted_wallet_ages_before_lifecycle_use(
    tmp_path: Path, age_days: int, *, operation: PinnedAuthorityOperation
) -> None:
    with frozen_clock(_DECIDED_AT + timedelta(days=age_days)), _secure_backend(tmp_path):
        _store_operator_profile()
        _save_wallet_gate_decision(amount=Decimal("1200"))
        work_unit, revision = _work_unit_and_revision_for_wallet_gate(
            compensation_amount=Decimal("1200"), operation=operation
        )
        if age_days == 31:
            assert _require_persisted_iva_compensation_decision_matches_revision(work_unit, revision) is not None
        else:
            supplied = IvaWalletDecisionRepository().load_decision(_TAXPAYER_NIF, work_unit.period)
            refreshed = resolve_iva_compensation_decision_for_calculation(
                work_unit,
                snapshot=_snapshot_303(),
                operation=operation,
                supplied_decision=supplied,
                repository=IvaWalletDecisionRepository(),
                observation_repository=CalculationObservationRepository(),
                history_repository=IvaCompensationHistoryRepository(),
                binding_values=None,
                backend_binding_values=None,
                casilla_inputs=None,
                backend_casilla_inputs=None,
                profile_values={"identity.tax_id": _TAXPAYER_NIF},
            )
            assert isinstance(refreshed, IvaCompensationReconciliationDecision) and refreshed.blocked
            with pytest.raises(ModeloIvaWalletReconciliationBlocked):
                _require_persisted_iva_compensation_decision_matches_revision(work_unit, revision)
            decision = IvaWalletDecisionRepository().load_decision(_TAXPAYER_NIF, work_unit.period)
            assert decision is not None and decision.stale_wallet and decision.blocked
            assert decision.wallet_captured_at == _DECIDED_AT


@pytest.mark.parametrize("action", ["calculate", "verify", "file"])
def test_backdated_lifecycle_clock_refuses_before_wallet_decision_persistence(
    tmp_path: Path, action: str, *, operation: PinnedAuthorityOperation
) -> None:
    """A refused clock must not replace stale authority with a backdated fresh decision."""
    lifecycle_at = _DECIDED_AT + timedelta(days=32)
    backdated_at = _DECIDED_AT + timedelta(days=31)
    with frozen_clock(lifecycle_at), _secure_backend(tmp_path):
        _store_operator_profile()
        snapshot = _snapshot_303(period="1T")
        work_unit, work_repo, calc_repo, event_repo = _work_unit_repositories_with_modelo_303_work_unit(
            snapshot, clock=lifecycle_at, operation=operation
        )
        decisions = IvaWalletDecisionRepository(operation=operation)
        observations = CalculationObservationRepository()
        profile = workflow_profile().model_copy(update={"activity_start_date": date(2026, 1, 1)})
        revision = None
        verification = None
        if action != "calculate":
            fresh = _reconcile_modelo_303_iva_compensation(
                snapshot,
                taxpayer_nif=_TAXPAYER_NIF,
                wallet=_wallet_observation(
                    pending=Decimal("0"), target_period=work_unit.period, captured_at=lifecycle_at
                ),
                repository=observations,
                decision_repository=decisions,
                decided_at=lifecycle_at,
                local_recurrence=None,
                prefill_report=BindingPrefillReport(prefilled=(), binding_values={}),
            )
            revision = _calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
                backend_binding_values=_modelo_303_engine_inputs(),
                iva_compensation_decision=fresh.decision,
                filing_period_date=date(2026, 3, 31),
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                bucket_event_repository=event_repo,
                clock=lifecycle_at,
                filing_instance_evidence=general_m303_filing_evidence(
                    work_unit.period, reference="test:iva-wallet-backdated-clock", operation=operation
                ),
            )
            if action == "file":
                verification = _verify_modelo_revision(
                    revision.calculation_revision_id,
                    actor="operator",
                    workflow_profile=profile,
                    settings=ready_clave_settings(_TAXPAYER_NIF),
                    clock=lifecycle_at,
                    operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                )
                assert verification.granted_verificado_completo is True

        # At the refused operation instant this same capture is exactly 31 days
        # old, so a misplaced wallet refresh would replace the blocked decision.
        stale = _reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=_TAXPAYER_NIF,
            wallet=_wallet_observation(pending=Decimal("0"), target_period=work_unit.period),
            repository=observations,
            decision_repository=decisions,
            decided_at=lifecycle_at,
            local_recurrence=None,
            prefill_report=BindingPrefillReport(prefilled=(), binding_values={}),
        ).decision
        assert stale.blocked is True and stale.stale_wallet is True
        assert stale.wallet_captured_at == _DECIDED_AT
        history_before = load_decision_history(decisions, _TAXPAYER_NIF, work_unit.period)
        assert decisions.load_decision(_TAXPAYER_NIF, work_unit.period) == stale
        assert history_before and stale in history_before

        with pytest.raises(ModeloLifecycleClockPrecedesError) as exc_info:
            if action == "calculate":
                _calculate_modelo_revision(
                    work_unit.work_unit_id,
                    actor="operator",
                    casilla_inputs={},
                    binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
                    backend_binding_values=_modelo_303_engine_inputs(),
                    filing_period_date=date(2026, 3, 31),
                    work_unit_repository=work_repo,
                    calculation_repository=calc_repo,
                    bucket_event_repository=event_repo,
                    clock=backdated_at,
                    filing_instance_evidence=general_m303_filing_evidence(
                        work_unit.period, reference="test:iva-wallet-backdated-clock", operation=operation
                    ),
                )
            elif action == "verify":
                assert revision is not None
                _verify_modelo_revision(
                    revision.calculation_revision_id,
                    actor="operator",
                    workflow_profile=profile,
                    settings=ready_clave_settings(_TAXPAYER_NIF),
                    clock=backdated_at,
                    operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                )
            else:
                assert revision is not None and verification is not None
                file_modelo_revision(
                    revision.calculation_revision_id,
                    approved_verification_report_id=verification.verification_report_id,
                    certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
                    operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                    ports=build_filing_action_ports(bucket_id=work_unit.bucket_id, operation=operation),
                    actor="operator",
                    workflow_profile=profile,
                    operation=operation,
                    settings=ready_clave_settings(_TAXPAYER_NIF),
                    clock=backdated_at,
                )

        assert exc_info.value.context is not None
        assert exc_info.value.context["operation"] == action
        assert decisions.load_decision(_TAXPAYER_NIF, work_unit.period) == stale
        assert load_decision_history(decisions, _TAXPAYER_NIF, work_unit.period) == history_before
