"""Real CLI bridge tests for fully materialised successful notice actions."""

from __future__ import annotations

import pytest

from ....application.operator_actions import ActionReference
from ....core.json_contract import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ResolvedActionArgument,
)
from .._common import resolve_notice_action

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_common_action_resolver_uses_the_live_surface_for_zero_and_required_inputs() -> None:
    zero_input_action = resolve_notice_action(
        action=ActionReference(action_id="operator.overview.status"),
    )

    assert zero_input_action.model_dump(mode="json") == {
        "action": {
            "action_id": "operator.overview.status",
            "target_command_key": "overview.status",
        },
        "argument_bindings": [],
    }

    with pytest.raises(ValueError, match=r"config\.profile\.sandbox\.restore: name"):
        resolve_notice_action(
            action=ActionReference(action_id="operator.profile.sandbox.restore"),
        )


def test_common_action_resolver_materialises_ledger_link_from_the_live_surface() -> None:
    action = resolve_notice_action(
        action=ActionReference(action_id="operator.ledger.link"),
        argument_bindings=(
            ResolvedActionArgument(
                argument_name="transaction_id",
                status=ActionArgumentStatus.RESOLVED,
                value="transaction-1",
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key="transaction_id",
            ),
            ResolvedActionArgument(
                argument_name="invoice_id",
                status=ActionArgumentStatus.RESOLVED,
                value="invoice-1",
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key="invoice_id",
            ),
        ),
    )

    assert action.action.target_command_key == "ledger.link"
    assert action.argument_bindings == (
        ResolvedActionArgument(
            argument_name="invoice_id",
            status=ActionArgumentStatus.RESOLVED,
            value="invoice-1",
            source=ActionArgumentSource.VERDICT_CONTEXT,
            source_key="invoice_id",
        ),
        ResolvedActionArgument(
            argument_name="transaction_id",
            status=ActionArgumentStatus.RESOLVED,
            value="transaction-1",
            source=ActionArgumentSource.VERDICT_CONTEXT,
            source_key="transaction_id",
        ),
    )


def test_common_action_resolver_accepts_modelo_calculate_verdict_context_binding() -> None:
    action = resolve_notice_action(
        action=ActionReference(action_id="operator.modelo.work.calculate"),
        argument_bindings=(
            ResolvedActionArgument(
                argument_name="work_unit_id",
                status=ActionArgumentStatus.RESOLVED,
                value="work-unit-1",
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key="work_unit_id",
            ),
        ),
    )

    assert action.model_dump(mode="json") == {
        "action": {
            "action_id": "operator.modelo.work.calculate",
            "target_command_key": "modelo.work.calculate",
        },
        "argument_bindings": [
            {
                "argument_name": "work_unit_id",
                "status": "resolved",
                "value": "work-unit-1",
                "source": "operator_action.verdict_context",
                "source_key": "work_unit_id",
                "source_evidence_id": None,
            },
        ],
    }
