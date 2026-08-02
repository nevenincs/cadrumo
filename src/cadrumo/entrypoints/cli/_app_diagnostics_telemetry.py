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
through :func:`~entrypoints.cli._common._emit_envelope`.

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

from typing import TYPE_CHECKING

import typer

from ...core.i18n import tr
from ._common import _emit_envelope
from ._diagnostics_payloads import (
    TelemetryFlushResult,
    TelemetryPayloadPreviewPayload,
    TelemetryStatusResult,
)

if TYPE_CHECKING:
    from ...core.telemetry import TelemetryTier

telemetry_app = typer.Typer(
    name="telemetry",
    help=tr(
        "cli.diagnostics.telemetry.app_help",
        default="Inspect and control the default-off, opt-in remote telemetry tier.",
    ),
    no_args_is_help=True,
)


@telemetry_app.command(
    "status",
    help=tr(
        "cli.diagnostics.telemetry.status.help",
        default="Report the current remote-telemetry consent posture. Never emits anything.",
    ),
)
def diagnostics_telemetry_status(
    ctx: typer.Context,
    opt_in: bool | None = typer.Option(
        None,
        "--opt-in/--no-opt-in",
        help=tr(
            "cli.diagnostics.telemetry.opt_in_help",
            default=(
                "Preview the posture as if CADRUMO_TELEMETRY_OPT_IN were this value for this "
                "invocation only; omit to report the deployment's actual configured setting."
            ),
        ),
    ),
    tier: str | None = typer.Option(
        None,
        "--tier",
        help=tr(
            "cli.diagnostics.telemetry.tier_help",
            default=(
                "Preview the posture as if CADRUMO_TELEMETRY_TIER were this value (off / crash_only / "
                "full) for this invocation only; omit to report the deployment's actual configured tier."
            ),
        ),
    ),
    endpoint: str | None = typer.Option(
        None,
        "--endpoint",
        help=tr(
            "cli.diagnostics.telemetry.endpoint_help",
            default=(
                "Preview the posture as if CADRUMO_TELEMETRY_ENDPOINT were this URL for this invocation "
                "only; omit to report the deployment's actual configured endpoint."
            ),
        ),
    ),
) -> None:
    """Report the current remote-telemetry consent posture; never emits anything."""
    from ...application.diagnostics_telemetry import build_telemetry_status_report
    from ...core.config import override_settings
    from ...core.telemetry import TelemetryTier

    overrides: dict[str, object] = {}
    if opt_in is not None:
        overrides["cadrumo_telemetry_opt_in"] = opt_in
    if tier is not None:
        overrides["cadrumo_telemetry_tier"] = _parse_tier(tier)
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
                    "Telemetry stays fully local by default. To opt in, set CADRUMO_TELEMETRY_OPT_IN=true "
                    "and CADRUMO_TELEMETRY_TIER to crash_only or full in env/.env."
                ),
            ),
        )

    _emit_envelope(ctx, command="diagnostics.telemetry.status", result=result, lines=lines)


@telemetry_app.command(
    "flush",
    help=tr(
        "cli.diagnostics.telemetry.flush.help",
        default="Build the aggregate local telemetry payload and, unless --dry-run, send it.",
    ),
)
def diagnostics_telemetry_flush(
    ctx: typer.Context,
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help=tr(
            "cli.diagnostics.telemetry.flush.dry_run_help",
            default=(
                "Preview the payload that would be sent without transmitting anything (default). "
                "Pass --no-dry-run to actually send when the consent gate permits."
            ),
        ),
    ),
    opt_in: bool | None = typer.Option(
        None,
        "--opt-in/--no-opt-in",
        help=tr(
            "cli.diagnostics.telemetry.opt_in_help",
            default=(
                "Preview/send as if CADRUMO_TELEMETRY_OPT_IN were this value for this invocation only; "
                "omit to use the deployment's actual configured setting."
            ),
        ),
    ),
    tier: str | None = typer.Option(
        None,
        "--tier",
        help=tr(
            "cli.diagnostics.telemetry.tier_help",
            default=(
                "Preview/send as if CADRUMO_TELEMETRY_TIER were this value (off / crash_only / full) for "
                "this invocation only; omit to use the deployment's actual configured tier."
            ),
        ),
    ),
    endpoint: str | None = typer.Option(
        None,
        "--endpoint",
        help=tr(
            "cli.diagnostics.telemetry.endpoint_help",
            default=(
                "Preview/send as if CADRUMO_TELEMETRY_ENDPOINT were this URL for this invocation only; "
                "omit to use the deployment's actual configured endpoint."
            ),
        ),
    ),
    acknowledge: bool = typer.Option(
        False,
        "--acknowledge-remote-telemetry",
        help=tr(
            "cli.diagnostics.telemetry.flush.acknowledge_help",
            default=(
                "Acknowledge this specific remote-telemetry send. Required (in addition to opt-in "
                "and a non-off tier) for --no-dry-run to actually transmit; never sticky, re-affirm "
                "on every invocation."
            ),
        ),
    ),
) -> None:
    """Build the aggregate local telemetry payload and, unless --dry-run, send it."""
    from ...application.diagnostics_telemetry import build_telemetry_flush_preview, flush_telemetry
    from ...core.config import load_settings, override_settings
    from ...core.json_contract import Notice, NoticeSeverity

    overrides: dict[str, object] = {}
    if opt_in is not None:
        overrides["cadrumo_telemetry_opt_in"] = opt_in
    if tier is not None:
        overrides["cadrumo_telemetry_tier"] = _parse_tier(tier)
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

    payload_row = TelemetryPayloadPreviewPayload(
        schema_version=preview.payload.schema_version,
        workspace_hash=preview.payload.workspace_hash,
        command=preview.payload.command,
        counters=dict(preview.payload.counters),
        timings_ms=dict(preview.payload.timings_ms),
        succeeded=preview.payload.succeeded,
        error_kind=preview.payload.error_kind,
        captured_at=preview.payload.captured_at,
    )

    result = TelemetryFlushResult(
        dry_run=dry_run,
        payload=payload_row,
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
        f"command\t{payload_row.command}",
        f"counters\t{payload_row.counters}",
        f"succeeded\t{payload_row.succeeded}",
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
                suggestion="aeat app diagnostics telemetry flush --no-dry-run --acknowledge-remote-telemetry",
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

    _emit_envelope(ctx, command="diagnostics.telemetry.flush", result=result, lines=lines, notices=notices)


def _parse_tier(value: str) -> TelemetryTier:
    from ...core.telemetry import TelemetryTier
    from ._common import _bad

    try:
        return TelemetryTier(value.strip().lower())
    except ValueError as exc:
        accepted = ", ".join(member.value for member in TelemetryTier)
        raise _bad(
            tr(
                "cli.diagnostics.telemetry.bad_tier",
                value=value,
                accepted=accepted,
                default=f"--tier must be one of: {accepted}; got {value!r}.",
            ),
        ) from exc
