"""Reconciliation command group for ``aeat app modelo reconcile``.

``reconcile`` is a command group expressing the two CLI standards:

* ``reconcile pull <work-unit>`` fetches the justificante from AEAT (the
  ``pull`` standard) and reconciles against it in one flow.
* ``reconcile file <work-unit> --file PATH [--kind justificante|declaration]``
  reconciles against a local PDF (the ``--file`` standard); local-only, never
  contacts AEAT. ``--kind`` selects the evidence document's KIND, orthogonal to
  the pull/file transport axis: ``justificante`` (the default, every modelo) or
  ``declaration`` (a filed declaración PDF, casilla-level reconcile, enrolled
  modelos only -- see :data:`application.modelo._reconcile._DECLARATION_CASILLA_RECONCILE_MODELOS`).
* ``reconcile history`` lists past reconciliations.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer

from ...application.modelo import ModeloReconciliationEvidenceKind, ModeloReconciliationReport
from ...core.i18n import tr
from ...domain.modelos import WorkUnit
from ._command_policy import command_execution_policy
from ._common import _emit_envelope
from ._modelo_execution_policies import BROWSER_MODEL_WRITE, MODEL_HANDOFF, MODEL_READ, declare_metadata_group
from ._modelo_work_options import _ActorOpt, _BucketIdOpt, _ModeloOpt, _PeriodOpt, _RevisionOpt, _YearOpt

_require_active_profile: Callable[[], None] | None = None
_resolve_work_unit_for_cli: Callable[..., WorkUnit] | None = None
_resolve_default_actor: Callable[[], str] | None = None
_active_bucket_id: Callable[[], str] | None = None


reconcile_app = typer.Typer(
    name="reconcile",
    help=tr(
        "cli.app.modelo.reconcile.app_help",
        default=(
            "Reconcile a modelo work unit against its AEAT justificante: `pull` fetches the receipt "
            "from AEAT and reconciles; `file` reconciles a local PDF; `history` lists past runs."
        ),
    ),
    no_args_is_help=True,
    add_completion=False,
)
declare_metadata_group(reconcile_app)


def register_reconcile_commands(
    app: typer.Typer,
    *,
    require_active_profile: Callable[[], None],
    resolve_work_unit_for_cli: Callable[..., WorkUnit],
    resolve_default_actor: Callable[[], str],
    active_bucket_id: Callable[[], str],
) -> None:
    """Mount the modelo reconcile command group on the modelo app."""
    global _require_active_profile, _resolve_work_unit_for_cli, _resolve_default_actor, _active_bucket_id
    _require_active_profile = require_active_profile
    _resolve_work_unit_for_cli = resolve_work_unit_for_cli
    _resolve_default_actor = resolve_default_actor
    _active_bucket_id = active_bucket_id
    app.add_typer(reconcile_app, name="reconcile")


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


def _active_bucket() -> str:
    if _active_bucket_id is None:
        raise RuntimeError("modelo reconcile commands were not registered")
    return _active_bucket_id()


def _render_reconciliation_report(
    ctx: typer.Context,
    report: ModeloReconciliationReport,
    *,
    command: str,
) -> None:
    """Render a :class:`~application.modelo.ModeloReconciliationReport` through the typed envelope.

    ``command`` is the registered leaf id (``modelo.reconcile.pull`` /
    ``modelo.reconcile.file``); reconciliation advisories ride the typed
    ``Notice`` channel (``aeat-cli-contract``) and are
    folded into the same text lines so JSON and text cannot drift.
    """
    from ...core.json_contract import Notice, NoticeSeverity
    from ._payloads_modelo_reconcile import ModeloReconcileResult, ModeloReconciliationDiffPayload

    result = ModeloReconcileResult(
        work_unit_id=report.work_unit_id,
        bucket_id=report.bucket_id,
        source_kind=report.source_kind,
        source_path=report.source_path,
        verdict=report.verdict,
        diffs=tuple(
            ModeloReconciliationDiffPayload(
                field_name=diff.field_name,
                work_unit_value=diff.work_unit_value,
                evidence_value=diff.evidence_value,
                kind=diff.kind,
                diff_kind=diff.diff_kind,
                legal_refs=diff.legal_refs,
                source_refs=diff.source_refs,
            )
            for diff in report.diffs
        ),
        reconciled_at=report.reconciled_at,
        narrative=report.narrative,
    )
    notices = [
        Notice(
            severity=NoticeSeverity.WARNING,
            code=advisory.code,
            message=advisory.message,
            context=dict(advisory.context) or None,
        )
        for advisory in report.advisories
    ]
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
    for advisory in report.advisories:
        lines.append(f"advisory\t{advisory.code}\t{advisory.message}")
    _emit_envelope(ctx, command=command, result=result, lines=lines, notices=notices)


_WorkUnitIdArg = Annotated[
    str | None,
    typer.Argument(
        help=tr(
            "cli.app.modelo.reconcile.work_unit_id_help",
            default="Work unit id (SHA-256 or unambiguous prefix).",
        ),
    ),
]
_KindOpt = Annotated[
    ModeloReconciliationEvidenceKind | None,
    typer.Option(
        "--kind",
        help=tr(
            "cli.app.modelo.reconcile.file_kind_help",
            default=(
                "Evidence document kind: `justificante` (AEAT receipt, every modelo) or "
                "`declaration` (filed declaración PDF, casilla-level reconcile, enrolled modelos only). "
                "Defaults to `justificante`."
            ),
        ),
    ),
]


@reconcile_app.command(
    "pull",
    help=tr(
        "cli.app.modelo.reconcile.pull_help",
        default="Pull the justificante for a work unit from AEAT and reconcile against it. Contacts AEAT (read-only).",
    ),
)
@command_execution_policy(BROWSER_MODEL_WRITE)
def reconcile_pull_verb(
    ctx: typer.Context,
    work_unit_id: _WorkUnitIdArg = None,
    modelo: _ModeloOpt = None,
    year: _YearOpt = None,
    period: _PeriodOpt = None,
    revision: _RevisionOpt = None,
    bucket_id: _BucketIdOpt = None,
    actor: _ActorOpt = None,
) -> None:
    """Pull the AEAT justificante for a work unit and reconcile against it."""
    from ...application.live import capture_justificante_snapshot, reconcile_capture

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
    snapshot = asyncio.run(
        capture_justificante_snapshot(
            bucket_id=unit.bucket_id,
            modelo=str(unit.modelo),
            year=unit.filing_year,
            period=unit.period,
        ),
    )
    report = reconcile_capture(work_unit_id=unit.work_unit_id, snapshot=snapshot, actor=resolved_actor)
    _render_reconciliation_report(ctx, report, command="modelo.reconcile.pull")


@reconcile_app.command(
    "file",
    help=tr(
        "cli.app.modelo.reconcile.file_help",
        default=(
            "Reconcile a work unit against a local justificante or declaración PDF. Local-only; never contacts AEAT."
        ),
    ),
)
@command_execution_policy(MODEL_HANDOFF)
def reconcile_file_verb(
    ctx: typer.Context,
    file: Annotated[
        Path,
        typer.Option(
            "--file",
            help=tr(
                "cli.app.modelo.reconcile.file_path_help",
                default="Path to the local justificante or declaración PDF to reconcile against.",
            ),
        ),
    ],
    work_unit_id: _WorkUnitIdArg = None,
    modelo: _ModeloOpt = None,
    year: _YearOpt = None,
    period: _PeriodOpt = None,
    revision: _RevisionOpt = None,
    bucket_id: _BucketIdOpt = None,
    actor: _ActorOpt = None,
    kind: _KindOpt = None,
) -> None:
    """Reconcile a work unit against a local justificante or declaración PDF file."""
    from ...application.modelo import ModeloReconciliationCommand, modelo_reconcile

    resolved_actor = actor.strip() if actor else _resolve_default_actor_value()
    resolved_kind = kind if kind is not None else ModeloReconciliationEvidenceKind.JUSTIFICANTE
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
            source_kind=resolved_kind,
            source_path=file,
            actor=resolved_actor,
        ),
    )
    _render_reconciliation_report(ctx, report, command="modelo.reconcile.file")


@reconcile_app.command(
    "history",
    help=tr(
        "cli.app.modelo.reconcile.history_help",
        default=(
            "List past reconciliations recorded for the active profile. Reads the encrypted "
            "reconciliation records written by each reconcile run."
        ),
    ),
)
@command_execution_policy(MODEL_READ)
def reconcile_history_verb(
    ctx: typer.Context,
    work_unit_id: Annotated[
        str | None,
        typer.Option(
            "--work-unit-id",
            help=tr(
                "cli.app.modelo.reconcile.history_work_unit_id_help",
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
                source_kind=entry.source_kind,
                source_path=entry.source_path,
                verdict=entry.verdict,
                diff_count=entry.diff_count,
                actor=entry.actor,
                reconciled_at=entry.reconciled_at,
            )
            for entry in entries
        ],
    )
    lines = [
        "operation\tmodelo.reconcile.history",
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
                ),
            )
            for entry in entries
        )
    else:
        lines.append(
            tr(
                "cli.app.modelo.reconcile.history_empty",
                default="No reconciliations recorded yet.",
            ),
        )
    _emit_envelope(ctx, command="modelo.reconcile.history", result=result, lines=lines)
