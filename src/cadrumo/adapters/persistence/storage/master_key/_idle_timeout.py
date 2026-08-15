"""Idle-timeout evaluation for `BucketSession`.

Every CLI invocation runs `evaluate_idle(session, now)` before granting access
to the session. The window it evaluates was fixed when the session was opened,
from `cadrumo_bucket_default_idle_lock_minutes`; the default is 15 minutes.
There is no per-bucket override to read: the plaintext bucket manifest that
once declared one is retired, and nothing replaced it.

The evaluator is a pure function over the session's idle deadline and
the supplied `now`; it never mutates the session. Mutation happens
through `session.touch(now)` which the caller invokes on a successful
authentication so the deadline rolls forward by the configured window.

Returning a typed `IdleEvaluation` record (rather than a bare boolean)
lets the CLI render an actionable "remaining N seconds" hint without
re-deriving the math at the verb layer.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ..errors import (
    storage_validation_error as _storage_validation_error,
)
from ._bucket_session import BucketSession

DEFAULT_IDLE_LOCK_MINUTES = 15


class IdleEvaluation(BaseModel):
    """Typed outcome of an idle-window evaluation."""

    model_config = _STRICT_FROZEN

    expired: bool
    remaining_seconds: int = Field(ge=0)


def evaluate_idle(
    *,
    session: BucketSession,
    now: datetime,
    configured_minutes: int = DEFAULT_IDLE_LOCK_MINUTES,
) -> IdleEvaluation:
    """Evaluate the session's idle window without mutating it.

    Args:
        session: The session whose idle deadline to evaluate.
        now: UTC timestamp at which the evaluation runs.
        configured_minutes: Idle-lock window in minutes, defaulting to
            `DEFAULT_IDLE_LOCK_MINUTES` (15). Validated as a strict positive
            integer and otherwise unused: the deadlines this function compares
            were computed when the session opened, so the value bounds nothing
            here. The live caller passes none.

    Returns:
        An :class:`IdleEvaluation` record carrying `expired` and the
        floor-truncated `remaining_seconds` until the earlier of the idle
        deadline and the absolute session cap (zero when either has
        elapsed).

    Raises:
        StorageValidationError: When ``configured_minutes`` is not a strict positive integer.
    """
    if configured_minutes <= 0:
        raise _storage_validation_error("configured_minutes must be a strict positive integer")

    if session.sealed:
        return IdleEvaluation(expired=True, remaining_seconds=0)

    # Enforce both the sliding idle window and the immutable absolute cap: the
    # session is expired once the earlier of the two deadlines is reached.
    deadline = min(session.idle_deadline, session.absolute_deadline)
    if now >= deadline:
        return IdleEvaluation(expired=True, remaining_seconds=0)

    delta: timedelta = deadline - now
    return IdleEvaluation(expired=False, remaining_seconds=int(delta.total_seconds()))


__all__ = ["DEFAULT_IDLE_LOCK_MINUTES", "IdleEvaluation", "evaluate_idle"]
