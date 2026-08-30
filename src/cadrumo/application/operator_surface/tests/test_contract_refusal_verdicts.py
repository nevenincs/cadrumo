"""Typed refusal coverage for the operator-surface contract helpers."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from ....core.operator_action_enums import ActionConditionality, NoRecoveryOutcome
from ..contract import require_accepted_root, resolve_source_kind_alias
from ..errors import OperatorSurfaceContractError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize(
    ("call", "condition_id", "fact_key", "fact_value"),
    (
        (lambda: require_accepted_root("setup"), "operator_surface.accepted_root", "requested_root", "setup"),
        (
            lambda: resolve_source_kind_alias("not-a-source-kind"),
            "operator_surface.source_kind_alias",
            "requested_source_kind",
            "not-a-source-kind",
        ),
    ),
)
def test_contract_refusals_carry_terminal_typed_verdict(
    call: Callable[[], object],
    condition_id: str,
    fact_key: str,
    fact_value: str,
) -> None:
    with pytest.raises(OperatorSurfaceContractError) as raised:
        call()

    verdict = raised.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == condition_id
    assert verdict.action is None
    assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL
    assert verdict.evidence[0].condition_id == condition_id
    assert verdict.evidence[0].values[fact_key] == fact_value
