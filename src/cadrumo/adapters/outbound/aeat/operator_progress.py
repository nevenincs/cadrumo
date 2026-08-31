"""Lightweight operator-progress channel shared by AEAT operations and frontends.

Keeping this ContextVar outside the concrete auth implementations lets CLI
metadata and local configuration commands start without browser-auth settings.
The CLI installs a stderr sink for headless operation; a full-screen frontend
may replace it within its worker context so progress stays inside the TUI.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar

from ....core.operator_progress import OperatorProgress

_OPERATOR_PROGRESS_SINK: ContextVar[Callable[[OperatorProgress], None] | None] = ContextVar(
    "_aeat_auth_operator_progress_sink",
    default=None,
)
"""Active operator progress sink for the current context, or ``None`` when unset."""


@contextmanager
def operator_progress_sink(sink: Callable[[OperatorProgress], None]) -> Generator[None]:
    """Route operator progress to ``sink`` within this context."""
    token = _OPERATOR_PROGRESS_SINK.set(sink)
    try:
        yield
    finally:
        _OPERATOR_PROGRESS_SINK.reset(token)


def emit_operator_progress(progress: OperatorProgress) -> None:
    """Send an already-redacted operator progress update when a sink is armed."""
    sink = _OPERATOR_PROGRESS_SINK.get()
    if sink is not None:
        sink(progress)


__all__ = ["emit_operator_progress", "operator_progress_sink"]
