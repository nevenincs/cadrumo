"""Which worker requests this process is serving, so background warm-up work defers to them.

The profile grounding warm-up and every worker request share one interpreter.
A request in flight, or one that ended moments ago, holds the warm-up back.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from time import monotonic

# How long worker requests must stay quiet before the grounding warm-up
# decodes its next revision. A frontend's burst of requests after sign-in has
# short gaps between round trips; the warm-up must not fill them.
_GROUNDING_WARMUP_QUIET_SECONDS = 0.75


class _WorkerRequestActivity:
    """The worker requests this process is serving, and when the last one ended.

    Process-wide because the contention it avoids is: the grounding warm-up
    and every request share one interpreter. Written only on the service
    loop; the warm-up thread only reads it.
    """

    def __init__(self) -> None:
        self.serving = 0
        self.quiet_since = monotonic()


_REQUEST_ACTIVITY = _WorkerRequestActivity()


@contextmanager
def worker_request_served() -> Generator[None]:
    """Mark one worker request as being served, so the grounding warm-up defers to it.

    The warm-up is a registry-wide decode that holds the interpreter. Run
    beside a person's first operations it slowed each of them several
    fold, though none of them waits for the index it builds.
    """
    _REQUEST_ACTIVITY.serving += 1
    try:
        yield
    finally:
        _REQUEST_ACTIVITY.serving -= 1
        _REQUEST_ACTIVITY.quiet_since = monotonic()


def grounding_deferred() -> bool:
    """Answer whether a request is being served or requests have not yet been quiet long enough."""
    return (
        _REQUEST_ACTIVITY.serving > 0 or monotonic() - _REQUEST_ACTIVITY.quiet_since < _GROUNDING_WARMUP_QUIET_SECONDS
    )


def restart_quiet_window() -> None:
    """Start the quiet window afresh, so the request that usually follows a sign-in reply comes first."""
    _REQUEST_ACTIVITY.quiet_since = monotonic()
