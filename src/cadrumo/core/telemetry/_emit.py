"""The single remote-telemetry emit call site.

:func:`~core.telemetry.emit_telemetry_event` is the ONLY function a producer
calls to emit a remote-eligible telemetry event. It composes the consent gate
(:func:`~core.telemetry.telemetry_emit_permitted`) with a pluggable
:class:`~core.telemetry.TelemetrySink`; when the gate refuses, emission is a
pure no-op -- nothing is constructed, nothing is written, nothing is sent.

:class:`~core.telemetry.LocalNoopTelemetrySink`, deliberately does
nothing observable: it exists so callers and tests can exercise the full
gate-then-emit sequence without a real transport, proving the payload a
network sink would send is already the allowlisted, scrubbed shape.

See Also:
    :func:`~core.telemetry.build_telemetry_payload`
        Constructs the allowlisted payload consumed here.
    :class:`~core.telemetry.HttpTelemetrySink`
        Optional network transport that implements the same sink protocol.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from ._consent import telemetry_emit_permitted

if TYPE_CHECKING:
    from ..config import Settings
    from .schema import TelemetryEventPayload

__all__ = ["LocalNoopTelemetrySink", "TelemetrySink", "emit_telemetry_event"]


class TelemetrySink(Protocol):
    """A destination for an allowlisted :class:`~core.telemetry.TelemetryEventPayload`.

    Implementations of this protocol are the only place a telemetry payload
    can leave this function's caller. :class:`LocalNoopTelemetrySink`
    transmits nothing over the network; :class:`~core.telemetry.HttpTelemetrySink`
    implements the same protocol for a call site that opts into real
    transmission.
    """

    def send(self, payload: TelemetryEventPayload) -> None:
        """Deliver ``payload`` to this sink's destination."""
        ...


class LocalNoopTelemetrySink:
    """A sink that intentionally does nothing.

    Used as the default sink: the safe default is to accept the
    already-gated, already-allowlisted payload and discard it. This lets
    :func:`~core.telemetry.emit_telemetry_event` be called end-to-end (gate,
    schema validation, sink dispatch) without any observable network or disk
    side effect.
    """

    def send(self, payload: TelemetryEventPayload) -> None:
        """Discard ``payload``. Deliberately a no-op."""
        return None


def emit_telemetry_event(
    payload: TelemetryEventPayload,
    *,
    settings: Settings,
    acknowledged: bool,
    sink: TelemetrySink | None = None,
) -> bool:
    """Emit ``payload`` to ``sink`` if and only if the consent gate permits it.

    Args:
        payload: The already-constructed, already-allowlisted
            :class:`~core.telemetry.TelemetryEventPayload` (build it with
            :func:`~core.telemetry.build_telemetry_payload` so its
            counters/timings are schema-validated).
        settings: Resolved deployment settings.
        acknowledged: Whether the operator acknowledged remote telemetry for
            this specific invocation. Never sticky; re-affirm at every call
            site.
        sink: The destination to hand the payload to when permitted. Defaults
            to :class:`~core.telemetry.LocalNoopTelemetrySink` (no caller
            opts into :class:`~core.telemetry.HttpTelemetrySink` here).

    Returns:
        ``True`` when the event was handed to the sink; ``False`` when the
        consent gate refused and emission was a no-op.
    """
    if not telemetry_emit_permitted(settings, acknowledged=acknowledged):
        return False
    resolved_sink = sink if sink is not None else LocalNoopTelemetrySink()
    resolved_sink.send(payload)
    return True
