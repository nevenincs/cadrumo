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


LIFECYCLES_BEFORE_ANY_CANCELLATION_REQUEST: frozenset[OperationLifecycle] = frozenset(
    {
        OperationLifecycle.CREATED,
        OperationLifecycle.QUEUED,
        OperationLifecycle.RUNNING,
        OperationLifecycle.WAITING_FOR_INTERACTION,
        OperationLifecycle.WAITING_FOR_EXTERNAL,
    },
)
"""Lifecycle stages an operation can only be in before any cancellation
request has been made.

Requesting cancellation is an irreversible, immediate lifecycle transition:
the moment a cancellation is requested, the operation moves to
``CANCELLATION_REQUESTED`` and can never return to one of these five stages.
So a recorded cancellation-request fact is inconsistent with the lifecycle
still sitting in this set -- if a request exists, the lifecycle must already
be ``CANCELLATION_REQUESTED``, ``SETTLING``, or ``TERMINAL``.

The complement is NOT "the states cancellation causes" -- ``SETTLING`` and
``TERMINAL`` are reached by every operation, cancelled or not. It is only the
states a recorded cancellation-request fact remains CONSISTENT with, because
the forward-only transition already ruled out coming back here."""


LIFECYCLES_BEFORE_EXECUTOR_ENTRY: frozenset[OperationLifecycle] = frozenset(
    {
        OperationLifecycle.CREATED,
        OperationLifecycle.QUEUED,
    },
)
"""Lifecycle stages an operation occupies before its executor can have entered.

An operation in one of these two stages has not been handed to an executor, so
it cannot have recorded an ``executor_entered_at`` instant.

This set is NOT interchangeable with ``executor_entered_at is None``, and the
direction matters. The persisted-snapshot validator enforces one implication
only -- a recorded entry instant means the lifecycle has already left this set
-- so this set is strictly NARROWER than "no entry recorded". The converse
does not hold: an operation can sit outside these stages with no entry instant,
which is exactly the pre-entry ``TERMINAL`` case the journal validates
separately. Swapping one condition for the other therefore changes behaviour,
and a caller must pick the one it means: this set asks "has it been handed to
an executor yet", the field asks "did an executor ever enter"."""


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
