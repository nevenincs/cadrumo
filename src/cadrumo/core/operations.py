"""Closed, frontend-neutral axes for supervised application operations."""

from __future__ import annotations

from enum import StrEnum


class OperationLifecycle(StrEnum):
    """Global position of an operation before, during, and after execution."""

    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_INTERACTION = "waiting_for_interaction"
    WAITING_FOR_EXTERNAL = "waiting_for_external"
    CANCELLATION_REQUESTED = "cancellation_requested"
    SETTLING = "settling"
    TERMINAL = "terminal"


class OperationTerminalCondition(StrEnum):
    """Reason an operation reached its settled terminal lifecycle."""

    SUCCEEDED = "succeeded"
    REFUSED = "refused"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    INTERRUPTED = "interrupted"


class OperationEffect(StrEnum):
    """Authoritative extent of committed effect, independent of terminal condition."""

    NONE = "none"
    UPDATED = "updated"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


EFFECTS_WITHOUT_PARTIAL_COMMIT: frozenset[OperationEffect] = frozenset(
    {
        OperationEffect.NONE,
        OperationEffect.UPDATED,
        OperationEffect.UNKNOWN,
    },
)
"""Effects declarable by an operation that either does nothing, fully applies,
or leaves an unknown extent, but never a partially-applied one.

:attr:`OperationEffect.PARTIAL` is excluded deliberately: an operation whose
sub-steps can fail independently and leave only some of them committed
declares ``PARTIAL`` explicitly in its own ``permitted_effects`` instead of
using this set. See
:mod:`cadrumo.application.live.filed_history_operation`, whose replay
operation returns :attr:`OperationEffect.PARTIAL` when some sub-operations
fail, for the contrasting case."""


class OperationDurability(StrEnum):
    """Persistence and recovery guarantee declared by an operation definition."""

    EPHEMERAL = "ephemeral"
    RECORDED = "recorded"
    RESUMABLE = "resumable"


class OperationCancellation(StrEnum):
    """Cancellation mechanism an operation can truthfully support."""

    UNSUPPORTED = "unsupported"
    COOPERATIVE = "cooperative"
    CONTAINED = "contained"


class OperationDeadline(StrEnum):
    """Aggregate deadline guarantee declared by an operation definition."""

    ABSENT = "absent"
    COOPERATIVE = "cooperative"
    ENFORCED = "enforced"


class OperationClosePolicy(StrEnum):
    """Frontend close behavior projected from operation policy."""

    DETACH_ALLOWED = "detach_allowed"
    REQUEST_CANCEL = "request_cancel"
    BLOCK_UNTIL_SETTLED = "block_until_settled"


class OperationEventKind(StrEnum):
    """Closed families of ordered, safe operation events."""

    PHASE = "phase"
    PROGRESS = "progress"
    LOG = "log"
    EFFECT = "effect"
    NOTICE = "notice"
    RECONCILIATION = "reconciliation"
    DIAGNOSTIC = "diagnostic"
    INTERACTION = "interaction"
    TERMINAL = "terminal"


class OperationInteractionKind(StrEnum):
    """Closed presentation families for typed operator interaction."""

    INPUT = "input"
    CHOICE = "choice"
    REVIEW = "review"
    APPLY = "apply"
    REJECT = "reject"


__all__ = [
    "OperationCancellation",
    "OperationClosePolicy",
    "OperationDeadline",
    "OperationDurability",
    "OperationEffect",
    "OperationEventKind",
    "OperationInteractionKind",
    "OperationLifecycle",
    "OperationTerminalCondition",
]
