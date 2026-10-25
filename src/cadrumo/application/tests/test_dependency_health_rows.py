"""Setup rows in ``aeat config check``, built from rows as the components role reports them."""

from __future__ import annotations

import pytest

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ..dependency_contracts import (
    DependencyBlockedReason,
    DependencyCheckMode,
    DependencyItemKind,
    DependencyRecoveryAction,
    DependencyStaleReason,
    DependencyState,
    DependencyStatusRow,
)
from ..preflight import HealthSeverity, dependency_preflight_checks

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _local_ai(state: DependencyState, **fields: object) -> DependencyStatusRow:
    return DependencyStatusRow.model_validate(
        {"item_id": "local_ai", "kind": DependencyItemKind.LOCAL_AI, "mode": DependencyCheckMode.QUICK, "state": state}
        | fields
    )


def _rows() -> tuple[DependencyStatusRow, ...]:
    return (
        DependencyStatusRow(
            item_id="browser",
            kind=DependencyItemKind.BROWSER,
            mode=DependencyCheckMode.QUICK,
            state=DependencyState.READY,
            version="1187",
        ),
        _local_ai(
            DependencyState.FAILED,
            failure_category=DependencyFailureCategory.INTERRUPTED,
            recovery=DependencyRecoveryAction.RESUME,
            recovery_action_id="operator.provision.local_ai",
        ),
    )


def test_config_check_rows_grade_each_item_and_name_its_recovery() -> None:
    checks = dependency_preflight_checks(_rows())
    by_id = {check.check: check for check in checks}
    assert list(by_id) == ["setup:browser", "setup:local_ai"]

    browser = by_id["setup:browser"]
    assert (browser.healthy, browser.severity, browser.facts) == (
        True,
        HealthSeverity.OK,
        {"item": "browser", "state": "ready", "version": "1187"},
    )
    local_ai = by_id["setup:local_ai"]
    assert (local_ai.healthy, local_ai.severity) == (False, HealthSeverity.ERROR)
    assert local_ai.facts["reason"] == "interrupted"
    assert local_ai.precondition_verdict is not None
    assert local_ai.precondition_verdict.action is not None
    assert local_ai.precondition_verdict.action.action_id == "operator.provision.local_ai"


def test_a_computer_below_the_floor_warns_with_nothing_to_do_and_a_stale_item_is_usable() -> None:
    hardware = _local_ai(DependencyState.BLOCKED, blocked_reason=DependencyBlockedReason.HARDWARE)
    (check,) = dependency_preflight_checks((hardware,))
    assert (check.healthy, check.severity) == (False, HealthSeverity.WARN)
    assert check.precondition_verdict is not None and check.precondition_verdict.action is None

    stale = _local_ai(DependencyState.STALE, stale_reason=DependencyStaleReason.DIFFERENT_MODEL_VERSION)
    (check,) = dependency_preflight_checks((stale,))
    assert (check.healthy, check.severity) == (True, HealthSeverity.WARN)
