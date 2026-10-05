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


__all__ = [
    "RUNTIME_EXCHANGE_MAX_TIMEOUT_SECONDS",
    "bounded_deadline_after",
    "deadline_after",
    "remaining_budget",
    "require_finite_budget",
]
