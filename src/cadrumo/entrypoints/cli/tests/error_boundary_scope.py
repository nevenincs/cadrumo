"""Expose original callback failures to CLI behavior assertions."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import Token

from ..errors import _BOUNDARY_SUSPENDED


@contextmanager
def suspend_error_boundary() -> Generator[None]:
    """Temporarily force :func:`command_error_boundary` to re-raise originals.

    Tests that need to assert on the raised exception type rather than
    the rendered stderr payload should wrap their invocation in this
    context manager. The override is scoped to the active context via
    :class:`~contextvars.ContextVar`, so concurrent callbacks are
    unaffected.

    Yields:
        ``None``. The context's only purpose is the side effect on the internal
        flag.
    """
    token: Token[bool] = _BOUNDARY_SUSPENDED.set(True)
    try:
        yield
    finally:
        _BOUNDARY_SUSPENDED.reset(token)
