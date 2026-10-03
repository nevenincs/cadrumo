"""Preserve registered CLI refusal detail, public failure facts and cleanup ownership."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel

from ...adapters.local_runtime.framing import RuntimeTransportCleanup
from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient, frontend_failure_code
from ...application.operations.error_detail import (
    OperationErrorDetailKind,
    OperationErrorDetailV1,
)
from ...application.operations.models import OperationId
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.async_cleanup import AsyncResourceCleanupError
from ...core.errors.error_codes import get_registered_error_code, get_registered_error_code_by_code
from ...core.errors.hierarchy import InternalInvariantError
from ...core.operations import OperationEffect, OperationTerminalCondition
from .errors import (
    CliOperationStillRunningError,
    CliOutboundPayloadBoundaryError,
    CliRecordedOperationError,
    CliRefusedBoundaryError,
    CliUnexpectedBoundaryError,
)
from .registered_operation_contracts import RegisteredOperationCompletion, RegisteredOperationProgress


def map_registered_transport_failure(
    client: RuntimeFrontendClient, operation_id: OperationId, error: Exception, progress: RegisteredOperationProgress
) -> CliRefusedBoundaryError:
    """Map public failure facts while preserving the original transport cleanup owner."""
    mapped = submitted_operation_error(
        operation_id,
        frontend_failure_code(error),
        terminal_condition=progress.condition,
        effect=progress.effect,
        refusal_code=progress.refusal_code,
    )
    for field in ("async_cleanup_error", "cleanup_error"):
        cleanup = error.__dict__.get(field)
        if isinstance(cleanup, AsyncResourceCleanupError):
            mapped.__dict__[field] = cleanup
    if isinstance(error.__dict__.get("_runtime_transport_cleanup"), RuntimeTransportCleanup):
        mapped.__dict__["_runtime_transport_cleanup"] = client.cleanup_owner(primary_error=error)
    return mapped


def submitted_operation_error(
    operation_id: OperationId,
    code: str,
    *,
    terminal_condition: OperationTerminalCondition | None,
    effect: OperationEffect | None,
    refusal_code: str | None = None,
    detail: OperationErrorDetailV1 | None = None,
    diagnostic_ref: str | None = None,
) -> CliRefusedBoundaryError:
    """Retain an exact operation ID and its last observed effect on refusal.

    With the operation's recorded error detail, the error is the one the
    stopped executor raised: its code, message, context and verdict. Without
    it, a failure that recorded no registered code is an unexpected internal
    fault, never a refusal; anything else keeps its registered code.
    """
    facts = {
        "operation_id": str(operation_id),
        "effect": effect.value if effect is not None else "unknown",
    }
    if terminal_condition is not None:
        facts["terminal_condition"] = terminal_condition.value
    if detail is not None:
        return detailed_registered_operation_error(detail, facts)
    if (
        terminal_condition is OperationTerminalCondition.FAILED
        and refusal_code is None
        and code == OperationTerminalCondition.FAILED.value
    ):
        unexpected = get_registered_error_code(CliUnexpectedBoundaryError)
        fault: dict[str, object] = dict(facts)
        if diagnostic_ref is not None:
            fault["diagnostic_ref"] = diagnostic_ref
        return CliRecordedOperationError(unexpected.code, context=fault, translated_message=unexpected.message_key)
    context = {**facts, "reason": code}
    if refusal_code is not None:
        context["refusal_code"] = refusal_code
    try:
        registered = get_registered_error_code_by_code(code)
    except InternalInvariantError:
        return CliRefusedBoundaryError(code, context=context)
    return CliRecordedOperationError(registered.code, context=context)


def invalid_completion_error[ResultT: BaseModel](
    completed: RegisteredOperationCompletion[ResultT],
) -> CliRefusedBoundaryError:
    """Refuse a settled result its command cannot correlate with the request or receipt.

    The refusal is an invalid frame that still names the operation and keeps
    its observed terminal condition, effect and refusal code, so a committed
    effect is never hidden behind a client-side validation failure.
    """
    return submitted_operation_error(
        completed.operation_id,
        RuntimeRefusalCode.INVALID_FRAME.value,
        terminal_condition=completed.terminal_condition,
        effect=completed.effect,
        refusal_code=completed.refusal_code,
    )


def detailed_registered_operation_error(
    detail: OperationErrorDetailV1, facts: Mapping[str, str]
) -> CliRecordedOperationError:
    """Rebuild the stopped executor's own error from its recorded public detail."""
    context: dict[str, object] = dict(detail.context_mapping())
    for key, value in facts.items():
        context.setdefault(key, value)
    if detail.context_entries_omitted:
        context.setdefault("context_entries_omitted", detail.context_entries_omitted)
    if detail.kind is OperationErrorDetailKind.RECORD_VALIDATION:
        # A record the application built failed its own contract: the
        # in-process boundary's classification, with the worker's projection.
        outbound = get_registered_error_code(CliOutboundPayloadBoundaryError)
        return CliRecordedOperationError(outbound.code, context=context, translated_message=outbound.message_key)
    if detail.error_code is None:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return CliRecordedOperationError(
        detail.error_code,
        context=context,
        translated_message=detail.message_key,
        precondition_verdict=detail.precondition_verdict(),
    )


def registered_operation_still_running(
    operation_id: OperationId, effect: OperationEffect | None, check_command: str | None
) -> CliOperationStillRunningError:
    """Report an admitted operation the command stopped waiting for, without claiming its outcome.

    A running operation may still commit, so its effect is unknown unless a
    committed effect was already observed.
    """
    observed = (
        effect
        if effect is not None and effect in {OperationEffect.UPDATED, OperationEffect.PARTIAL}
        else OperationEffect.UNKNOWN
    )
    return CliOperationStillRunningError(
        operation_id=str(operation_id),
        effect=observed.value,
        check_command=check_command,
    )
