"""Bound registered CLI exchanges, settlement polling and settled-result reads."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

from ...application.runtime.deadline_budget import bounded_deadline_after

#: Longest a command waits for an admitted operation to settle; each exchange keeps its own timeout.
MAX_OPERATION_SETTLEMENT_SECONDS = 3600.0


OPERATION_POLL_INITIAL_SECONDS = 0.02


OPERATION_POLL_MAX_SECONDS = 0.5


#: Below this much time left on the shared deadline, a settled operation's result read gets its own.
MIN_SETTLED_OPERATION_READ_SECONDS = 0.25


@dataclass(frozen=True, slots=True)
class RegisteredOperationDeadline:
    """One settlement deadline with independent bounded exchanges and settled-result reads."""

    deadline: float
    timeout: float
    settlement_timeout: float | None

    def call_deadline(self) -> float:
        """Bound an exchange by both the settlement and per-call timeout."""
        return min(self.deadline, time.monotonic() + self.timeout)

    def settled_read_deadline(self) -> float:
        """Read an already settled outcome within its original minimum result-read budget."""
        if self.settlement_timeout is not None:
            return max(self.deadline, time.monotonic() + self.timeout)
        bounded = self.call_deadline()
        return (
            bounded
            if bounded - time.monotonic() >= MIN_SETTLED_OPERATION_READ_SECONDS
            else time.monotonic() + self.timeout
        )


def operation_settlement_deadline(timeout: float, settlement_timeout: float | None) -> float:
    """Validate the admitted settlement wait within its original one-hour bound."""
    if settlement_timeout is None:
        return bounded_deadline_after(timeout, subject="modelo operation")
    if not math.isfinite(settlement_timeout) or not timeout <= settlement_timeout <= MAX_OPERATION_SETTLEMENT_SECONDS:
        raise ValueError("operation settlement wait must be finite, at least the timeout and at most one hour")
    return time.monotonic() + settlement_timeout
