"""Reconciliation command registration for ``aeat app modelo``."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer

from ...application.modelo import ModeloReconciliationReport, WorkUnit
from ...core.i18n import tr
from ._common import _emit_envelope

_require_active_profile: Callable[[], None] | None = None
_resolve_work_unit_for_cli: Callable[..., WorkUnit] | None = None
_resolve_default_actor: Callable[[], str] | None = None
_active_bucket_id: Callable[[], str] | None = None


def register_reconcile_commands(
    app: typer.Typer,
    *,
    require_active_profile: Callable[[], None],
    resolve_work_unit_for_cli: Callable[..., WorkUnit],
    resolve_default_actor: Callable[[], str],
    active_bucket_id: Callable[[], str],
) -> None:
    """Register local-only modelo reconciliation commands."""
    global _require_active_profile, _resolve_work_unit_for_cli, _resolve_default_actor, _active_bucket_id
    _require_active_profile = require_active_profile
    _resolve_work_unit_for_cli = resolve_work_unit_for_cli
    _resolve_default_actor = resolve_default_actor
    _active_bucket_id = active_bucket_id
    app.command(
        "reconciliation-history",
        help=tr(
            "cli.app.modelo.reconciliation_history.help",
            default=(
                "List past reconciliations recorded for the active profile. Reads the "
                "append-only MODELO_RECONCILED bucket-event history; reconciliations are "
                "repeatable on demand, so this is a convenience read-back, not a stored record."
            ),
        ),
    )(modelo_reconciliation_history_verb)
    app.command(
        "reconcile",
        help=tr(
            "cli.app.modelo.reconcile.help",
            default=(
                "Reconcile a modelo work unit against external evidence (justificante PDF). "
                "Local-only; never contacts AEAT."
            ),
        ),
    )(modelo_reconcile_verb)
    app.command(
        "reconcile-from-justificante",
        help=tr(
            "cli.app.modelo.reconcile_from_justificante.help",
            default=(
                "Reconcile a modelo work unit against a justificante PDF. Sugar for "
                'operators who think "reconcile from this justificante" rather than '
                '"reconcile, source = justificante". Shares the modelo_reconcile '
                "application service entry point with the flag-based form. Local-only; "
                "never contacts AEAT."
            ),
        ),
    )(modelo_reconcile_from_justificante_verb)


def _require_profile() -> None:
    if _require_active_profile is None:
        raise RuntimeError("modelo reconcile commands were not registered")
    _require_active_profile()


def _resolve_default_actor_value() -> str:
    if _resolve_default_actor is None:
        raise RuntimeError("modelo reconcile commands were not registered")
    return _resolve_default_actor()


def _resolve_work_unit(
    *,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: str | None,
    revision: str | None,
    bucket_id: str | None,
) -> WorkUnit:
    if _resolve_work_unit_for_cli is None:
        raise RuntimeError("modelo reconcile commands were not registered")
    return _resolve_work_unit_for_cli(
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
    )


def _render_reconciliation_report(
    ctx: typer.Context,
    report: ModeloReconciliationReport,
    *,
    command: str,
) -> None:
    """Render a :class:`~aeat.application.modelo.ModeloReconciliationReport` through the typed envelope."""
    from ._common import _emit_envelope
    from ._modelo_payloads import (
        ModeloReconcileResult,
        ModeloReconciliationDiffPayload,
    )

    result = ModeloReconcileResult(
        work_unit_id=report.work_unit_id,
        bucket_id=report.bucket_id,
        source_kind=report.source_kind.value,
        source_path=report.source_path,
        verdict=report.verdict.value,
        diffs=tuple(
            ModeloReconciliationDiffPayload(
                field_name=diff.field_name,
                work_unit_value=diff.work_unit_value,
                evidence_value=diff.evidence_value,
                kind=diff.kind,
            )
            for diff in report.diffs
        ),
        reconciled_at=report.reconciled_at.isoformat(),
        narrative=report.narrative,
    )
    lines = [
        f"work_unit_id\t{report.work_unit_id}",
        f"bucket\t{report.bucket_id}",
        f"source_kind\t{report.source_kind.value}",
        f"source_path\t{report.source_path}",
        f"verdict\t{report.verdict.value}",
        f"diffs\t{len(report.diffs)}",
    ]
    for diff in report.diffs:
        lines.append(
            f"diff\t{diff.field_name}\twork_unit={diff.work_unit_value}\tevidence={diff.evidence_value}",
        )
    _emit_envelope(ctx, command=command, result=result, lines=lines)


def _source_from_options(*, from_justificante: Path | None, from_declaration: Path | None):
    from ...application.modelo import ModeloReconciliationSourceKind

    if from_justificante is None and from_declaration is None:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.reconcile.errors.missing_source",
                default="Supply --from-justificante PATH, --from-declaration PATH, or --from-capture SNAPSHOT_ID.",
            ),
        )
    if from_justificante is not None and from_declaration is not None:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.reconcile.errors.exclusive_source",
                default="--from-justificante and --from-declaration are mutually exclusive.",
            ),
        )
    if from_justificante is not None:
        return ModeloReconciliationSourceKind.JUSTIFICANTE, from_justificante
    assert from_declaration is not None
    return ModeloReconciliationSourceKind.DECLARATION, from_declaration


def _active_bucket() -> str:
    if _active_bucket_id is None:
        raise RuntimeError("modelo reconcile commands were not registered")
    return _active_bucket_id()


def modelo_reconciliation_history_verb(
    ctx: typer.Context,
    work_unit_id: Annotated[
        str | None,
        typer.Option(
            "--work-unit-id",
            help=tr(
                "cli.app.modelo.reconciliation_history.work_unit_id_help",
                default="Optional work unit id to narrow the history to one work unit.",
            ),
        ),
    ] = None,
) -> None:
    """List past reconciliations recorded in the active profile."""
    from ...application.modelo import list_modelo_reconciliations
    from ._modelo_payloads_m036 import (
        ModeloReconciliationHistoryResult,
        ModeloReconciliationHistoryRowPayload,
    )

    _require_profile()
    bucket_id = _active_bucket()
    work_unit_token = work_unit_id.strip() if work_unit_id else None
    entries = list_modelo_reconciliations(bucket_id=bucket_id, work_unit_id=work_unit_token)
    result = ModeloReconciliationHistoryResult(
        bucket_id=bucket_id,
        work_unit_id=work_unit_token,
        reconciliation_count=len(entries),
        reconciliations=[
            ModeloReconciliationHistoryRowPayload(
                event_id=entry.event_id,
                bucket_id=entry.bucket_id,
                work_unit_id=entry.work_unit_id,
                source_kind=entry.source_kind.value,
                source_path=entry.source_path,
                verdict=entry.verdict.value,
                diff_count=entry.diff_count,
                actor=entry.actor,
                reconciled_at=entry.reconciled_at.isoformat(),
            )
            for entry in entries
        ],
    )
    lines = [
        "operation\tmodelo.reconciliation-history",
        f"bucket_id\t{bucket_id}",
        f"reconciliation_count\t{len(entries)}",
    ]
    if entries:
        lines.append("reconciled_at\twork_unit_id\tsource_kind\tverdict\tdiff_count\tactor")
        lines.extend(
            "\t".join(
                (
                    entry.reconciled_at.isoformat(),
                    entry.work_unit_id,
                    entry.source_kind.value,
                    entry.verdict.value,
                    str(entry.diff_count),
                    entry.actor,
                )
            )
            for entry in entries
        )
    else:
        lines.append(
            tr(
                "cli.app.modelo.reconciliation_history.empty",
                default="No reconciliations recorded yet.",
            )
        )
    _emit_envelope(ctx, command="modelo.reconciliation_history", result=result, lines=lines)


def modelo_reconcile_verb(
    ctx: typer.Context,
    work_unit_id: Annotated[
        str | None,
        typer.Argument(
            help=tr(
                "cli.app.modelo.reconcile.work_unit_id_help",
                default="Work unit id (SHA-256 or unambiguous prefix).",
            ),
        ),
    ] = None,
    modelo: Annotated[
        str | None,
        typer.Option("--modelo", help=tr("cli.app.modelo.work.modelo_help")),
    ] = None,
    year: Annotated[
        int | None,
        typer.Option("--year", help=tr("cli.app.modelo.work.year_help")),
    ] = None,
    period: Annotated[
        str | None,
        typer.Option("--period", help=tr("cli.app.modelo.work.period_help")),
    ] = None,
    revision: Annotated[
        str | None,
        typer.Option("--revision", help=tr("cli.app.modelo.work.revision_help")),
    ] = None,
    bucket_id: Annotated[
        str | None,
        typer.Option("--bucket-id", help=tr("cli.app.modelo.work.bucket_id_help")),
    ] = None,
    from_justificante: Annotated[
        Path | None,
        typer.Option(
            "--from-justificante",
            help=tr(
                "cli.app.modelo.reconcile.from_justificante_help",
                default="Path to the AEAT justificante PDF to reconcile against.",
            ),
        ),
    ] = None,
    from_declaration: Annotated[
        Path | None,
        typer.Option(
            "--from-declaration",
            help=tr(
                "cli.app.modelo.reconcile.from_declaration_help",
                default="Path to the filed declaration PDF to reconcile against.",
            ),
        ),
    ] = None,
    from_capture: Annotated[
        str | None,
        typer.Option(
            "--from-capture",
            help=tr(
                "cli.app.modelo.reconcile.from_capture_help",
                default=(
                    "Snapshot id (or prefix) of a persisted live justificante capture to reconcile "
                    "against. Local-only: reads the already-captured receipt, never contacts AEAT."
                ),
            ),
        ),
    ] = None,
    actor: Annotated[
        str | None,
        typer.Option("--by", help=tr("cli.app.modelo.work.actor_help")),
    ] = None,
) -> None:
    """Reconcile a modelo work unit against an external evidence source."""
    from ...application.modelo import ModeloReconciliationCommand, modelo_reconcile

    resolved_actor = actor.strip() if actor else _resolve_default_actor_value()
    _require_profile()
    unit = _resolve_work_unit(
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
    )
    if from_capture is not None:
        if from_justificante is not None or from_declaration is not None:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.reconcile.errors.exclusive_capture_source",
                    default="--from-capture is mutually exclusive with --from-justificante / --from-declaration.",
                ),
            )
        from ...application.live import JustificanteCaptureSnapshotService, reconcile_capture

        snapshot = JustificanteCaptureSnapshotService(bucket_id=unit.bucket_id).show(from_capture.strip())
        report = reconcile_capture(
            work_unit_id=unit.work_unit_id,
            snapshot=snapshot,
            actor=resolved_actor,
        )
        _render_reconciliation_report(ctx, report, command="modelo.reconcile")
        return

    source_kind, source_path = _source_from_options(
        from_justificante=from_justificante,
        from_declaration=from_declaration,
    )
    report = modelo_reconcile(
        ModeloReconciliationCommand(
            work_unit_id=unit.work_unit_id,
            source_kind=source_kind,
            source_path=source_path,
            actor=resolved_actor,
        ),
    )
    _render_reconciliation_report(ctx, report, command="modelo.reconcile")


def modelo_reconcile_from_justificante_verb(
    ctx: typer.Context,
    justificante_path: Annotated[
        Path,
        typer.Argument(
            help=tr(
                "cli.app.modelo.reconcile_from_justificante.justificante_path_help",
                default="Path to the AEAT justificante PDF to reconcile against.",
            ),
        ),
    ],
    work_unit_id: Annotated[
        str | None,
        typer.Argument(
            help=tr(
                "cli.app.modelo.reconcile_from_justificante.work_unit_id_help",
                default="Work unit id (SHA-256 or unambiguous prefix).",
            ),
        ),
    ] = None,
    modelo: Annotated[
        str | None,
        typer.Option("--modelo", help=tr("cli.app.modelo.work.modelo_help")),
    ] = None,
    year: Annotated[
        int | None,
        typer.Option("--year", help=tr("cli.app.modelo.work.year_help")),
    ] = None,
    period: Annotated[
        str | None,
        typer.Option("--period", help=tr("cli.app.modelo.work.period_help")),
    ] = None,
    revision: Annotated[
        str | None,
        typer.Option("--revision", help=tr("cli.app.modelo.work.revision_help")),
    ] = None,
    bucket_id: Annotated[
        str | None,
        typer.Option("--bucket-id", help=tr("cli.app.modelo.work.bucket_id_help")),
    ] = None,
) -> None:
    """Reconcile a work unit against the supplied justificante PDF."""
    from ...application.modelo import (
        ModeloReconciliationCommand,
        ModeloReconciliationSourceKind,
        modelo_reconcile,
    )

    _require_profile()
    unit = _resolve_work_unit(
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
    )
    report = modelo_reconcile(
        ModeloReconciliationCommand(
            work_unit_id=unit.work_unit_id,
            source_kind=ModeloReconciliationSourceKind.JUSTIFICANTE,
            source_path=justificante_path,
        ),
    )
    _render_reconciliation_report(ctx, report, command="modelo.reconcile_from_justificante")
