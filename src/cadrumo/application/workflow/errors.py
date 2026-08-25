"""Exception hierarchy for :mod:`application.workflow`.

All workflow errors inherit from :class:`core.errors.CadrumoError` per
the project-wide error-hierarchy rule. The engine's default path never
raises :class:`WorkflowAbortedError`: aborts are first-class outcomes
encoded in the returned
:class:`application.workflow.WorkflowResult`. Callers who want
exception-on-abort behaviour opt in by inspecting the result themselves.
"""

from __future__ import annotations

from ...core.errors import CadrumoError, CoreValidationError
from .abort import WorkflowAbortReason


class WorkflowError(CadrumoError):
    """Base exception for all :mod:`application.workflow` failures."""


class WorkflowComponentError(WorkflowError):
    """Raised when a cross-module component raises an unexpected exception.

    The engine catches every exception raised by an injected Protocol
    component, wraps it in a :class:`WorkflowComponentError`, records the
    context on the surrounding :class:`application.workflow.WorkflowStep`, and
    lets the workflow abort with
    :attr:`application.workflow.WorkflowAbortReason.UNHANDLED_EXCEPTION`.
    """


class WorkflowAbortedError(WorkflowError):
    """Raised only when a caller explicitly opts in to exception-on-abort.

    The default driver path returns a populated
    :class:`application.workflow.WorkflowResult` whose ``aborted_reason`` is set.
    This exception is reserved for callers that prefer raising over
    inspecting (e.g. a future cron runner that wants a non-zero exit).
    """


class BootstrapAlreadyCompleteError(WorkflowError):
    """Raised when `aeat config profile create NAME` is re-invoked after a profile already exists.

    The bootstrap wizard is a one-shot first-run flow. A second invocation
    must refuse with this typed error so the operator is redirected to the
    canonical second-or-later-profile creation path (the ``aeat config
    profile create NAME`` verb) rather than silently overwriting the
    existing default profile.
    """


class ProfileNameCollisionError(WorkflowError):
    """Raised when an operator-typed profile NAME is already in use.

    Fired by the lifecycle service's `create` and `rename` paths
    when the requested NAME already names a live or tombstoned
    profile. The error payload carries the colliding name so the
    CLI can render it back to the operator without a second
    repository round trip.
    """


class ProfileLockedError(WorkflowError):
    """Raised when a profile-scoped operation requires an unlocked profile session.

    The profile-bucket lifecycle mandates explicit unlock-on-switch
    semantics: a verb that needs the active profile's plaintext payload
    must run inside an unlocked ``BucketSession``. Verbs that touch
    encrypted payloads on a locked-default state refuse with this typed
    error so the operator runs the unlock flow explicitly.
    """


class UnhandledWorkflowError(WorkflowComponentError):
    """Raised when a workflow stage propagates an exception with no typed handler.

    Wraps every bare ``except Exception`` catch inside
    ``cadrumo.application.workflow._engine.WorkflowEngine._record_unhandled``
    so the unhandled path produces a structured :class:`ErrorEnvelope` with
    a stable ``INTERNAL_WORKFLOW_UNHANDLED`` code rather than an opaque
    ``UNHANDLED_EXCEPTION`` abort reason alone.
    """


class ProfileLabelAmbiguousError(WorkflowError):
    """Raised when a profile label resolves to more than one live bucket.

    The name-uniqueness guard should prevent this among live profiles.
    When it occurs, the operator must disambiguate by UUID rather than
    by label. Carries the label and the ambiguous match count so the
    CLI can render a diagnostic without a second repository round trip.
    """


class WorkflowInputMismatchError(CoreValidationError):
    """Raised when a workflow input request does not match the expected contract.

    Used both by the engine's ``run_for_period`` gate (malformed
    ``resumed_from`` run id shape) and by
    :class:`application.modelo._workflow_gate._RevisionInputsProvider`
    (modelo code or period mismatch against the baked revision).  Any
    deviation signals a programming error or a stale work-unit reference
    and must be rejected before inputs reach the engine.
    """


class WorkflowAbortSignalError(WorkflowError):  # internal control-flow signal, not a public error type
    """Internal control-flow signal raised by stage methods to bail out.

    Named ``WorkflowAbortSignalError`` because it subclasses ``WorkflowError``
    and the project-wide naming convention requires the ``Error`` suffix on all
    exception classes. The engine treats it as an internal control-flow vehicle
    — it never propagates outside :class:`application.workflow.WorkflowEngine`.
    ``WorkflowEngine._drive`` always catches it and materialises the
    :class:`application.workflow.WorkflowResult`. Subclasses
    :class:`WorkflowError` so the project-wide error-hierarchy rule
    still holds and the registry can bind a stable
    ``INTERNAL_WORKFLOW_ABORT_SIGNAL`` code for telemetry.

    Attributes:
        reason: The :class:`WorkflowAbortReason` that classifies the bailout.
    """

    def __init__(
        self,
        *,
        reason: WorkflowAbortReason,
    ) -> None:
        """Construct with the closed abort reason.

        Args:
            reason: The :class:`WorkflowAbortReason` that classifies the
                bailout.
        """
        super().__init__(reason.value)
        self.reason = reason
