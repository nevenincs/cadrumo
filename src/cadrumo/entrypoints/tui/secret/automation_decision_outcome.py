"""Safe public result facts retained after an automation decision settles."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from ....adapters.local_runtime.automation_decision import AutomationDecisionCompletion, AutomationDecisionRunError
from ....application.operations.models import OperationId
from ....core.operations import OperationEffect, OperationTerminalCondition


@dataclass(frozen=True, slots=True)
class AutomationDecisionUiOutcome:
    """Settlement facts safe for display; no password, credential or exception is retained."""

    operation_id: OperationId | None
    terminal_condition: OperationTerminalCondition | None
    effect: OperationEffect | None
    reason: str | None
    completed: bool
    access_lost: bool


def decision_task_outcome(task: asyncio.Task[AutomationDecisionCompletion]) -> AutomationDecisionUiOutcome:
    """Convert worker settlement to public operation facts without retaining its error object."""
    try:
        completion = task.result()
    except AutomationDecisionRunError as error:
        return AutomationDecisionUiOutcome(
            error.operation_id, error.terminal_condition, error.effect, error.reason, False, False
        )
    except BaseException:
        return AutomationDecisionUiOutcome(None, None, None, None, False, False)
    return AutomationDecisionUiOutcome(
        completion.operation_id, OperationTerminalCondition.SUCCEEDED, completion.effect, None, True, False
    )
