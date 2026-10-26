"""Confirmation blockers retain their native reason beside one action class."""

from __future__ import annotations

import pytest

from ..confirmation_gate import OPERATOR_ACTION_BY_CONFIRMATION_BLOCK_REASON, ConfirmationBlockReason
from ..operator_action_enums import OperatorActionAxis

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_confirmation_action_projection_is_total_and_owned_beside_the_reason() -> None:
    assert set(OPERATOR_ACTION_BY_CONFIRMATION_BLOCK_REASON) == set(ConfirmationBlockReason)
    assert set(OPERATOR_ACTION_BY_CONFIRMATION_BLOCK_REASON.values()) <= set(OperatorActionAxis)
    assert (
        OPERATOR_ACTION_BY_CONFIRMATION_BLOCK_REASON[ConfirmationBlockReason.CLOSURE_DISCREPANCY]
        is OperatorActionAxis.RESOLVE_VALUE_DIVERGENCE
    )
    assert (
        OPERATOR_ACTION_BY_CONFIRMATION_BLOCK_REASON[ConfirmationBlockReason.AMBIGUOUS_IDENTITY]
        is OperatorActionAxis.RESOLVE_IDENTITY
    )
    assert (
        OPERATOR_ACTION_BY_CONFIRMATION_BLOCK_REASON[ConfirmationBlockReason.UNDETERMINED_ESTABLISHMENT]
        is OperatorActionAxis.SUPPLY_MANUAL_INPUT
    )
