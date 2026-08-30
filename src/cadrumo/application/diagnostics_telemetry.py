"""Remote-telemetry posture reporting and the dry-run-safe flush composition.

Wires the CLI surface over the core telemetry package
(:mod:`~core.telemetry`) without re-implementing any of its gate, schema,
or sink logic:

* :func:`~application.diagnostics_telemetry.build_telemetry_status_report`
  projects the current
  :class:`~core.config.Settings` posture (opt-in, tier, gestor mode,
  endpoint) plus whether an emission would currently be permitted, so an
  operator can inspect the deployment's telemetry posture without guessing at
  environment variable names.
* :func:`~application.diagnostics_telemetry.build_telemetry_flush_preview`
  aggregates the same local, non-sensitive LLM run-timing signal
  :func:`~application.diagnostics_run_health.build_run_health_report` already
  reads (:class:`~adapters.outbound.llm.LLMRunTelemetryRecorder`)
  into ONE allowlisted :class:`~core.telemetry.TelemetryEventPayload` via
  :func:`~core.telemetry.build_telemetry_payload`, and reports whether the
  consent gate (:func:`~core.telemetry.telemetry_emit_permitted`) would
  currently permit sending it. This function never sends anything: it is the
  ``--dry-run`` preview surface. ``build_telemetry_flush_preview`` is also the
  payload-construction step the real (non-dry-run) flush reuses, so preview and
  send can never observe a different payload shape.
* :func:`~application.diagnostics_telemetry.flush_telemetry` performs the real
  send: it reuses the identical
  preview payload, re-checks the consent gate, and -- only when both the gate
  permits AND an endpoint is configured -- hands the payload to a real
  :class:`~core.telemetry.HttpTelemetrySink`. When the gate refuses or no
  endpoint is configured, it is a pure no-op (mirroring
  :func:`~core.telemetry.emit_telemetry_event`'s own no-op contract), so
  calling this function is always safe regardless of posture.

No producer here reads transaction content, profile identity, or file
contents; the aggregate is built from the same accounting/timing-only
:class:`~adapters.outbound.llm.LLMRunRecord` rows the local-only
``run-health`` diagnostics already expose.

See Also:
    :mod:`~core.telemetry`
        Consent gate, closed payload schema, workspace hash, and optional HTTP
        sink reused by this application service.
    :func:`~application.diagnostics_run_health.build_run_health_report`
        Local-only LLM run accounting source aggregated by the flush preview.
    :mod:`~entrypoints.cli._app_diagnostics_telemetry`
        CLI transport that exposes status and dry-run-safe flush commands.
    :class:`~core.telemetry.TelemetryEventPayload`
        Closed allowlisted payload shape built by preview and reused by send.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ..core.config import Settings, load_settings
from ..core.telemetry import (
    HttpTelemetrySink,
    TelemetryEventPayload,
    TelemetryTier,
    build_telemetry_payload,
    emit_telemetry_event,
    telemetry_emit_permitted,
    workspace_hash,
)
from ..core.time import now
from .diagnostics_run_health import build_run_health_report

__all__ = [
    "TelemetryFlushPreview",
    "TelemetryStatusReport",
    "build_telemetry_flush_preview",
    "build_telemetry_status_report",
    "flush_telemetry",
]


_FLUSH_COMMAND = "diagnostics.llm_run"


#: Deliberately NOT the canonical ``STRICT_FROZEN_CONFIG``: the records below are
#: ``RootModel`` subclasses, and pydantic refuses ``extra`` on a root model
#: outright -- ``PydanticUserError: RootModel does not support setting
#: model_config['extra']``. The canonical config carries ``extra="forbid"``, so it
#: cannot be applied here at all. This is a constraint-shape divergence, not a
#: weaker config nobody chose.
_STRICT_FROZEN = ConfigDict(strict=True, frozen=True)


class TelemetryStatusReport(BaseModel):
    """The deployment's current remote-telemetry posture.

    Projects the raw :class:`~core.config.Settings` telemetry fields
    plus the derived ``would_emit`` verdict a hypothetical fully-acknowledged
    invocation would currently receive from
    :func:`~core.telemetry.telemetry_emit_permitted`. Never triggers an
    emission; this is a read-only report.
    """

    model_config = _STRICT_FROZEN

    opt_in: bool
    tier: TelemetryTier
    gestor_mode: bool
    endpoint: str | None = None
    would_emit_if_acknowledged: bool


class TelemetryFlushPreview(BaseModel):
    """The payload a flush would send, plus whether it would currently send at all.

    ``payload`` is the exact allowlisted :class:`~core.telemetry.TelemetryEventPayload`
    :func:`~application.diagnostics_telemetry.flush_telemetry` would hand to the
    sink; ``gate_permits`` and ``would_send`` are evaluated against the SAME
    ``acknowledged`` value the caller supplied (never hardcoded to ``True``), so
    a preview built without an acknowledgement honestly reports "would not
    currently send" even when opt-in, tier, and endpoint are otherwise fully
    configured. ``would_send`` folds the consent-gate verdict with whether an
    endpoint is configured, so a dry-run preview can honestly report "built, but
    would not transmit" (refused consent, or no endpoint) versus "would
    transmit".
    """

    model_config = _STRICT_FROZEN

    payload: TelemetryEventPayload
    gate_permits: bool
    endpoint_configured: bool
    would_send: bool


def build_telemetry_status_report(*, settings: Settings | None = None) -> TelemetryStatusReport:
    """Report the current remote-telemetry consent posture.

    Args:
        settings: Resolved deployment settings; defaults to
            :func:`~core.config.load_settings`.

    Returns:
        The populated
        :class:`~application.diagnostics_telemetry.TelemetryStatusReport`.
    """
    resolved_settings = settings if settings is not None else load_settings()
    return TelemetryStatusReport(
        opt_in=resolved_settings.cadrumo_telemetry_opt_in,
        tier=resolved_settings.cadrumo_telemetry_tier,
        gestor_mode=resolved_settings.cadrumo_telemetry_gestor_mode,
        endpoint=resolved_settings.cadrumo_telemetry_endpoint,
        would_emit_if_acknowledged=telemetry_emit_permitted(resolved_settings, acknowledged=True),
    )


def _build_flush_payload(settings: Settings) -> TelemetryEventPayload:
    report = build_run_health_report()
    return build_telemetry_payload(
        workspace_hash=workspace_hash(settings.cadrumo_local_storage_root),
        command=_FLUSH_COMMAND,
        counters={
            "runs": report.total_runs,
            "succeeded": report.total_succeeded,
            "failed": report.total_failed,
        },
        succeeded=report.total_failed == 0,
        captured_at=now().isoformat(),
    )


def build_telemetry_flush_preview(
    *,
    settings: Settings | None = None,
    acknowledged: bool = False,
) -> TelemetryFlushPreview:
    """Build the allowlisted payload a flush would send, without sending it.

    Aggregates every locally recorded LLM run
    (:class:`~adapters.outbound.llm.LLMRunRecord`, read via
    :func:`~application.diagnostics_run_health.build_run_health_report`)
    into one ``diagnostics.llm_run`` :class:`~core.telemetry.TelemetryEventPayload`.
    This is the sole payload-construction step; both the ``--dry-run`` preview
    and the real
    :func:`~application.diagnostics_telemetry.flush_telemetry` call this function
    so they can never observe a different payload shape.

    ``gate_permits``/``would_send`` are evaluated against ``acknowledged``
    exactly as supplied -- defaulting to ``False`` (the honest state of a bare
    ``--dry-run`` invocation with no acknowledgement flag), never hardcoded to
    ``True``. This mirrors :func:`~core.telemetry.telemetry_emit_permitted`'s
    own never-sticky per-invocation acknowledgement contract.

    Args:
        settings: Resolved deployment settings; defaults to
            :func:`~core.config.load_settings`.
        acknowledged: Whether the operator acknowledged remote telemetry for
            this specific invocation. Never sticky.

    Returns:
        The populated
        :class:`~application.diagnostics_telemetry.TelemetryFlushPreview`. Never
        performs a network call.
    """
    resolved_settings = settings if settings is not None else load_settings()
    payload = _build_flush_payload(resolved_settings)
    gate_permits = telemetry_emit_permitted(resolved_settings, acknowledged=acknowledged)
    endpoint_configured = bool(resolved_settings.cadrumo_telemetry_endpoint)
    return TelemetryFlushPreview(
        payload=payload,
        gate_permits=gate_permits,
        endpoint_configured=endpoint_configured,
        would_send=gate_permits and endpoint_configured,
    )


def flush_telemetry(*, settings: Settings | None = None, acknowledged: bool) -> TelemetryFlushPreview:
    """Send the aggregate local telemetry payload, honouring the consent gate.

    Reuses
    :func:`~application.diagnostics_telemetry.build_telemetry_flush_preview`
    (with the SAME ``acknowledged`` value) for payload construction and verdict
    computation, so the returned report always reflects the real invocation's
    acknowledgement -- never a hardcoded optimistic verdict. Delegates the
    actual gate check and dispatch to :func:`~core.telemetry.emit_telemetry_event`
    (``aeat-architecture-boundaries``): this function never
    re-implements the consent gate or the HTTP transport.

    A real send requires ALL of: the consent gate permits (deployment opt-in,
    non-``off`` tier, gestor mode off) AND ``acknowledged`` is ``True`` for
    THIS invocation (never sticky) AND ``settings.cadrumo_telemetry_endpoint`` is
    configured. Any missing condition makes this call a pure no-op -- nothing
    is sent -- mirroring :func:`~core.telemetry.emit_telemetry_event`'s own
    no-op contract.

    Args:
        settings: Resolved deployment settings; defaults to
            :func:`~core.config.load_settings`.
        acknowledged: Whether the operator acknowledged remote telemetry for
            this specific invocation. Never sticky; must be re-affirmed on
            every call.

    Returns:
        The :class:`~application.diagnostics_telemetry.TelemetryFlushPreview`
        reflecting exactly what was (or, because a condition was refused, would
        have been) sent for THIS invocation's ``acknowledged`` value.
    """
    resolved_settings = settings if settings is not None else load_settings()
    preview = build_telemetry_flush_preview(settings=resolved_settings, acknowledged=acknowledged)
    sink = HttpTelemetrySink(endpoint=resolved_settings.cadrumo_telemetry_endpoint)
    emit_telemetry_event(preview.payload, settings=resolved_settings, acknowledged=acknowledged, sink=sink)
    return preview
