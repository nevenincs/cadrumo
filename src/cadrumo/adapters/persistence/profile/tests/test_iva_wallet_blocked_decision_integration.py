"""Blocked IVA wallet decision integration tests for Modelo 303."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.calculation_observations import (
    CalculationObservationRepository,
    IvaWalletDecisionRepository,
)
from cadrumo.adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests._iva_wallet_engine_support import (
    _DECIDED_AT,
    _TARGET_PERIOD,
    _TARGET_YEAR,
    _TAXPAYER_NIF,
    _modelo_303_engine_inputs,
    _period,
    _secure_backend,
    _snapshot_303,
    _store_operator_profile,
    _store_prior_303_compensation,
    _wallet_observation,
    _work_unit_repositories_with_modelo_303_work_unit,
)
from cadrumo.application.calculations.binding_prefill import (
    BindingPrefillReport,
    LocalIvaCompensationRecurrence,
    extract_modelo_303_local_iva_compensation_recurrence,
)
from cadrumo.application.calculations.iva_wallet_reconciliation import (
    IvaCompensationReconciliationReport,
    reconcile_modelo_303_iva_compensation,
)
from cadrumo.application.calculations.tests.filing_evidence import general_m303_filing_evidence
from cadrumo.application.modelo.calculation_actions import calculate_modelo_revision
from cadrumo.application.modelo.iva_wallet_gate import ModeloIvaWalletReconciliationBlocked
from cadrumo.core.casilla_id import CasillaId
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.bindings import BindingId
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.iva_compensation.reconciliation import (
    DEFAULT_MAX_WALLET_AGE_DAYS,
    IvaCompensationReconciliationDecision,
    IvaCompensationWalletObservationProtocol,
)
from cadrumo.domain.modelos.calculation_revision import CalculationRevision
from cadrumo.domain.modelos.calculation_revision_m303_handoff import FilingInstanceEvidence
from cadrumo.entrypoints.adapter_composition import build_calculation_action_ports

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _calculate_modelo_revision(
    work_unit_id: str,
    *,
    actor: str,
    casilla_inputs: Mapping[CasillaId, Decimal],
    binding_values: Mapping[BindingId, Decimal],
    iva_compensation_decision: IvaCompensationReconciliationDecision | None,
    filing_period_date: date,
    work_unit_repository: WorkUnitCatalogueRepository,
    clock: datetime,
    filing_instance_evidence: FilingInstanceEvidence,
) -> CalculationRevision:
    bucket_id = work_unit_repository.bucket_id
    if bucket_id is None:
        raise RuntimeError("Modelo calculation test requires a resolved work-unit repository bucket")
    with bundled_indexed_authority().operation() as operation:
        return calculate_modelo_revision(
            work_unit_id,
            ports=build_calculation_action_ports(bucket_id=bucket_id, operation=operation),
            actor=actor,
            casilla_inputs=casilla_inputs,
            binding_values=binding_values,
            iva_compensation_decision=iva_compensation_decision,
            filing_period_date=filing_period_date,
            clock=clock,
            filing_instance_evidence=filing_instance_evidence,
        )


def _reconcile_modelo_303_iva_compensation(
    snapshot: RegistrySnapshot,
    *,
    taxpayer_nif: str,
    wallet: IvaCompensationWalletObservationProtocol | None,
    repository: CalculationObservationRepository,
    decided_at: datetime,
    max_wallet_age_days: int,
    local_recurrence: LocalIvaCompensationRecurrence | None,
    prefill_report: BindingPrefillReport,
    persist: bool,
) -> IvaCompensationReconciliationReport:
    with bundled_indexed_authority().operation() as operation:
        return reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=taxpayer_nif,
            wallet=wallet,
            repository=repository,
            decision_repository=IvaWalletDecisionRepository(),
            decided_at=decided_at,
            max_wallet_age_days=max_wallet_age_days,
            local_recurrence=local_recurrence,
            prefill_report=prefill_report,
            persist=persist,
            operation=operation,
        )


def _extract_modelo_303_local_iva_compensation_recurrence(
    snapshot: RegistrySnapshot,
    *,
    repository: CalculationObservationRepository,
    captured_at: datetime,
    iva_history_repository: IvaCompensationHistoryRepository,
) -> tuple[LocalIvaCompensationRecurrence | None, BindingPrefillReport]:
    with bundled_indexed_authority().operation() as operation:
        return extract_modelo_303_local_iva_compensation_recurrence(
            snapshot,
            operation=operation,
            repository=repository,
            captured_at=captured_at,
            iva_history_repository=iva_history_repository,
        )


#: The blocked-decision reasons the refusal carries, keyed by the divergence
#: the decision reports. Both wallet directions share one reason: the
#: taxonomy distinguishes divergence from staleness, not which side is higher.
_BLOCKED_REASON_KEY_BY_DIVERGENCE = {
    "wallet_higher": "application.iva_wallet.decision_reason.wallet_local_recurrence_divergence",
    "wallet_lower": "application.iva_wallet.decision_reason.wallet_local_recurrence_divergence",
    "wallet_stale": "application.iva_wallet.decision_reason.stale_wallet_local_recurrence_requires_override",
    "missing": "application.iva_wallet.decision_reason.no_usable_authority",
}


def _assert_blocked_wallet_decision_refuses_real_modelo_303_calculation(
    *,
    snapshot: RegistrySnapshot,
    decision: IvaCompensationReconciliationDecision,
    expected_divergence: str,
) -> None:
    with bundled_indexed_authority().operation() as operation:
        work_unit, work_repo, calc_repo, _event_repo = _work_unit_repositories_with_modelo_303_work_unit(
            snapshot,
            operation=operation,
        )
        filing_instance_evidence = general_m303_filing_evidence(
            work_unit.period,
            reference="test:iva-wallet-blocked-decision",
            operation=operation,
        )
    # The refusal names its decision reason, and that taxonomy no longer
    # distinguishes a higher wallet from a lower one -- both are one
    # divergence reason. Direction is still proven, by the
    # `decision.divergence` assertion each caller makes; this asserts the
    # refusal the operator actually receives.
    expected_reason_key = _BLOCKED_REASON_KEY_BY_DIVERGENCE[expected_divergence]
    with pytest.raises(ModeloIvaWalletReconciliationBlocked) as blocked:
        _calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator",
            casilla_inputs={},
            binding_values=_modelo_303_engine_inputs(),
            iva_compensation_decision=decision,
            filing_period_date=date(2026, 6, 30),
            work_unit_repository=work_repo,
            clock=_DECIDED_AT,
            filing_instance_evidence=filing_instance_evidence,
        )
    assert len(calc_repo.load()) == 0
    assert blocked.value.translated_message == expected_reason_key


def _blocked_wallet_decision(
    *,
    prior_amount: Decimal | None,
    wallet_amount: Decimal | None,
    wallet_age_days: int,
    max_wallet_age_days: int,
) -> tuple[RegistrySnapshot, IvaCompensationReconciliationDecision]:
    observation_repo = CalculationObservationRepository()
    if prior_amount is not None:
        _store_prior_303_compensation(observation_repo, amount=prior_amount)
    snapshot = _snapshot_303()
    wallet = (
        _wallet_observation(pending=wallet_amount, captured_at=_DECIDED_AT - timedelta(days=wallet_age_days))
        if wallet_amount is not None
        else None
    )
    local_recurrence, prefill_report = _extract_modelo_303_local_iva_compensation_recurrence(
        snapshot,
        repository=observation_repo,
        captured_at=_DECIDED_AT,
        iva_history_repository=IvaCompensationHistoryRepository(),
    )
    report = _reconcile_modelo_303_iva_compensation(
        snapshot,
        taxpayer_nif=_TAXPAYER_NIF,
        wallet=wallet,
        repository=observation_repo,
        decided_at=_DECIDED_AT,
        max_wallet_age_days=max_wallet_age_days,
        local_recurrence=local_recurrence,
        prefill_report=prefill_report,
        persist=True,
    )
    return snapshot, report.decision


def test_unpersisted_wallet_decision_cannot_feed_modelo_303_engine(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        observation_repo = CalculationObservationRepository()
        _store_prior_303_compensation(observation_repo, amount=Decimal("1200.00"))
        snapshot = _snapshot_303()
        local_recurrence, prefill_report = _extract_modelo_303_local_iva_compensation_recurrence(
            snapshot,
            repository=observation_repo,
            captured_at=_DECIDED_AT,
            iva_history_repository=IvaCompensationHistoryRepository(),
        )
        report = _reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=_TAXPAYER_NIF,
            wallet=_wallet_observation(pending=Decimal("1200.00")),
            repository=observation_repo,
            decided_at=_DECIDED_AT,
            max_wallet_age_days=DEFAULT_MAX_WALLET_AGE_DAYS,
            persist=False,
            local_recurrence=local_recurrence,
            prefill_report=prefill_report,
        )
        assert (
            IvaWalletDecisionRepository().load_decision(
                _TAXPAYER_NIF,
                _period(_TARGET_YEAR, _TARGET_PERIOD),
            )
            is None
        )

        with bundled_indexed_authority().operation() as operation:
            work_unit, work_repo, calc_repo, _event_repo = _work_unit_repositories_with_modelo_303_work_unit(
                snapshot,
                operation=operation,
            )
            filing_instance_evidence = general_m303_filing_evidence(
                work_unit.period,
                reference="test:iva-wallet-blocked-decision",
                operation=operation,
            )

        with pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info:
            _calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values=_modelo_303_engine_inputs(),
                iva_compensation_decision=report.decision,
                filing_period_date=date(2026, 6, 30),
                work_unit_repository=work_repo,
                clock=_DECIDED_AT,
                filing_instance_evidence=filing_instance_evidence,
            )
        assert exc_info.value.translated_message == "application.modelo.errors.iva_wallet_not_seeded"
        assert not hasattr(exc_info.value, "suggestion")
        assert exc_info.value.precondition_failure.scenario_id == "modelo.work.calculate.iva_wallet.not_seeded"
        assert len(calc_repo.load()) == 0


@pytest.mark.parametrize(
    (
        "prior_amount",
        "wallet_amount",
        "wallet_age_days",
        "max_wallet_age_days",
        "expected_divergence",
        "expected_selected_authority",
    ),
    (
        (Decimal("800.00"), Decimal("1200.00"), 0, 31, "wallet_higher", None),
        (Decimal("1200.00"), Decimal("800.00"), 0, 31, "wallet_lower", None),
        (Decimal("800.00"), Decimal("1200.00"), 40, 31, "wallet_stale", None),
        (None, None, 0, 31, "missing", "missing"),
    ),
    ids=("wallet-higher", "wallet-lower", "wallet-stale", "missing-wallet-and-local-history"),
)
def test_blocked_wallet_divergence_refuses_real_modelo_303_calculation_before_persisting_revision(
    tmp_path: Path,
    prior_amount: Decimal | None,
    wallet_amount: Decimal | None,
    wallet_age_days: int,
    max_wallet_age_days: int,
    expected_divergence: str,
    expected_selected_authority: str | None,
) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        snapshot, decision = _blocked_wallet_decision(
            prior_amount=prior_amount,
            wallet_amount=wallet_amount,
            wallet_age_days=wallet_age_days,
            max_wallet_age_days=max_wallet_age_days,
        )

        assert decision.divergence == expected_divergence
        assert decision.blocked is True
        assert decision.stale_wallet is (expected_divergence == "wallet_stale")
        if expected_selected_authority is not None:
            assert decision.selected_authority == expected_selected_authority
        _assert_blocked_wallet_decision_refuses_real_modelo_303_calculation(
            snapshot=snapshot,
            decision=decision,
            expected_divergence=expected_divergence,
        )


def test_persisted_blocked_wallet_decision_is_replayed_by_modelo_303_calculation(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        observation_repo = CalculationObservationRepository()
        _store_prior_303_compensation(observation_repo, amount=Decimal("800.00"))
        snapshot = _snapshot_303()
        local_recurrence, prefill_report = _extract_modelo_303_local_iva_compensation_recurrence(
            snapshot,
            repository=observation_repo,
            captured_at=_DECIDED_AT,
            iva_history_repository=IvaCompensationHistoryRepository(),
        )
        report = _reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=_TAXPAYER_NIF,
            wallet=_wallet_observation(pending=Decimal("1200.00")),
            repository=observation_repo,
            decided_at=_DECIDED_AT,
            max_wallet_age_days=DEFAULT_MAX_WALLET_AGE_DAYS,
            local_recurrence=local_recurrence,
            prefill_report=prefill_report,
            persist=True,
        )
        assert report.decision.blocked is True

        with bundled_indexed_authority().operation() as operation:
            work_unit, work_repo, calc_repo, _event_repo = _work_unit_repositories_with_modelo_303_work_unit(
                snapshot,
                operation=operation,
            )
            filing_instance_evidence = general_m303_filing_evidence(
                work_unit.period,
                reference="test:iva-wallet-blocked-decision",
                operation=operation,
            )

        with pytest.raises(
            ModeloIvaWalletReconciliationBlocked,
            match="application\\.iva_wallet\\.decision_reason\\.wallet_local_recurrence_divergence",
        ):
            _calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values=_modelo_303_engine_inputs(),
                iva_compensation_decision=None,
                filing_period_date=date(2026, 6, 30),
                work_unit_repository=work_repo,
                clock=_DECIDED_AT,
                filing_instance_evidence=filing_instance_evidence,
            )
    assert len(calc_repo.load()) == 0
