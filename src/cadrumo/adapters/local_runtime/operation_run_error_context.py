"""Recovery context carried by a submitted operation's local-runtime run error."""

from __future__ import annotations

from ...application.operations.models import OperationId
from ...core.operations import OperationEffect, OperationTerminalCondition


def operation_run_error_context(
    *,
    code: str,
    operation_id: OperationId,
    terminal_condition: OperationTerminalCondition | None,
    effect: OperationEffect | None,
) -> dict[str, str]:
    """Return the safe reason, recovery identity and only observed settlement facts.

    An unobserved effect is written as ``unknown`` so the context never implies
    that a submitted operation had no effect; an unobserved terminal condition
    is omitted rather than invented.
    """
    context = {
        "reason": code,
        "operation_id": str(operation_id),
        "effect": effect.value if effect is not None else "unknown",
    }
    if terminal_condition is not None:
        context["terminal_condition"] = terminal_condition.value
    return context


__all__ = ["operation_run_error_context"]
