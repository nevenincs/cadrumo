"""Activity-start authority at the first-period IVA wallet boundary."""

from __future__ import annotations

from pathlib import Path

import pytest

from ....domain.iva_compensation.reconciliation import IvaCompensationDecisionReason
from ....tests.profile_capsule import load_test_profile_record, replace_test_profile_record
from ...calculations.observations_repository import IvaWalletDecisionRepository
from .._iva_wallet_gate import lazily_reconcile_local_iva_compensation_for_work_unit
from ._iva_wallet_engine_support import (
    _BUCKET_ID,
    _TAXPAYER_NIF,
    _create_modelo_303_work_unit,
    _period,
    _secure_backend,
    _snapshot_303,
    _store_operator_profile,
    _work_unit_repositories,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _first_period_work_unit():
    snapshot = _snapshot_303(period="1T")
    work_units, _, _ = _work_unit_repositories()
    return snapshot, _create_modelo_303_work_unit(snapshot, work_unit_repository=work_units)


def test_declared_activity_start_persists_an_uncontrasted_first_period_zero(tmp_path: Path) -> None:
    """The actual grounding path stores the weaker, honest authority identity."""
    with _secure_backend(tmp_path):
        _store_operator_profile()
        snapshot, work_unit = _first_period_work_unit()

        decision = lazily_reconcile_local_iva_compensation_for_work_unit(
            work_unit,
            snapshot=snapshot,
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


def test_missing_activity_start_still_blocks_the_first_period_zero(tmp_path: Path) -> None:
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
        snapshot, work_unit = _first_period_work_unit()

        decision = lazily_reconcile_local_iva_compensation_for_work_unit(
            work_unit,
            snapshot=snapshot,
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
