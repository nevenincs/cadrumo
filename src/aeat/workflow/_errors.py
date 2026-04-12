"""Exception hierarchy for :mod:`aeat.workflow`.

All workflow errors inherit from :class:`aeat.errors.AeatError` per the
project-wide error-hierarchy rule. The engine's *default* path never
raises :class:`WorkflowAbortedError`: aborts are first-class outcomes
encoded in the returned :class:`aeat.workflow.WorkflowResult`. Callers
who want exception-on-abort behaviour opt in by inspecting the result
themselves.
"""

from __future__ import annotations

from aeat.errors import AeatError


class WorkflowError(AeatError):
    """Base exception for all :mod:`aeat.workflow` failures."""


class WorkflowComponentError(WorkflowError):
    """Raised when a cross-module component raises an unexpected exception.

    The engine catches every exception raised by an injected Protocol
    component, wraps it in a :class:`WorkflowComponentError`, records the
    context on the surrounding :class:`aeat.workflow.WorkflowStep`, and
    lets the workflow abort with
    :attr:`aeat.workflow.WorkflowAbortReason.UNHANDLED_EXCEPTION`.
    """


class WorkflowAbortedError(WorkflowError):
    """Raised only when a caller explicitly opts in to exception-on-abort.

    The default driver path returns a populated
    :class:`aeat.workflow.WorkflowResult` whose ``aborted_reason`` is set.
    This exception is reserved for callers that prefer raising over
    inspecting (e.g. a future cron runner that wants a non-zero exit).
    """
