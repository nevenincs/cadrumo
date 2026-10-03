"""Layer-neutral operator-progress schema and the context-scoped channel that carries it.

The channel lives in core so that whichever layer owns the operator's view can
arm it: the operation supervisor forwards each update's ``notice_code`` into
the operation's public notice events, and the CLI routes in-process updates to
stderr. An emitter running with no sink armed only records to its own log.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Annotated

from pydantic import BaseModel, Field

from .models import STRICT_FROZEN_CONFIG

OPERATOR_DISPLAY_CODE_PATTERN = r"^[A-Z0-9]{3,8}$"
"""A short code the operator compares across two screens; never free text."""

type OperatorDisplayCode = Annotated[str, Field(pattern=OPERATOR_DISPLAY_CODE_PATTERN)]
type OperatorProgressSink = Callable[[OperatorProgress], Awaitable[None]]


class OperatorProgress(BaseModel):
    """Actionable progress text plus a stable notice code and optional live countdown.

    ``notice_code`` and the optional ``display_code`` are the only parts that
    cross a frontend contract, where a frontend renders its own localized text
    for them; ``message`` is free text for the runtime log and in-process
    operator output.
    """

    model_config = STRICT_FROZEN_CONFIG

    notice_code: str = Field(min_length=3, max_length=128, pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
    display_code: OperatorDisplayCode | None = None
    message: str = Field(min_length=1)
    timeout_seconds: int | None = Field(default=None, gt=0)

    def render(self, *, remaining_seconds: int | None = None) -> str:
        """Render the update for a frontend that cannot animate a timer."""
        seconds = self.timeout_seconds if remaining_seconds is None else remaining_seconds
        if seconds is None:
            return self.message
        minutes, remainder = divmod(max(0, seconds), 60)
        return f"{self.message} Time remaining {minutes}:{remainder:02d}."


_OPERATOR_PROGRESS_SINK: ContextVar[OperatorProgressSink | None] = ContextVar(
    "_operator_progress_sink",
    default=None,
)
"""Active operator progress sink for the current context, or ``None`` when unset."""


@contextmanager
def operator_progress_sink(sink: OperatorProgressSink) -> Generator[None]:
    """Route operator progress to ``sink`` within this context."""
    token = _OPERATOR_PROGRESS_SINK.set(sink)
    try:
        yield
    finally:
        _OPERATOR_PROGRESS_SINK.reset(token)


async def emit_operator_progress(progress: OperatorProgress) -> None:
    """Send an already-redacted operator progress update when a sink is armed."""
    sink = _OPERATOR_PROGRESS_SINK.get()
    if sink is not None:
        await sink(progress)


__all__ = [
    "OPERATOR_DISPLAY_CODE_PATTERN",
    "OperatorDisplayCode",
    "OperatorProgress",
    "OperatorProgressSink",
    "emit_operator_progress",
    "operator_progress_sink",
]
