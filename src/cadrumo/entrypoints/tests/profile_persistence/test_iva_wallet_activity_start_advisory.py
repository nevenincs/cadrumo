"""Activity-start authority at the first-period IVA wallet boundary."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.calculation_observations import (
    CalculationObservationRepository,
    IvaWalletDecisionRepository,
)
from cadrumo.adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    load_test_profile_record,
    replace_test_profile_record,
)
from cadrumo.application.modelo.iva_wallet_gate import resolve_iva_compensation_decision_for_calculation
from cadrumo.application.user_profile.projections import profile_path_values_for_bucket
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.iva_compensation.reconciliation import (
    IvaCompensationDecisionReason,
    IvaCompensationReconciliationDecision,
)
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.entrypoints.tests.profile_persistence._iva_wallet_engine_support import (
    _BUCKET_ID,
    _TAXPAYER_NIF,
    _create_modelo_303_work_unit,
    _period,
    _secure_backend,
    _snapshot_303,
    _store_operator_profile,
    _work_unit_repositories,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _resolve_without_caller_inputs(
    work_unit: WorkUnit,
    *,
    snapshot: RegistrySnapshot,
    operation: PinnedAuthorityOperation,
    repository: IvaWalletDecisionRepository,
    observation_repository: CalculationObservationRepository,
) -> IvaCompensationReconciliationDecision | None:
    """Drive the calculation gate with no supplied, persisted or caller-bound compensation."""
    decision = resolve_iva_compensation_decision_for_calculation(
        work_unit,
        snapshot=snapshot,
        operation=operation,
        supplied_decision=None,
        repository=repository,
        observation_repository=observation_repository,
        history_repository=IvaCompensationHistoryRepository(),
        binding_values=None,
        backend_binding_values=None,
        casilla_inputs=None,
        backend_casilla_inputs=None,
        profile_values=profile_path_values_for_bucket(work_unit.bucket_id),
    )
    assert decision is None or isinstance(decision, IvaCompensationReconciliationDecision)
    return decision


def _first_period_work_unit(*, operation: PinnedAuthorityOperation):

    snapshot = _snapshot_303(period="1T")

    work_units, _, _ = _work_unit_repositories()

    return snapshot, _create_modelo_303_work_unit(snapshot, work_unit_repository=work_units, operation=operation)


def test_declared_activity_start_persists_an_uncontrasted_first_period_zero(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The actual grounding path stores the weaker, honest authority identity."""

    with _secure_backend(tmp_path):
        _store_operator_profile()

        snapshot, work_unit = _first_period_work_unit(operation=operation)

        decision = _resolve_without_caller_inputs(
            work_unit,
            snapshot=snapshot,
            operation=operation,
            repository=IvaWalletDecisionRepository(),
            observation_repository=CalculationObservationRepository(),
        )

        assert decision is not None

        assert decision.selected_amount == 0

        assert decision.reason_identity is IvaCompensationDecisionReason.FIRST_PERIOD_ZERO_ACTIVITY_START_UNCONTRASTED

        assert (
            IvaWalletDecisionRepository().load_decision(
                _TAXPAYER_NIF,
                _period(2026, "1T"),
            )
            == decision
        )


def test_missing_activity_start_still_blocks_the_first_period_zero(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """Absence remains fail-closed; the advisory must not become a grant."""

    with _secure_backend(tmp_path):
        _store_operator_profile()

        profile = load_test_profile_record(_BUCKET_ID)

        replace_test_profile_record(
            profile.model_copy(
                update={
                    "facts": tuple(fact for fact in profile.facts if fact.path != "censo.activity_start_date"),
                },
            ),
        )

        snapshot, work_unit = _first_period_work_unit(operation=operation)

        decision = _resolve_without_caller_inputs(
            work_unit,
            snapshot=snapshot,
            operation=operation,
            repository=IvaWalletDecisionRepository(),
            observation_repository=CalculationObservationRepository(),
        )

        assert decision is not None

        assert decision.blocked is True

        assert decision.selected_amount is None

        assert decision.reason_identity is IvaCompensationDecisionReason.NO_USABLE_AUTHORITY

        assert (
            IvaWalletDecisionRepository().load_decision(
                _TAXPAYER_NIF,
                _period(2026, "1T"),
            )
            == decision
        )
