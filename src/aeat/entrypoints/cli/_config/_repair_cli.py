"""Config repair maintenance command registration."""

from __future__ import annotations

from pathlib import Path

import typer

from ....application.diagnostics import (
    build_config_repair_report as _build_config_repair_report,
)
from ....application.diagnostics import (
    build_registry_integrity_report as _build_registry_integrity_report,
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
from ....core import resolve_active_bucket_id as _resolve_active_bucket_id
from ....core.i18n import tr
from ....core.logging import default_log_file_path as _default_log_file_path
from .._common import _emit, _emit_envelope
from .._errors import CliRefusedBoundaryError as _CliRefusedBoundaryError


def register_repair_maintenance_commands(repair_app: typer.Typer) -> None:
    """Register config repair maintenance commands."""
    _register_repair_root_callback(repair_app)
    _register_repair_logs_command(repair_app)
    _register_repair_quarantine_command(repair_app)
    _register_repair_reset_progress_command(repair_app)
    _register_repair_integrity_commands(repair_app)
    _register_repair_connectivity_command(repair_app)


def _register_repair_root_callback(repair_app: typer.Typer) -> None:
    @repair_app.callback()
    def repair(ctx: typer.Context) -> None:
        """Diagnose and repair local configuration, registry, profile, auth, and log state."""
        if ctx.invoked_subcommand is not None:
            return
        report = _build_config_repair_report()
        _emit(ctx, report.model_dump(mode="json"), _render_config_repair_text(report).splitlines())


def _register_repair_logs_command(repair_app: typer.Typer) -> None:
    @repair_app.command("logs", help=tr("cli.config.repair.logs_help"))
    def repair_logs(
        ctx: typer.Context,
        lines: int = typer.Option(20, "--lines", min=0, help=tr("cli.config.repair.logs_lines_help")),
    ) -> None:
        """Show the configured log file path and recent lines."""
        from .._config_payloads import RepairLogsResult

        path = _default_log_file_path()
        tail = _tail_lines(path, lines) if path.exists() and lines > 0 else ()
        result = RepairLogsResult(path=str(path), lines=list(tail))
        _emit_envelope(
            ctx,
            command="config.repair.logs",
            result=result,
            lines=(f"path\t{path}", *tail),
        )


def _register_repair_quarantine_command(repair_app: typer.Typer) -> None:
    @repair_app.command("quarantine", help=tr("cli.config.repair.quarantine_help"))
    def repair_quarantine(
        ctx: typer.Context,
        yes: bool = typer.Option(False, "--yes", help=tr("cli.config.repair.quarantine_yes_help")),
        dry_run: bool = typer.Option(
            False,
            "--dry-run/--no-dry-run",
            help=tr("cli.config.repair.quarantine_dry_run_help"),
        ),
    ) -> None:
        """Move secure-object rows that fail tag verification into quarantine."""
        from .._config_payloads import QuarantineNamespacePayload, RepairQuarantineResult

        if not dry_run and not yes:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.repair.quarantine_requires_yes",
            )
        if _resolve_active_bucket_id() is None:
            result = RepairQuarantineResult(dry_run=dry_run, quarantined=0, retained=0, reason="no-active-profile")
            _emit_envelope(
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
            return
        if dry_run:
            report = _preview_quarantine_unreadable_secure_objects()
            result = RepairQuarantineResult(
                dry_run=True,
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
            _emit_envelope(
                ctx,
                command="config.repair.quarantine",
                result=result,
                lines=(
                    "dry_run\ttrue",
                    f"would_quarantine\t{report.unreadable_total}",
                    f"would_retain\t{report.readable_total}",
                    *tuple(f"{item.namespace}\t{item.unreadable}" for item in report.namespaces if item.unreadable > 0),
                ),
            )
            return
        report = _quarantine_unreadable_secure_objects()
        result = RepairQuarantineResult(
            dry_run=False,
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
        _emit_envelope(
            ctx,
            command="config.repair.quarantine",
            result=result,
            lines=(
                "dry_run\tfalse",
                f"quarantined\t{report.unreadable_total}",
                f"retained\t{report.readable_total}",
                *tuple(f"{item.namespace}\t{item.unreadable}" for item in report.namespaces if item.unreadable > 0),
            ),
        )


def _register_repair_reset_progress_command(repair_app: typer.Typer) -> None:
    @repair_app.command("reset-progress", help=tr("cli.config.repair.reset_progress_help"))
    def repair_reset_progress(
        ctx: typer.Context,
        yes: bool = typer.Option(False, "--yes", help=tr("cli.config.repair.reset_progress_yes_help")),
        dry_run: bool = typer.Option(
            False,
            "--dry-run/--no-dry-run",
            help=tr("cli.config.repair.reset_progress_dry_run_help"),
        ),
    ) -> None:
        """Reset the saved interrupted-command progress after reporting its corruption fingerprint."""
        from .._config_payloads import RepairResetProgressResult, WorkflowFingerprintPayload

        if not dry_run and not yes:
            raise _CliRefusedBoundaryError(translated_message="cli.config.repair.reset_progress_requires_yes")
        if _resolve_active_bucket_id() is None:
            result = RepairResetProgressResult(reset=False, reason="nothing to reset")
            _emit_envelope(
                ctx,
                command="config.repair.reset_progress",
                result=result,
                lines=("reset\tfalse", "reason\tnothing to reset"),
            )
            return
        from ....application.workflow import fingerprint_workflow_state, reset_workflow_state

        if dry_run:
            fingerprint = fingerprint_workflow_state()
            fp = WorkflowFingerprintPayload(
                schema_version=fingerprint.schema_version,
                written_at=fingerprint.written_at.isoformat() if fingerprint.written_at is not None else None,
                byte_length=fingerprint.byte_length,
                reason_class=fingerprint.reason_class,
                recovered_bucket_id=fingerprint.recovered_bucket_id or None,
            )
            result = RepairResetProgressResult(dry_run=True, fingerprint=fp)
            lines = (
                "dry_run\ttrue",
                f"schema_version\t{fingerprint.schema_version if fingerprint.schema_version is not None else '<none>'}",
                f"written_at\t{fingerprint.written_at.isoformat() if fingerprint.written_at is not None else '<none>'}",
                f"byte_length\t{fingerprint.byte_length if fingerprint.byte_length is not None else '<none>'}",
                f"reason_class\t{fingerprint.reason_class}",
                f"recovered_bucket_id\t{fingerprint.recovered_bucket_id or '<none>'}",
            )
            _emit_envelope(ctx, command="config.repair.reset_progress", result=result, lines=lines)
            return
        fingerprint = reset_workflow_state()
        fp = WorkflowFingerprintPayload(
            schema_version=fingerprint.schema_version,
            written_at=fingerprint.written_at.isoformat() if fingerprint.written_at is not None else None,
            byte_length=fingerprint.byte_length,
            reason_class=fingerprint.reason_class,
            recovered_bucket_id=fingerprint.recovered_bucket_id or None,
        )
        result = RepairResetProgressResult(dry_run=False, fingerprint=fp)
        lines = (
            "dry_run\tfalse",
            f"schema_version\t{fingerprint.schema_version if fingerprint.schema_version is not None else '<none>'}",
            f"written_at\t{fingerprint.written_at.isoformat() if fingerprint.written_at is not None else '<none>'}",
            f"byte_length\t{fingerprint.byte_length if fingerprint.byte_length is not None else '<none>'}",
            f"reason_class\t{fingerprint.reason_class}",
            f"recovered_bucket_id\t{fingerprint.recovered_bucket_id or '<none>'}",
        )
        _emit_envelope(ctx, command="config.repair.reset_progress", result=result, lines=lines)


def _register_repair_integrity_commands(repair_app: typer.Typer) -> None:
    integrity_app = typer.Typer(
        name="integrity",
        help=tr(
            "cli.config.repair.integrity_help",
            default="Probe secure-object and registry integrity.",
        ),
        no_args_is_help=True,
    )

    @integrity_app.command(
        "objects",
        help=tr(
            "cli.config.repair.integrity.objects_help",
            default="Probe persisted secure objects for duplicate keys and tag failures.",
        ),
    )
    def repair_integrity_objects(
        ctx: typer.Context,
        namespace: str | None = typer.Option(
            None,
            "--namespace",
            help=tr("cli.config.repair.integrity.objects_namespace_help", default="Limit output to one namespace."),
        ),
    ) -> None:
        """Report duplicate secure-object keys and unreadable encrypted rows."""
        from .._config_payloads import RepairIntegrityObjectsResult

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
        _emit_envelope(
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

    @integrity_app.command(
        "registry",
        help=tr(
            "cli.config.repair.integrity.registry_help",
            default="Probe calculation registry snapshot and authority integrity.",
        ),
    )
    def repair_integrity_registry(ctx: typer.Context) -> None:
        """Report calculation registry authority and bundled snapshot integrity."""
        from .._config_payloads import RepairIntegrityRegistryResult

        report = _build_registry_integrity_report()
        result = RepairIntegrityRegistryResult.model_validate(report.model_dump(mode="json"))
        issue_lines = tuple(f"issue\t{finding.summary}" for finding in report.check.findings)
        _emit_envelope(
            ctx,
            command="config.repair.integrity.registry",
            result=result,
            lines=(
                f"ok\t{report.check.status == 'ok'}",
                f"issues\t{len(report.check.findings)}",
                *issue_lines,
            ),
        )

    repair_app.add_typer(integrity_app, name="integrity")


def _register_repair_connectivity_command(repair_app: typer.Typer) -> None:
    @repair_app.command("connectivity", help=tr("cli.config.repair.connectivity_help"))
    def repair_connectivity(ctx: typer.Context, headless: bool = typer.Option(True, "--headless/--headed")) -> None:
        """Probe browser connectivity to the AEAT Sede landing page."""
        from .._config_payloads import RepairConnectivityResult

        _ = headless
        report = _probe_browser_connectivity()
        result = RepairConnectivityResult(target="aeat_sede", status=report.model_dump(mode="json"))
        _emit_envelope(
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
