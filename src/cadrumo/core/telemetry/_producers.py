"""Non-sensitive operational telemetry producers.

Each function here projects an already-non-sensitive local signal into an
allowlisted :class:`~core.telemetry.TelemetryEventPayload` (via
:func:`~core.telemetry.build_telemetry_payload`) and hands it to
:func:`~core.telemetry.emit_telemetry_event`. Every producer is a pure
projection: it reads fields that are already accounting/timing metadata (a
command name, a duration, a success flag, a closed error-kind label) and never
reads transaction content, profile identity, or file contents.

No producer here performs a network call. When the consent gate refuses (the
default posture), :func:`~core.telemetry.emit_telemetry_event` is a pure
no-op and none of these functions have any observable side effect beyond that
no-op return value.

See Also:
    :func:`~core.telemetry.build_telemetry_payload`
        Closed-schema builder each producer uses before emission.
    :func:`~core.telemetry.emit_telemetry_event`
        Consent-gated dispatcher shared by all producers.
    :func:`~core.telemetry.workspace_hash`
        Stable pseudonymous deployment identifier carried by producer payloads.
    :data:`~core.telemetry.TELEMETRY_METRIC_REGISTRY`
        Metric allowlist that declares which counters and timings may be remote.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .emit import emit_telemetry_event
from .schema import build_telemetry_payload

if TYPE_CHECKING:
    from ..config import Settings
    from .emit import TelemetrySink

__all__ = ["emit_command_invocation_telemetry", "emit_error_frequency_telemetry", "emit_llm_run_telemetry"]


def emit_command_invocation_telemetry(
    *,
    workspace_hash: str,
    succeeded: bool,
    duration_ms: int,
    captured_at: str,
    settings: Settings,
    acknowledged: bool,
    sink: TelemetrySink | None = None,
) -> bool:
    """Emit a non-sensitive CLI command-completion event.

    Carries only an invocation count, a succeeded/failed split, and a
    wall-clock duration -- never the command's arguments, output, or any
    operator-supplied content. Registered under the closed
    ``"diagnostics.command_invocation"``
    :class:`~core.telemetry._schema.MetricSchema`.

    Args:
        workspace_hash: Stable pseudonymous local-deployment identifier (see
            :func:`~core.telemetry.workspace_hash`).
        succeeded: Whether the CLI invocation completed without raising.
        duration_ms: Wall-clock invocation duration in milliseconds.
        captured_at: ISO-8601 UTC capture timestamp.
        settings: Resolved deployment settings carrying the telemetry consent
            posture.
        acknowledged: Whether the operator acknowledged remote telemetry for
            this specific invocation. Never sticky.
        sink: Destination sink; defaults to
            :class:`~core.telemetry.LocalNoopTelemetrySink`.

    Returns:
        ``True`` when the event was handed to the sink; ``False`` when the
        consent gate refused and emission was a no-op.
    """
    payload = build_telemetry_payload(
        workspace_hash=workspace_hash,
        command="diagnostics.command_invocation",
        counters={"invocations": 1, "succeeded": 1 if succeeded else 0, "failed": 0 if succeeded else 1},
        timings_ms={"duration": duration_ms},
        succeeded=succeeded,
        captured_at=captured_at,
    )
    return emit_telemetry_event(payload, settings=settings, acknowledged=acknowledged, sink=sink)


def emit_llm_run_telemetry(
    *,
    workspace_hash: str,
    succeeded: bool,
    duration_ms: int,
    captured_at: str,
    settings: Settings,
    acknowledged: bool,
    sink: TelemetrySink | None = None,
) -> bool:
    """Emit a non-sensitive local-LLM-run-completion event.

    Projects the same accounting fields
    :class:`~adapters.outbound.llm.LLMRunRecord` already carries locally
    (run count, succeeded/failed split, duration) into the remote-eligible
    allowlist -- never the run's prompt text, response text, or provider
    payload. Registered under the closed ``"diagnostics.llm_run"``
    :class:`~core.telemetry._schema.MetricSchema`.

    Args:
        workspace_hash: Stable pseudonymous local-deployment identifier.
        succeeded: Whether the LLM run completed without raising.
        duration_ms: Wall-clock run duration in milliseconds.
        captured_at: ISO-8601 UTC capture timestamp.
        settings: Resolved deployment settings carrying the telemetry consent
            posture.
        acknowledged: Whether the operator acknowledged remote telemetry for
            this specific invocation. Never sticky.
        sink: Destination sink; defaults to
            :class:`~core.telemetry.LocalNoopTelemetrySink`.

    Returns:
        ``True`` when the event was handed to the sink; ``False`` when the
        consent gate refused and emission was a no-op.
    """
    payload = build_telemetry_payload(
        workspace_hash=workspace_hash,
        command="diagnostics.llm_run",
        counters={"runs": 1, "succeeded": 1 if succeeded else 0, "failed": 0 if succeeded else 1},
        timings_ms={"duration": duration_ms},
        succeeded=succeeded,
        captured_at=captured_at,
    )
    return emit_telemetry_event(payload, settings=settings, acknowledged=acknowledged, sink=sink)


def emit_error_frequency_telemetry(
    *,
    workspace_hash: str,
    error_kind: str,
    captured_at: str,
    settings: Settings,
    acknowledged: bool,
    sink: TelemetrySink | None = None,
) -> bool:
    """Emit a single non-sensitive error-kind occurrence.

    ``error_kind`` MUST be a short closed label (an exception class name such
    as ``"LLMClassifierError"``, mirroring
    :attr:`~adapters.outbound.llm.LLMRunRecord.error_kind`) -- never raw
    exception text, a stack trace, or any operator-controlled string.
    Registered under the closed ``"diagnostics.error_frequency"``
    :class:`~core.telemetry._schema.MetricSchema`.

    Args:
        workspace_hash: Stable pseudonymous local-deployment identifier.
        error_kind: Closed short error-kind label for this occurrence.
        captured_at: ISO-8601 UTC capture timestamp.
        settings: Resolved deployment settings carrying the telemetry consent
            posture.
        acknowledged: Whether the operator acknowledged remote telemetry for
            this specific invocation. Never sticky.
        sink: Destination sink; defaults to
            :class:`~core.telemetry.LocalNoopTelemetrySink`.

    Returns:
        ``True`` when the event was handed to the sink; ``False`` when the
        consent gate refused and emission was a no-op.
    """
    payload = build_telemetry_payload(
        workspace_hash=workspace_hash,
        command="diagnostics.error_frequency",
        counters={"occurrences": 1},
        succeeded=False,
        error_kind=error_kind,
        captured_at=captured_at,
    )
    return emit_telemetry_event(payload, settings=settings, acknowledged=acknowledged, sink=sink)
