"""Config repair maintenance behavior handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from cadrumo_client.commands.errors import CliRefusedBoundaryError

from ....adapters.outbound.aeat.browser.connectivity import (
    probe_browser_connectivity,
)
from ....application.connectivity_probe import probe_connectivity
from ....application.diagnostics import (
    build_config_repair_report,
    render_config_repair_text,
)
from ....application.diagnostics_repair import (
    check_secure_object_integrity,
    read_log_tail,
    run_secure_object_quarantine,
    run_workflow_progress_reset,
)
from ....application.diagnostics_repair_documents import (
    connectivity_document,
    integrity_objects_document,
    quarantine_document,
    repair_report_document,
    reset_progress_document,
)
from ....core.bucket_pointer import resolve_active_bucket_id
from ....core.json_contract import strict_round_trip
from ..common import emit_envelope, resolve_cli_precondition_action
from .connectivity_rendering import render_browser_connectivity_text

if TYPE_CHECKING:
    from ....application.diagnostic_models import SecureObjectIntegrityReport
    from ....application.workflow.events import WorkflowStateResetFingerprint


def repair(ctx: typer.Context) -> None:
    """Diagnose and repair local configuration, profile, auth, and log state."""
    if ctx.invoked_subcommand is not None:
        return
    from cadrumo_client.commands.payloads import ConfigRepairResult

    from ..state_projection_support import diagnostics_ports

    report = build_config_repair_report(ports=diagnostics_ports(ctx))
    document = repair_report_document(report, resolve_action=resolve_cli_precondition_action)
    result = strict_round_trip(ConfigRepairResult, document)
    lines = render_config_repair_text(report).splitlines()
    emit_envelope(
        ctx,
        command="config.repair",
        result=result,
        lines=lines,
    )


def repair_logs(
    ctx: typer.Context,
    lines: int = 20,
) -> None:
    """Show the configured log file path and recent lines."""
    from cadrumo_client.commands.payloads import RepairLogsResult

    tail = read_log_tail(lines)
    result = RepairLogsResult(path=tail.path, lines=list(tail.lines))
    emit_envelope(
        ctx,
        command="config.repair.logs",
        result=result,
        lines=(f"path\t{tail.path}", *tail.lines),
    )


def _quarantine_lines(report: SecureObjectIntegrityReport, *, dry_run: bool) -> tuple[str, ...]:
    """Render the preview or committed quarantine counters in stable order."""
    quarantine_label = "would_quarantine" if dry_run else "quarantined"
    retain_label = "would_retain" if dry_run else "retained"
    return (
        f"dry_run\t{str(dry_run).lower()}",
        f"{quarantine_label}\t{report.unreadable_total}",
        f"{retain_label}\t{report.readable_total}",
        *tuple(f"{item.namespace}\t{item.unreadable}" for item in report.namespaces if item.unreadable > 0),
    )


def _emit_no_active_quarantine(ctx: typer.Context, *, dry_run: bool) -> None:
    """Emit the non-mutating no-active-profile quarantine outcome."""
    from cadrumo_client.commands.payloads import RepairQuarantineResult

    result = RepairQuarantineResult(dry_run=dry_run, quarantined=0, retained=0, reason="no-active-profile")
    emit_envelope(
        ctx,
        command="config.repair.quarantine",
        result=result,
        lines=(
            f"dry_run\t{str(dry_run).lower()}",
            "quarantined\t0",
            "retained\t0",
            "reason\tno active profile; nothing to quarantine",
        ),
    )


def repair_quarantine(
    ctx: typer.Context,
    yes: bool = False,
    dry_run: bool = False,
) -> None:
    """Move secure-object rows that fail tag verification into quarantine."""
    if not dry_run and not yes:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.repair.quarantine_requires_yes",
        )
    if resolve_active_bucket_id() is None:
        _emit_no_active_quarantine(ctx, dry_run=dry_run)
        return
    from cadrumo_client.commands.payloads import RepairQuarantineResult

    from ..state_projection_support import diagnostics_ports

    report = run_secure_object_quarantine(ports=diagnostics_ports(ctx), dry_run=dry_run)
    emit_envelope(
        ctx,
        command="config.repair.quarantine",
        result=strict_round_trip(RepairQuarantineResult, quarantine_document(report, dry_run=dry_run)),
        lines=_quarantine_lines(report, dry_run=dry_run),
    )


def _reset_progress_lines(fingerprint: WorkflowStateResetFingerprint, *, dry_run: bool) -> tuple[str, ...]:
    """Render the shared workflow fingerprint facts in the existing order."""
    progress_schema_version = fingerprint.schema_version if fingerprint.schema_version is not None else "<none>"
    saved_at = fingerprint.written_at.isoformat() if fingerprint.written_at is not None else "<none>"
    stored_bytes = fingerprint.byte_length if fingerprint.byte_length is not None else "<none>"
    if dry_run:
        return (
            "dry_run\ttrue",
            f"progress_schema_version\t{progress_schema_version}",
            f"saved_at\t{saved_at}",
            f"stored_bytes\t{stored_bytes}",
            f"read_status\t{fingerprint.reason_class}",
        )
    return (
        "dry_run\tfalse",
        "cleared\ttrue",
        f"progress_schema_version\t{progress_schema_version}",
        f"saved_at\t{saved_at}",
        f"stored_bytes\t{stored_bytes}",
        f"read_status\t{fingerprint.reason_class}",
    )


def _emit_no_active_reset_progress(ctx: typer.Context) -> None:
    """Emit the no-op reset outcome when no active profile exists."""
    from cadrumo_client.commands.payloads import RepairResetProgressResult

    result = RepairResetProgressResult(reset=False, reason="nothing to reset")
    emit_envelope(
        ctx,
        command="config.repair.reset_progress",
        result=result,
        lines=("reset\tfalse", "reason\tnothing to reset"),
    )


def repair_reset_progress(
    ctx: typer.Context,
    yes: bool = False,
    dry_run: bool = False,
) -> None:
    """Clear saved interrupted-command progress after summarising the saved record."""
    if not dry_run and not yes:
        raise CliRefusedBoundaryError(translated_message="cli.config.repair.reset_progress_requires_yes")
    if resolve_active_bucket_id() is None:
        _emit_no_active_reset_progress(ctx)
        return
    from cadrumo_client.commands.payloads import RepairResetProgressResult

    fingerprint = run_workflow_progress_reset(dry_run=dry_run)
    emit_envelope(
        ctx,
        command="config.repair.reset_progress",
        result=strict_round_trip(RepairResetProgressResult, reset_progress_document(fingerprint, dry_run=dry_run)),
        lines=_reset_progress_lines(fingerprint, dry_run=dry_run),
    )


def repair_integrity_objects(
    ctx: typer.Context,
    namespace: str | None = None,
) -> None:
    """Report duplicate secure-object keys and unreadable encrypted rows."""
    from cadrumo_client.commands.payloads import RepairIntegrityObjectsResult

    from ..state_projection_support import diagnostics_ports

    check = check_secure_object_integrity(ports=diagnostics_ports(ctx), namespace=namespace)
    report = check.report
    result = strict_round_trip(RepairIntegrityObjectsResult, integrity_objects_document(check))
    emit_envelope(
        ctx,
        command="config.repair.integrity.objects",
        result=result,
        lines=(
            f"readable\t{report.readable_total}",
            f"unreadable\t{report.unreadable_total}",
            *tuple(
                f"{item.namespace}\treadable={item.readable}\tunreadable={item.unreadable}"
                for item in report.namespaces
            ),
        ),
    )


def repair_connectivity(ctx: typer.Context, headless: bool = True) -> None:
    """Probe browser connectivity to the AEAT Sede landing page."""
    from cadrumo_client.commands.payloads import RepairConnectivityResult

    _ = headless
    report = probe_connectivity(probe_browser_connectivity)
    result = strict_round_trip(RepairConnectivityResult, connectivity_document(report))
    emit_envelope(
        ctx,
        command="config.repair.connectivity",
        result=result,
        lines=render_browser_connectivity_text(report.status).splitlines(),
    )


__all__ = [
    "repair",
    "repair_connectivity",
    "repair_integrity_objects",
    "repair_logs",
    "repair_quarantine",
    "repair_reset_progress",
]
