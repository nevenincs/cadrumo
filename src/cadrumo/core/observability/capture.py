"""In-memory capture sink for emitted CLI success envelopes.

The deterministic-output substrate captures the verbatim emitted
:class:`~core.json_contract.SchemaEnvelope` document so a recorded
run can be replayed and asserted byte-identical after masking. The sink
is a context variable holding a list; it is unset (``None``) in production,
so :func:`record_emitted_envelope` is a no-op unless a
:func:`capture_envelopes` scope has armed it — the emit path pays only a
single ``ContextVar.get`` when capture is off.

This module deliberately has NO dependency on
:mod:`core.json_contract`, so the emit path
(:func:`core.json_contract.emit_json_success`) can feed it through a
cheap lazy import without an import cycle. Typed re-validation of a
captured document against the schema registry lives in
:mod:`core.observability.golden`.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar

_CAPTURE_SINK: ContextVar[list[dict[str, object]] | None] = ContextVar(
    "_aeat_envelope_capture_sink",
    default=None,
)
"""Active capture list for the current context, or ``None`` when capture is off."""


@contextmanager
def capture_envelopes() -> Iterator[list[dict[str, object]]]:
    """Arm envelope capture for the current context, yielding the sink list.

    Nesting-aware: when a sink is already active (e.g. armed by an outer
    replay scope), this reuses it rather than shadowing it, so a
    re-entered command's emitted envelope lands in the outermost armed
    sink. The reused case does not reset the outer sink on exit.

    Yields:
        The list that :func:`record_emitted_envelope` appends to; each
        entry is a shallow copy of an emitted envelope document.
    """
    existing = _CAPTURE_SINK.get()
    if existing is not None:
        yield existing
        return
    sink: list[dict[str, object]] = []
    token = _CAPTURE_SINK.set(sink)
    try:
        yield sink
    finally:
        _CAPTURE_SINK.reset(token)


def record_emitted_envelope(envelope: Mapping[str, object]) -> None:
    """Append ``envelope`` to the active capture sink; a no-op when unarmed.

    Args:
        envelope: The already-redacted, emitted envelope document.
    """
    sink = _CAPTURE_SINK.get()
    if sink is not None:
        sink.append(dict(envelope))


def capture_is_armed() -> bool:
    """Return whether an envelope-capture scope is active for the current context."""
    return _CAPTURE_SINK.get() is not None


__all__ = [
    "capture_envelopes",
    "capture_is_armed",
    "record_emitted_envelope",
]
