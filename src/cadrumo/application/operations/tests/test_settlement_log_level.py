"""A settled operation is logged at the level its typed condition and effect call for."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pytest

from cadrumo.tests.log_records import delivered_records

from ....core.operations import OperationEffect, OperationTerminalCondition
from ..models import OperationIdentity, OperationTerminalReceipt
from ..settlement_snapshot import log_settlement, settlement_log_level

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(1980, 1, 1, 12, 0, tzinfo=UTC)
_LOGGER_NAME = "cadrumo.application.operations.settlement_snapshot"


def _receipt(condition: OperationTerminalCondition, effect: OperationEffect) -> OperationTerminalReceipt:
    references: dict[str, str] = {}
    if condition is OperationTerminalCondition.SUCCEEDED:
        references["result_ref"] = "result:unit"
    elif condition is OperationTerminalCondition.REFUSED:
        references["refusal_ref"] = "REFUSED_MODELO_PROFILE_READINESS"
    return OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64, definition_id="operation.unit.settlement", subject_ref="subject:unit"
        ),
        revision=3,
        condition=condition,
        effect=effect,
        settled_at=_NOW,
        **references,
    )


_CASES = [
    (OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE, logging.INFO),
    (OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED, logging.INFO),
    (OperationTerminalCondition.REFUSED, OperationEffect.NONE, logging.INFO),
    (OperationTerminalCondition.REFUSED, OperationEffect.UNKNOWN, logging.WARNING),
    (OperationTerminalCondition.REFUSED, OperationEffect.UPDATED, logging.WARNING),
    (OperationTerminalCondition.REFUSED, OperationEffect.PARTIAL, logging.WARNING),
    (OperationTerminalCondition.FAILED, OperationEffect.NONE, logging.WARNING),
    (OperationTerminalCondition.FAILED, OperationEffect.UNKNOWN, logging.WARNING),
    (OperationTerminalCondition.CANCELLED, OperationEffect.NONE, logging.WARNING),
    (OperationTerminalCondition.TIMED_OUT, OperationEffect.NONE, logging.WARNING),
    (OperationTerminalCondition.INTERRUPTED, OperationEffect.NONE, logging.WARNING),
    (OperationTerminalCondition.INTERRUPTED, OperationEffect.UNKNOWN, logging.WARNING),
]


@pytest.mark.parametrize(("condition", "effect", "level"), _CASES)
def test_a_settlement_is_logged_at_the_level_its_condition_and_effect_call_for(
    caplog: pytest.LogCaptureFixture, condition: OperationTerminalCondition, effect: OperationEffect, level: int
) -> None:
    receipt = _receipt(condition, effect)

    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        log_settlement(receipt, cause="owner")

    (record,) = delivered_records(caplog, _LOGGER_NAME)
    assert settlement_log_level(condition, effect) == level
    assert record.levelno == level
    message = record.getMessage()
    assert f"condition={condition.value} effect={effect.value}" in message
    assert f"refusal={receipt.refusal_ref or '-'}" in message


def test_every_condition_and_effect_pair_has_a_level_that_only_a_clean_outcome_lowers() -> None:
    quiet = {
        (condition, effect)
        for condition in OperationTerminalCondition
        for effect in OperationEffect
        if settlement_log_level(condition, effect) == logging.INFO
    }

    assert quiet == {
        *((OperationTerminalCondition.SUCCEEDED, effect) for effect in OperationEffect),
        (OperationTerminalCondition.REFUSED, OperationEffect.NONE),
    }
