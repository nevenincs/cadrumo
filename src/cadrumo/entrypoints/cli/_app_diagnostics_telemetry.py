"""CLI commands for the ``aeat app diagnostics telemetry`` subcommand group.

Provides the ``status`` and ``flush`` verbs over the default-off,
consent-gated remote telemetry tier: ``status`` reports the deployment's current posture
(opt-in, tier, gestor mode, endpoint) without ever emitting anything;
``flush`` builds the one aggregate local-run payload a real send would
transmit and, by default (``--dry-run``, the CLI default), only PREVIEWS
it -- no network call is made. Passing ``--no-dry-run`` performs a real send,
and even then only when the consent gate permits AND an endpoint is
configured; otherwise it remains a safe no-op.

Every field this module can ever surface as "would be sent" is drawn from
:class:`~core.telemetry.TelemetryEventPayload`, the closed allowlisted
payload shape -- there is no other data source, so this transport module
cannot itself widen what telemetry carries.

This module is the transport adapter over
:func:`~application.diagnostics_telemetry.build_telemetry_status_report`,
:func:`~application.diagnostics_telemetry.build_telemetry_flush_preview`,
and :func:`~application.diagnostics_telemetry.flush_telemetry`. It emits
:class:`~entrypoints.cli._diagnostics_payloads.TelemetryStatusResult` and
:class:`~entrypoints.cli._diagnostics_payloads.TelemetryFlushResult`
through :func:`~entrypoints.cli._common.emit_envelope`.

See Also:
    :func:`~application.diagnostics_telemetry.build_telemetry_status_report`
        Read-only application service backing ``status``.
    :func:`~application.diagnostics_telemetry.build_telemetry_flush_preview`
        Dry-run payload builder backing the default ``flush`` mode.
    :func:`~application.diagnostics_telemetry.flush_telemetry`
        Non-dry-run application service that still honours the consent gate.
    :class:`~core.telemetry.TelemetryEventPayload`
        Closed payload shape surfaced in the flush preview result.
"""

from __future__ import annotations

import typer

from ...core.i18n.render import tr
from ...core.telemetry.tier import TelemetryTier
from ._common import emit_envelope
from ._diagnostics_payloads import (
    TelemetryFlushResult,
    TelemetryStatusResult,
)


def diagnostics_telemetry_status(
    ctx: typer.Context,
    opt_in: bool | None = None,
    tier: TelemetryTier | None = None,
    endpoint: str | None = None,
) -> None:
    """Report the current remote-telemetry consent posture; never emits anything."""
    from ...application.diagnostics_telemetry import build_telemetry_status_report
    from ...core.config import override_settings

    overrides: dict[str, object] = {}
    if opt_in is not None:
        overrides["cadrumo_telemetry_opt_in"] = opt_in
    if tier is not None:
        overrides["cadrumo_telemetry_tier"] = tier
    if endpoint is not None:
        overrides["cadrumo_telemetry_endpoint"] = endpoint

    if overrides:
        ctx.with_resource(override_settings(**overrides))

    report = build_telemetry_status_report()

    result = TelemetryStatusResult(
        opt_in=report.opt_in,
        tier=report.tier,
        gestor_mode=report.gestor_mode,
        endpoint=report.endpoint,
        would_emit_if_acknowledged=report.would_emit_if_acknowledged,
    )

    lines = [
        tr("cli.diagnostics.telemetry.status.header", default="Remote telemetry posture:"),
        f"opt_in\t{report.opt_in}",
        f"tier\t{report.tier.value}",
        f"gestor_mode\t{report.gestor_mode}",
        f"endpoint\t{report.endpoint or '(not set)'}",
        f"would_emit_if_acknowledged\t{report.would_emit_if_acknowledged}",
    ]
    if report.tier is TelemetryTier.OFF:
        lines.append(
            tr(
                "cli.diagnostics.telemetry.status.off_hint",
                default=(
                    "Telemetry stays fully local by default. To opt in, set the "
                    "CADRUMO_TELEMETRY_OPT_IN and CADRUMO_TELEMETRY_TIER environment variables "
                    "(CADRUMO_TELEMETRY_OPT_IN=true, CADRUMO_TELEMETRY_TIER=crash_only or full)."
                ),
            ),
        )

    emit_envelope(ctx, command="diagnostics.telemetry.status", result=result, lines=lines)


def diagnostics_telemetry_flush(
    ctx: typer.Context,
    dry_run: bool = True,
    opt_in: bool | None = None,
    tier: TelemetryTier | None = None,
    endpoint: str | None = None,
    acknowledge: bool = False,
) -> None:
    """Build the aggregate local telemetry payload and, unless --dry-run, send it."""
    from ...application.diagnostics_telemetry import build_telemetry_flush_preview, flush_telemetry
    from ...core.config import load_settings, override_settings
    from ...core.json_contract import Notice, NoticeSeverity

    overrides: dict[str, object] = {}
    if opt_in is not None:
        overrides["cadrumo_telemetry_opt_in"] = opt_in
    if tier is not None:
        overrides["cadrumo_telemetry_tier"] = tier
    if endpoint is not None:
        overrides["cadrumo_telemetry_endpoint"] = endpoint

    if overrides:
        ctx.with_resource(override_settings(**overrides))

    settings = load_settings()

    if dry_run:
        # A bare --dry-run never sends regardless of --acknowledge-remote-telemetry;
        # the preview still reflects the real acknowledgement value so the
        # operator can see exactly what a matching --no-dry-run run would do.
        preview = build_telemetry_flush_preview(settings=settings, acknowledged=acknowledge)
        sent = False
    else:
        preview = flush_telemetry(settings=settings, acknowledged=acknowledge)
        sent = preview.would_send

    result = TelemetryFlushResult(
        dry_run=dry_run,
        payload=preview.payload,
        gate_permits=preview.gate_permits,
        endpoint_configured=preview.endpoint_configured,
        would_send=preview.would_send,
        sent=sent,
    )

    lines = [
        tr(
            "cli.diagnostics.telemetry.flush.header",
            default="Telemetry payload (dry run, nothing sent):" if dry_run else "Telemetry flush:",
        ),
        f"command\t{preview.payload.command}",
        f"counters\t{preview.payload.counters}",
        f"succeeded\t{preview.payload.succeeded}",
        f"gate_permits\t{preview.gate_permits}",
        f"endpoint_configured\t{preview.endpoint_configured}",
        f"would_send\t{preview.would_send}",
        f"sent\t{sent}",
    ]

    notices: list[Notice] = []
    if dry_run:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="diagnostics.telemetry.flush.dry_run",
                message=tr(
                    "cli.diagnostics.telemetry.flush.dry_run_notice",
                    default="Dry run: this payload was built but nothing was transmitted.",
                ),
            ),
        )
    elif not preview.gate_permits:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="diagnostics.telemetry.flush.consent_refused",
                message=tr(
                    "cli.diagnostics.telemetry.flush.consent_refused_notice",
                    default=(
                        "Nothing was sent: remote telemetry is off by default (opt-in, tier, gestor "
                        "mode, or per-invocation acknowledgement refused it)."
                    ),
                ),
            ),
        )
    elif not preview.endpoint_configured:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="diagnostics.telemetry.flush.no_endpoint",
                message=tr(
                    "cli.diagnostics.telemetry.flush.no_endpoint_notice",
                    default="Nothing was sent: no CADRUMO_TELEMETRY_ENDPOINT is configured.",
                ),
            ),
        )

    emit_envelope(ctx, command="diagnostics.telemetry.flush", result=result, lines=lines, notices=notices)


__all__ = ["diagnostics_telemetry_flush", "diagnostics_telemetry_status"]
