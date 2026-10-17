"""Errors shared by command frontends at their operator boundary."""

from __future__ import annotations

import logging
from collections.abc import Mapping

from pydantic import BaseModel, ValidationError

from cadrumo.application.operator_actions.models import PreconditionVerdict
from cadrumo.core.errors.failure_report import log_boundary_failure, raising_product_frame
from cadrumo.core.errors.hierarchy import CadrumoError, RecordedRegisteredError
from cadrumo.core.errors.record_fault import internal_record_fault_context


class CliRefusedBoundaryError(CadrumoError):
    """Refuse a command without exposing a success-shaped JSON result."""


class CliUnexpectedBoundaryError(CadrumoError):
    """Wrap an unexpected callback exception without exposing its message."""

    def __init__(self, error: Exception) -> None:
        """Wrap the unexpected exception with its product-owned origin."""
        super().__init__(
            translated_message="errors.internal.internal_cli_unexpected_boundary",
            context={"exception_type": type(error).__name__, "raised_at": _raising_product_frame(error)},
        )
        self.original_exception = error


def _raising_product_frame(error: BaseException) -> str:
    return raising_product_frame(error) or "unknown"


def log_cli_boundary_failure(boundary: str, error: BaseException, *, durable: bool = True) -> str:
    """Log a failure a command frontend is about to render, returning its correlation id.

    Internal failures are logged at ERROR and expected refusals at INFO; both
    reach the durable log. ``durable=False`` is for a refusal raised before any
    command ran, which must not configure process state just to be logged. The
    record stays off stderr, which carries the error document.
    """
    from cadrumo.core.errors.error_codes import ErrorCategory, get_registered_error_code
    from cadrumo.core.logging import get_logger

    try:
        internal = get_registered_error_code(error).category is ErrorCategory.INTERNAL
    except Exception:
        internal = True
    return log_boundary_failure(
        get_logger(__name__),
        boundary,
        error,
        level=logging.ERROR if internal else logging.INFO,
        operator_document=True,
        durable=durable,
    )


class CliOutboundPayloadBoundaryError(CadrumoError):
    """Mark a typed outbound payload that failed its own validation."""

    def __init__(self, error: ValidationError, *, record: type[BaseModel] | None = None) -> None:
        """Wrap an invalid outbound record with its safe validation context."""
        super().__init__(
            translated_message="errors.internal.cli_outbound_payload_boundary",
            context=internal_record_fault_context(error, record=record),
        )
        self.original_exception = error


class CliRecordedOperationError(CliRefusedBoundaryError, RecordedRegisteredError):
    """Preserve the registered public failure detail and its optional verdict."""

    def __init__(
        self,
        registered_code: str,
        *,
        context: Mapping[str, object] | None = None,
        translated_message: str | None = None,
        precondition_verdict: PreconditionVerdict | None = None,
    ) -> None:
        """Retain the registered failure context and optional precondition result."""
        super().__init__(registered_code, context=context, translated_message=translated_message)
        self._terminal_precondition_verdict = precondition_verdict

    @property
    def terminal_precondition_verdict(self) -> PreconditionVerdict | None:
        """Return the terminal precondition result, if one was recorded."""
        return self._terminal_precondition_verdict

    @terminal_precondition_verdict.setter
    def terminal_precondition_verdict(self, verdict: PreconditionVerdict | None) -> None:
        """Attach a follow-up verdict while retaining this recorded failure."""
        self._terminal_precondition_verdict = verdict


def attach_cli_policy_verdict[ErrorT: Exception](error: ErrorT, *, verdict: PreconditionVerdict) -> ErrorT:
    """Attach one typed policy verdict while preserving the concrete error."""
    attribute = "terminal_precondition_verdict"
    setattr(error, attribute, verdict)
    return error


class CliOperationStillRunningError(CadrumoError):
    """Retain an admitted operation whose final effect is not yet known."""

    def __init__(self, *, operation_id: str, effect: str, check_command: str | None = None) -> None:
        """Record an admitted operation whose final effect is still unknown."""
        context: dict[str, object] = {"operation_id": operation_id, "effect": effect}
        if check_command is not None:
            context["check_command"] = check_command
        super().__init__(translated_message="errors.locked.locked_cli_operation_still_running", context=context)


__all__ = [
    "CliOperationStillRunningError",
    "CliOutboundPayloadBoundaryError",
    "CliRecordedOperationError",
    "CliRefusedBoundaryError",
    "CliUnexpectedBoundaryError",
    "attach_cli_policy_verdict",
    "log_cli_boundary_failure",
]
