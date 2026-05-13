"""Exception hierarchy for :mod:`aeat.application.workflow`.

All workflow errors inherit from :class:`aeat.core.errors.AeatError` per
the project-wide error-hierarchy rule. The engine's default path never
raises :class:`WorkflowAbortedError`: aborts are first-class outcomes
encoded in the returned
:class:`aeat.application.workflow.WorkflowResult`. Callers who want
exception-on-abort behaviour opt in by inspecting the result themselves.
"""

from __future__ import annotations

from ...core.errors import AeatError
from ._models import WorkflowAbortReason


class WorkflowError(AeatError):
    """Base exception for all :mod:`aeat.application.workflow` failures."""


class WorkflowComponentError(WorkflowError):
    """Raised when a cross-module component raises an unexpected exception.

    The engine catches every exception raised by an injected Protocol
    component, wraps it in a :class:`WorkflowComponentError`, records the
    context on the surrounding :class:`aeat.application.workflow.WorkflowStep`, and
    lets the workflow abort with
    :attr:`aeat.application.workflow.WorkflowAbortReason.UNHANDLED_EXCEPTION`.
    """


class WorkflowAbortedError(WorkflowError):
    """Raised only when a caller explicitly opts in to exception-on-abort.

    The default driver path returns a populated
    :class:`aeat.application.workflow.WorkflowResult` whose ``aborted_reason`` is set.
    This exception is reserved for callers that prefer raising over
    inspecting (e.g. a future cron runner that wants a non-zero exit).
    """


class WorkflowAbortSignal(WorkflowError):
    """Internal control-flow signal raised by stage methods to bail out.

    Named ``WorkflowAbortSignal`` deliberately (rather than
    ``WorkflowAbortSignalError``) because the engine treats it as an
    internal control-flow vehicle, not as a public error type — it
    never propagates outside :class:`aeat.application.workflow.WorkflowEngine`.
    :meth:`WorkflowEngine._drive` always catches it and materialises the
    :class:`aeat.application.workflow.WorkflowResult`. Subclasses
    :class:`WorkflowError` so the project-wide error-hierarchy rule
    still holds and the registry can bind a stable
    ``INTERNAL_WORKFLOW_ABORT_SIGNAL`` code for telemetry.

    Attributes:
        reason: The :class:`WorkflowAbortReason` that classifies the bailout.
        summary: Human-readable :class:`str` summary surfaced on
            the resulting :class:`WorkflowResult`.
    """

    def __init__(
        self,
        *,
        reason: WorkflowAbortReason,
        summary: str,
    ) -> None:
        super().__init__(reason.value)
        self.reason = reason
        self.summary = summary
