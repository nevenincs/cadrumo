"""Config repair maintenance behavior handlers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer

from ....application.diagnostics import (
    build_config_repair_report as _build_config_repair_report,
)
from ....application.diagnostics import (
    preview_quarantine_unreadable_secure_objects as _preview_quarantine_unreadable_secure_objects,
)
from ....application.diagnostics import (
    probe_browser_connectivity as _probe_browser_connectivity,
)
from ....application.diagnostics import (
    quarantine_unreadable_secure_objects as _quarantine_unreadable_secure_objects,
)
from ....application.diagnostics import (
    render_browser_connectivity_text as _render_browser_connectivity_text,
)
from ....application.diagnostics import (
    render_config_repair_text as _render_config_repair_text,
)
from ....core.bucket_pointer import resolve_active_bucket_id as _resolve_active_bucket_id
from ....core.json_contract import strict_round_trip
from ....core.logging import default_log_file_path as _default_log_file_path
from .._common import emit_envelope, resolve_cli_precondition_action
from ..errors import CliRefusedBoundaryError as _CliRefusedBoundaryError

if TYPE_CHECKING:
    from ....application.diagnostic_models import (
        ConfigRepairReport,
        DiagnosticCheck,
        SecureObjectIntegrityReport,
    )
    from ....application.workflow.events import WorkflowStateResetFingerprint
    from ..config_payloads import (
        ConfigRepairCheckPayload,
        ConfigRepairResult,
        RepairQuarantineResult,
        RepairResetProgressResult,
        WorkflowFingerprintPayload,
    )


def _workflow_fingerprint_payload(fingerprint: WorkflowStateResetFingerprint) -> WorkflowFingerprintPayload:
    """Project an encrypted-workflow reset fingerprint into its typed CLI payload."""
    from ..config_payloads import WorkflowFingerprintPayload

    return WorkflowFingerprintPayload(
        schema_version=fingerprint.schema_version,
        written_at=fingerprint.written_at,
        byte_length=fingerprint.byte_length,
        reason_class=fingerprint.reason_class,
        recovered_bucket_id=fingerprint.recovered_bucket_id or None,
    )


def _repair_check_payload(check: DiagnosticCheck) -> ConfigRepairCheckPayload:
    """Project one application diagnostic check into its typed CLI payload.

    The CLI boundary is where an application-owned precondition verdict
    becomes a schema-resolved wire action; every repair surface that emits a
    check row shares this one projection.
    """
    from ..config_payloads import ConfigRepairCheckPayload, ConfigRepairFindingPayload

    return ConfigRepairCheckPayload(
        name=check.name,
        status=check.status,
        summary=check.summary,
        detail=check.detail,
        precondition_action=(
            resolve_cli_precondition_action(check.precondition_verdict)
            if check.precondition_verdict is not None
            else None
        ),
        audience=check.audience,
        findings=[
            ConfigRepairFindingPayload(
                summary=finding.summary,
                detail=finding.detail,
                requirement=finding.requirement,
            )
            for finding in check.findings
        ],
    )


def _config_repair_result(report: ConfigRepairReport) -> ConfigRepairResult:
    """Project diagnostics through the one CLI action resolver before emitting.

    Diagnostics preserve application-owned precondition verdicts.  This is the
    CLI boundary where those records become schema-resolved wire actions; the
    application renderer never reconstructs command prose from them.
    """
    from ..config_payloads import (
        ConfigRepairNamespacePayload,
        ConfigRepairResult,
        ConfigRepairSecureObjectsPayload,
        ConfigRepairSetupPayload,
    )

    checks = [_repair_check_payload(check) for check in report.checks]
    return ConfigRepairResult(
        overall=report.overall,
        package_name=report.package_name,
        package_version=report.package_version,
        python_version=report.python_version,
        log_file=report.log_file,
        setup=(
            ConfigRepairSetupPayload(
                active_profile=report.setup.active_profile,
                profile_ready=report.setup.profile_ready,
                identity_ready=report.setup.identity_ready,
                enrolment_ready=report.setup.enrolment_ready,
                missing_required=list(report.setup.missing_required),
                missing_enrolment=list(report.setup.missing_enrolment),
                profile_present_keys=report.setup.profile_present_keys,
                profile_total_keys=report.setup.profile_total_keys,
                auth_provider=report.setup.auth_provider,
                login_ready=report.setup.login_ready,
            )
            if report.setup is not None
            else None
        ),
        secure_objects=ConfigRepairSecureObjectsPayload(
            namespaces=[
                ConfigRepairNamespacePayload(
                    namespace=item.namespace,
                    readable=item.readable,
                    unreadable=item.unreadable,
                )
                for item in report.secure_objects.namespaces
            ],
            readable_total=report.secure_objects.readable_total,
            unreadable_total=report.secure_objects.unreadable_total,
        ),
        checks=checks,
    )


def repair(ctx: typer.Context) -> None:
    """Diagnose and repair local configuration, profile, auth, and log state."""
    if ctx.invoked_subcommand is not None:
        return
    from ..config_payloads import ConfigRepairResult

    report = _build_config_repair_report()
    result = strict_round_trip(ConfigRepairResult, _config_repair_result(report))
    emit_envelope(
        ctx,
        command="config.repair",
        result=result,
        lines=_render_config_repair_text(report).splitlines(),
    )


def repair_logs(
    ctx: typer.Context,
    lines: int = 20,
) -> None:
    """Show the configured log file path and recent lines."""
    from ..config_payloads import RepairLogsResult

    path = _default_log_file_path()
    tail = _tail_lines(path, lines) if path.exists() and lines > 0 else ()
    result = RepairLogsResult(path=str(path), lines=list(tail))
    emit_envelope(
        ctx,
        command="config.repair.logs",
        result=result,
        lines=(f"path\t{path}", *tail),
    )


def _quarantine_result(report: SecureObjectIntegrityReport, *, dry_run: bool) -> RepairQuarantineResult:
    """Project one application quarantine report into the CLI result model."""
    from .._config_quarantine_payloads import QuarantineNamespacePayload
    from ..config_payloads import RepairQuarantineResult

    return RepairQuarantineResult(
        dry_run=dry_run,
        unreadable_total=report.unreadable_total,
        readable_total=report.readable_total,
        namespaces=[
            QuarantineNamespacePayload(
                namespace=item.namespace,
                readable=item.readable,
                unreadable=item.unreadable,
            )
            for item in report.namespaces
        ],
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
    from ..config_payloads import RepairQuarantineResult

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
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.repair.quarantine_requires_yes",
        )
    if _resolve_active_bucket_id() is None:
        _emit_no_active_quarantine(ctx, dry_run=dry_run)
        return
    report = _preview_quarantine_unreadable_secure_objects() if dry_run else _quarantine_unreadable_secure_objects()
    emit_envelope(
        ctx,
        command="config.repair.quarantine",
        result=_quarantine_result(report, dry_run=dry_run),
        lines=_quarantine_lines(report, dry_run=dry_run),
    )


def _reset_progress_result(
    fingerprint: WorkflowStateResetFingerprint,
    *,
    dry_run: bool,
) -> RepairResetProgressResult:
    """Project a workflow reset fingerprint into the typed CLI result."""
    from ..config_payloads import RepairResetProgressResult

    return RepairResetProgressResult(dry_run=dry_run, fingerprint=_workflow_fingerprint_payload(fingerprint))


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
    from ..config_payloads import RepairResetProgressResult

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
        raise _CliRefusedBoundaryError(translated_message="cli.config.repair.reset_progress_requires_yes")
    if _resolve_active_bucket_id() is None:
        _emit_no_active_reset_progress(ctx)
        return
    from ....application.workflow.persistence import fingerprint_workflow_state, reset_workflow_state

    fingerprint = fingerprint_workflow_state() if dry_run else reset_workflow_state()
    emit_envelope(
        ctx,
        command="config.repair.reset_progress",
        result=_reset_progress_result(fingerprint, dry_run=dry_run),
        lines=_reset_progress_lines(fingerprint, dry_run=dry_run),
    )


def repair_integrity_objects(
    ctx: typer.Context,
    namespace: str | None = None,
) -> None:
    """Report duplicate secure-object keys and unreadable encrypted rows."""
    from ..config_payloads import RepairIntegrityObjectsResult

    report = _preview_quarantine_unreadable_secure_objects()
    if namespace is not None:
        namespaces = tuple(item for item in report.namespaces if item.namespace == namespace)
        report = report.model_copy(
            update={
                "namespaces": namespaces,
                "readable_total": sum(item.readable for item in namespaces),
                "unreadable_total": sum(item.unreadable for item in namespaces),
            },
        )
    result = RepairIntegrityObjectsResult.model_validate(
        {
            **report.model_dump(mode="json"),
            "check": {
                "status": "fail" if report.unreadable_total else "ok",
                "summary": f"{report.unreadable_total} unreadable secure-object rows",
            },
        },
    )
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
    from ..config_payloads import RepairConnectivityResult

    _ = headless
    report = _probe_browser_connectivity()
    result = RepairConnectivityResult(target="aeat_sede", status=report.model_dump(mode="json"))
    emit_envelope(
        ctx,
        command="config.repair.connectivity",
        result=result,
        lines=_render_browser_connectivity_text(report).splitlines(),
    )


def _tail_lines(path: Path, count: int) -> tuple[str, ...]:
    """Return the last ``count`` lines from ``path`` without trailing newlines."""
    if count <= 0:
        return ()
    chunk_size = 8192
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            file_size = handle.tell()
            blocks: list[bytes] = []
            newlines_seen = 0
            position = file_size
            while position > 0 and newlines_seen <= count:
                read_size = min(chunk_size, position)
                position -= read_size
                handle.seek(position)
                block = handle.read(read_size)
                blocks.append(block)
                newlines_seen += block.count(b"\n")
    except OSError:
        return ()
    data = b"".join(reversed(blocks))
    text = data.decode("utf-8", errors="replace")
    return tuple(text.splitlines()[-count:])


__all__ = [
    "repair",
    "repair_connectivity",
    "repair_integrity_objects",
    "repair_logs",
    "repair_quarantine",
    "repair_reset_progress",
]
