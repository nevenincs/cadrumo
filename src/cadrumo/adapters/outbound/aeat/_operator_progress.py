"""Lightweight operator-progress channel shared by AEAT operations and frontends.

Keeping this ContextVar outside the heavy auth facade lets CLI metadata and
local configuration commands start without importing browser-auth settings.
The CLI installs a stderr sink for headless operation; a full-screen frontend
may replace it within its worker context so progress stays inside the TUI.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OperatorProgress:
    """Actionable progress text plus an optional live countdown duration."""

    message: str
    timeout_seconds: int | None = None

    def render(self, *, remaining_seconds: int | None = None) -> str:
        """Render the update for a frontend that cannot animate a timer."""
        seconds = self.timeout_seconds if remaining_seconds is None else remaining_seconds
        if seconds is None:
            return self.message
        minutes, remainder = divmod(max(0, seconds), 60)
        return f"{self.message} Time remaining {minutes}:{remainder:02d}."


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


__all__ = ["OperatorProgress", "emit_operator_progress", "operator_progress_sink"]
