"""Context-local capture scopes for golden-output and redaction tests."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from ..capture import CAPTURE_SINK


@contextmanager
def capture_envelopes() -> Generator[list[dict[str, object]]]:
    """Arm envelope capture for the current context, yielding the sink list.

    Nesting-aware: when a sink is already active (e.g. armed by an outer
    capture scope), this reuses it rather than shadowing it, so a
    re-entered command's emitted envelope lands in the outermost armed
    sink. The reused case does not reset the outer sink on exit.

    Yields:
        The list that :func:`record_emitted_envelope` appends to; each
        entry is a shallow copy of an emitted envelope document.
    """
    existing = CAPTURE_SINK.get()
    if existing is not None:
        yield existing
        return
    sink: list[dict[str, object]] = []
    token = CAPTURE_SINK.set(sink)
    try:
        yield sink
    finally:
        CAPTURE_SINK.reset(token)
