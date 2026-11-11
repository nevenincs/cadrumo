"""Activity-start authority at the first-period IVA wallet boundary."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.calculation_observations import (
    CalculationObservationRepository,
    IvaWalletDecisionRepository,
)
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    load_test_profile_record,
    replace_test_profile_record,
)
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.iva_compensation.reconciliation import (
    IvaCompensationDecisionReason,
)
from cadrumo.entrypoints.tests.profile_persistence.iva_wallet_engine_support import (
    BUCKET_ID,
    TARGET_YEAR,
    TAXPAYER_NIF,
    create_modelo_303_work_unit,
    period,
    secure_backend,
    snapshot_303,
    store_operator_profile,
    work_unit_repositories,
)

from .iva_wallet_engine_support import resolve_without_caller_inputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _first_period_work_unit(*, operation: PinnedAuthorityOperation):

    snapshot = snapshot_303(period="1T")

    work_units, _, _ = work_unit_repositories()

    return snapshot, create_modelo_303_work_unit(snapshot, work_unit_repository=work_units, operation=operation)


def test_declared_activity_start_persists_an_uncontrasted_first_period_zero(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The actual grounding path stores the weaker, honest authority identity."""

    with secure_backend(tmp_path):
        store_operator_profile()

        snapshot, work_unit = _first_period_work_unit(operation=operation)

        decision = resolve_without_caller_inputs(
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
                TAXPAYER_NIF,
                period(TARGET_YEAR, "1T"),
            )
            == decision
        )


def test_missing_activity_start_still_blocks_the_first_period_zero(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """Absence remains fail-closed; the advisory must not become a grant."""

    with secure_backend(tmp_path):
        store_operator_profile()

        profile = load_test_profile_record(BUCKET_ID)

        replace_test_profile_record(
            profile.model_copy(
                update={
                    "facts": tuple(fact for fact in profile.facts if fact.path != "censo.activity_start_date"),
                },
            ),
        )

        snapshot, work_unit = _first_period_work_unit(operation=operation)

        decision = resolve_without_caller_inputs(
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

        # The blocked decision is refused at calculation, which therefore stores none.
        assert IvaWalletDecisionRepository().load_decision(TAXPAYER_NIF, period(TARGET_YEAR, "1T")) is None
