"""Finite monotonic deadline budgets for frontend exchanges with the local runtime.

A deadline is an absolute :func:`time.monotonic` instant. Every budget is
finite: a NaN never compares as expired and an infinite budget would wait
without bound, so both fail closed as an exceeded deadline.
"""

from __future__ import annotations

import math
import time

from .contracts import RuntimeRefusalCode, RuntimeRefusalError

#: Longest a single frontend exchange with the runtime may be granted by its caller.
RUNTIME_EXCHANGE_MAX_TIMEOUT_SECONDS = 120.0


def require_finite_budget(timeout: float) -> float:
    """Return ``timeout`` unchanged, refusing a non-finite or empty budget as an exceeded deadline."""
    if not math.isfinite(timeout) or timeout <= 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
    return timeout


def deadline_after(timeout: float) -> float:
    """Return the deadline ``timeout`` seconds from now, refusing a non-finite or empty budget."""
    return time.monotonic() + require_finite_budget(timeout)


def bounded_deadline_after(
    timeout: float,
    *,
    subject: str,
    maximum_seconds: float = RUNTIME_EXCHANGE_MAX_TIMEOUT_SECONDS,
) -> float:
    """Validate a caller-chosen budget and return its deadline.

    An out-of-range budget is a caller error rather than a runtime refusal, so
    it raises :class:`ValueError` naming ``subject``.
    """
    if not math.isfinite(timeout) or not 0 < timeout <= maximum_seconds:
        raise ValueError(f"{subject} timeout must be finite and at most {maximum_seconds:g} seconds")
    return time.monotonic() + timeout


def remaining_budget(deadline: float) -> float:
    """Return the positive seconds left before ``deadline`` or refuse it as exceeded."""
    remaining = deadline - time.monotonic()
    if not math.isfinite(remaining) or remaining <= 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
    return remaining


def exchange_timeout(deadline: float | None = None) -> float:
    """Return how long one frontend exchange may wait for the runtime's reply.

    The runtime is legitimately slow while another caller holds a profile
    guard, a worker starts or a supervised KDF child attests on a loaded host.
    A client that stops waiting earlier closes its connection on a reply that
    was coming, and for a mutation leaves the outcome unknown. So an exchange
    may use its command's remaining ``deadline``, or the runtime's documented
    single-exchange maximum when it has none, but never more than that maximum:
    a runtime that has really stalled still fails within a bounded time.
    """
    if deadline is None:
        return RUNTIME_EXCHANGE_MAX_TIMEOUT_SECONDS
    return min(remaining_budget(deadline), RUNTIME_EXCHANGE_MAX_TIMEOUT_SECONDS)


def exchange_deadline(deadline: float | None = None) -> float:
    """Return :func:`exchange_timeout` as an absolute deadline for one exchange of a longer command."""
    return time.monotonic() + exchange_timeout(deadline)


__all__ = [
    "RUNTIME_EXCHANGE_MAX_TIMEOUT_SECONDS",
    "bounded_deadline_after",
    "deadline_after",
    "exchange_deadline",
    "exchange_timeout",
    "remaining_budget",
    "require_finite_budget",
]
