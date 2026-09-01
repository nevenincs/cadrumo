"""The real network-transmitting :class:`~core.telemetry.TelemetrySink`.

:class:`~core.telemetry.HttpTelemetrySink` is the transport that was
deliberately deferred until every earlier piece (the consent gate, the
closed allowlisted :class:`~core.telemetry.TelemetryEventPayload`, and
:class:`~core.telemetry.LocalNoopTelemetrySink`) proved the pipeline
end-to-end without ever touching the network. This module adds the one sink
that actually POSTs a payload off the operator's host, and it is
**structurally inert by default**:
:func:`~core.telemetry.emit_telemetry_event` never constructs a sink on its own,
so an ``HttpTelemetrySink`` only ever exists (and therefore only ever sends)
when a call site both explicitly builds one AND already passed the four-way
consent gate
(:func:`~core.telemetry.telemetry_emit_permitted`).

Two additional invariants beyond the consent gate keep this sink safe:

1. **No configured endpoint means no send, unconditionally.** A sink built
   without :attr:`~core.config.Settings.cadrumo_telemetry_endpoint` set (the
   documented default -- ``None``, scaffolded but read by no other transport)
   is a no-op, mirroring
   :class:`~core.telemetry.LocalNoopTelemetrySink`'s inertness. This
   protects a deployment that flips ``cadrumo_telemetry_opt_in`` and a tier on
   without ever configuring where to send data.
2. **A transport failure never escapes.** Telemetry is best-effort diagnostic
   signal, never a load-bearing part of any command's outcome; a connection
   refusal, timeout, or non-2xx response is logged at debug level and
   swallowed. The payload itself -- already the allowlisted, non-sensitive
   :class:`~core.telemetry.TelemetryEventPayload` shape -- is never
   logged, so a failure cannot leak transmission content into local logs.

The HTTP transport reuses :mod:`httpx`, the project's single outbound HTTP
client dependency (the same library the
:class:`~llm._providers.gemini.GeminiAdapter` and
sibling LLM provider adapters use), rather than introducing a second HTTP
client dependency.

See Also:
    :class:`~core.telemetry.HttpTelemetrySink`
        Public facade export for this optional network sink.
    :func:`~core.telemetry.emit_telemetry_event`
        Gate-then-dispatch function that accepts a sink but never constructs
        this transport by default.
    :func:`~core.telemetry.telemetry_emit_permitted`
        Consent gate callers must pass before any real send is attempted.
    :class:`~core.telemetry.TelemetryEventPayload`
        Closed payload shape posted by this transport when configured.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..external_constants import UTF_8_ENCODING

if TYPE_CHECKING:
    from .schema import TelemetryEventPayload

__all__ = ["HttpTelemetrySink"]

_DEFAULT_TIMEOUT_S = 5.0


class HttpTelemetrySink:
    """Posts an allowlisted payload to a configured endpoint.

    Attributes:
        endpoint: The remote telemetry collector URL, or ``None``. When
            ``None`` (the default-off posture's natural value for
            ``settings.cadrumo_telemetry_endpoint``),
            :meth:`~core.telemetry.HttpTelemetrySink.send` is a pure no-op --
            the sink never dials out.
    """

    def __init__(self, endpoint: str | None, *, timeout_s: float = _DEFAULT_TIMEOUT_S) -> None:
        """Initialize the sink.

        Args:
            endpoint: The remote telemetry collector URL to POST to, or
                ``None`` to construct a permanently-inert sink. Callers should
                pass ``settings.cadrumo_telemetry_endpoint`` directly.
            timeout_s: Per-request HTTP timeout in seconds. Telemetry is
                best-effort and must never block a command for long; the
                default is deliberately short.
        """
        self._endpoint = endpoint
        self._timeout_s = timeout_s

    @property
    def endpoint(self) -> str | None:
        """The configured destination URL, or ``None`` when inert."""
        return self._endpoint

    def send(self, payload: TelemetryEventPayload) -> None:
        """Best-effort POST of ``payload`` to the configured endpoint.

        A no-op when :attr:`~core.telemetry.HttpTelemetrySink.endpoint` is
        ``None`` (no transport configured). Any transport-level failure
        (connection error, timeout, non-2xx response) is caught, logged at debug
        level with no payload content, and swallowed -- telemetry delivery
        failure must never surface to or affect the caller.

        Args:
            payload: The already-gated, already-allowlisted payload to
                transmit. Only
                :class:`~core.telemetry.TelemetryEventPayload`'s own JSON
                representation is sent; no other data is attached to the
                request.
        """
        if not self._endpoint:
            return
        # Imported lazily for cold start, not for a cycle: this package is
        # reached from ``core.config`` (for ``TelemetryTier``), which every CLI
        # surface imports, so a module-scope ``import httpx`` made ``aeat
        # --version`` pay ~0.7s for an HTTP client it never constructs -- this
        # transport is opt-in and ``emit_telemetry_event`` never builds it by
        # default. The cost lands only on a configured remote emission.
        import httpx

        try:
            response = httpx.post(
                self._endpoint,
                content=payload.model_dump_json().encode(UTF_8_ENCODING),
                headers={"content-type": "application/json"},
                timeout=self._timeout_s,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            # Imported lazily: ``core.logging.get_logger`` -> ``configure_logging``
            # -> ``core.config`` -> ``core.telemetry`` (for ``TelemetryTier``) would
            # otherwise cycle back into this package at module-import time.
            from ..logging import get_logger

            get_logger(__name__).debug("Remote telemetry transport failure; emission dropped.", exc_info=True)
            return
