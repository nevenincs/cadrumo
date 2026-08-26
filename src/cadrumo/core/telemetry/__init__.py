"""Default-off, consent-gated remote telemetry.

Every existing telemetry primitive in this codebase is local-only by
construction: encrypted secure storage or a local JSONL file, never a network
call. This package is the one deliberate, narrow exception -- a REMOTE
telemetry tier an operator may opt into to help improve the project.

The consent gate mirrors
the retired evidence cloud-read gate's shape
exactly (gestor-mode absolute bar -> deployment opt-in -> tier -> per-
invocation acknowledgement, all ANDed, never sticky). The payload contract is
a closed, code-authored allowlist
(:class:`~core.telemetry.TelemetryEventPayload`): there is no ``extra`` field,
no free-text field wide enough to carry operator content, and no metric key can
be emitted remotely unless it is explicitly registered in
:data:`~core.telemetry.TELEMETRY_METRIC_REGISTRY` with ``remote_allowed=True``.

:func:`~core.telemetry.emit_telemetry_event`'s default sink,
:class:`~core.telemetry.LocalNoopTelemetrySink`, discards the payload -- this
proves the gate-then-schema-then-emit pipeline end-to-end without any real
transmission.
:class:`~core.telemetry.HttpTelemetrySink` is the real network-transmitting
implementation of the same :class:`~core.telemetry.TelemetrySink` protocol: it
is structurally inert (a pure no-op) unless a caller both builds it with a
configured ``settings.cadrumo_telemetry_endpoint`` AND the consent gate already
permitted emission, and any transport failure is swallowed rather than raised.
No caller wires it as a default sink today; a producer or CLI surface must
explicitly opt a call site into it.

Three non-sensitive operational producers are wired
(:func:`~core.telemetry.emit_command_invocation_telemetry`,
:func:`~core.telemetry.emit_llm_run_telemetry`,
:func:`~core.telemetry.emit_error_frequency_telemetry`), each registered in
:data:`~core.telemetry.TELEMETRY_METRIC_REGISTRY` and exercising the full
gate-then-schema-then-emit pipeline against the local sink.

See Also:
    :func:`~core.telemetry.telemetry_emit_permitted`
        Consent gate every remote-eligible event must pass.
    :func:`~core.telemetry.build_telemetry_payload`
        Payload builder that enforces the metric allowlist before emission.
    :class:`~core.telemetry.HttpTelemetrySink`
        Optional network sink; never the default transport.
"""

from __future__ import annotations

from ._consent import telemetry_emit_permitted
from ._emit import LocalNoopTelemetrySink, TelemetrySink, emit_telemetry_event
from ._http_sink import HttpTelemetrySink
from ._producers import (
    emit_command_invocation_telemetry,
    emit_error_frequency_telemetry,
    emit_llm_run_telemetry,
)
from ._schema import (
    TELEMETRY_METRIC_REGISTRY,
    CounterSpec,
    TelemetryEventPayload,
    TimingSpec,
    build_telemetry_payload,
)
from ._tier import TelemetryTier
from ._workspace import workspace_hash
from .errors import TelemetrySchemaError

__all__ = [
    "TELEMETRY_METRIC_REGISTRY",
    "CounterSpec",
    "HttpTelemetrySink",
    "LocalNoopTelemetrySink",
    "TelemetryEventPayload",
    "TelemetrySchemaError",
    "TelemetrySink",
    "TelemetryTier",
    "TimingSpec",
    "build_telemetry_payload",
    "emit_command_invocation_telemetry",
    "emit_error_frequency_telemetry",
    "emit_llm_run_telemetry",
    "emit_telemetry_event",
    "telemetry_emit_permitted",
    "workspace_hash",
]
