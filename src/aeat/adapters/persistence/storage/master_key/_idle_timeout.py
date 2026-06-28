"""Idle-timeout evaluation for `BucketSession`.

Every CLI invocation runs `evaluate_idle(session, now, configured_minutes)`
before granting access to the session. The configured value lives in
the bucket manifest (`ManifestKdfParams` is plaintext; `idle_lock_minutes` is
read from the durable config profile. The default is
15 minutes.

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
        configured_minutes: Operator-configured idle-lock window in
            minutes (read from the bucket manifest). Defaults to
            `DEFAULT_IDLE_LOCK_MINUTES` (15).
            Strict positive integer; non-positive values raise.

    Returns:
        An :class:`IdleEvaluation` record carrying `expired` and the
        floor-truncated `remaining_seconds` until the deadline (zero
        when expired).

    Raises:
        StorageValidationError: When ``configured_minutes`` is not a strict positive integer.
    """
    if configured_minutes <= 0:
        raise _storage_validation_error("configured_minutes must be a strict positive integer")

    if session.sealed:
        return IdleEvaluation(expired=True, remaining_seconds=0)

    deadline = session.idle_deadline
    if now >= deadline:
        return IdleEvaluation(expired=True, remaining_seconds=0)

    delta: timedelta = deadline - now
    return IdleEvaluation(expired=False, remaining_seconds=int(delta.total_seconds()))


__all__ = ["DEFAULT_IDLE_LOCK_MINUTES", "IdleEvaluation", "evaluate_idle"]
