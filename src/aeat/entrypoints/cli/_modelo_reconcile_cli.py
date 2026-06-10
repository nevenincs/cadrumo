"""Reconciliation command registration for ``aeat app modelo``."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer

from ...application.modelo import ModeloReconciliationReport, WorkUnit
from ...core.i18n import tr

_require_active_profile: Callable[[], None] | None = None
_resolve_work_unit_for_cli: Callable[..., WorkUnit] | None = None
_resolve_default_actor: Callable[[], str] | None = None


def register_reconcile_commands(
    app: typer.Typer,
    *,
    require_active_profile: Callable[[], None],
    resolve_work_unit_for_cli: Callable[..., WorkUnit],
    resolve_default_actor: Callable[[], str],
) -> None:
    """Register local-only modelo reconciliation commands."""
    global _require_active_profile, _resolve_work_unit_for_cli, _resolve_default_actor
    _require_active_profile = require_active_profile
    _resolve_work_unit_for_cli = resolve_work_unit_for_cli
    _resolve_default_actor = resolve_default_actor
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
                default="Supply --from-justificante PATH or --from-declaration PATH.",
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
    actor: Annotated[
        str | None,
        typer.Option("--by", help=tr("cli.app.modelo.work.actor_help")),
    ] = None,
) -> None:
    """Reconcile a modelo work unit against an external evidence source."""
    from ...application.modelo import ModeloReconciliationCommand, modelo_reconcile

    source_kind, source_path = _source_from_options(
        from_justificante=from_justificante,
        from_declaration=from_declaration,
    )
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
