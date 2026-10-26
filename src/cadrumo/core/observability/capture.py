"""In-memory capture sink for emitted CLI success envelopes.

The emit path appends an envelope to an explicitly armed context-local sink.
An unarmed sink makes :func:`record_emitted_envelope` a no-op.

This module deliberately has NO dependency on
:mod:`core.json_contract`, so the emit path
(:func:`core.json_contract.emit_json_success`) can feed it through a
cheap lazy import without an import cycle. Typed re-validation of a
captured document against the schema registry lives in
:mod:`cadrumo.tests.golden_comparison`.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextvars import ContextVar

CAPTURE_SINK: ContextVar[list[dict[str, object]] | None] = ContextVar(
    "_aeat_envelope_capture_sink",
    default=None,
)
"""Active capture list for the current context, or ``None`` when capture is off."""


def record_emitted_envelope(envelope: Mapping[str, object]) -> None:
    """Append ``envelope`` to the active capture sink; a no-op when unarmed.

    Args:
        envelope: The already-redacted, emitted envelope document.
    """
    sink = CAPTURE_SINK.get()
    if sink is not None:
        sink.append(dict(envelope))


__all__ = [
    "record_emitted_envelope",
]
