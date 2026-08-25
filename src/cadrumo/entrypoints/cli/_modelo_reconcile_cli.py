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
from pathlib import Path

import typer

from ...application.modelo import ModeloReconciliationEvidenceKind, ModeloReconciliationReport
from ...core.i18n import tr
from ...domain.modelos import WorkUnit
from ._common import active_bucket_id_or_refuse, emit_envelope
from ._modelo_behavior_support import require_active_profile, resolve_work_unit_for_cli
from ._modelo_cli_support import resolve_default_actor


def _require_profile() -> None:
    require_active_profile()


def _resolve_default_actor_value() -> str:
    return resolve_default_actor()


def _resolve_work_unit(
    *,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: str | None,
    revision: str | None,
    bucket_id: str | None,
) -> WorkUnit:
    return resolve_work_unit_for_cli(
        work_unit_id=work_unit_id, modelo=modelo, year=year, period=period, revision=revision, bucket_id=bucket_id
    )


def _active_bucket() -> str:
    return active_bucket_id_or_refuse()


def _render_reconciliation_report(ctx: typer.Context, report: ModeloReconciliationReport, *, command: str) -> None:
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
        lines.append(f"diff\t{diff.field_name}\twork_unit={diff.work_unit_value}\tevidence={diff.evidence_value}")
    for advisory in report.advisories:
        lines.append(f"advisory\t{advisory.code}\t{advisory.message}")
    emit_envelope(ctx, command=command, result=result, lines=lines, notices=notices)


def reconcile_pull_verb(
    ctx: typer.Context,
    work_unit_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    revision: str | None = None,
    bucket_id: str | None = None,
    actor: str | None = None,
) -> None:
    """Pull the AEAT justificante for a work unit and reconcile against it."""
    from ...application.live import capture_justificante_snapshot, reconcile_capture

    resolved_actor = actor.strip() if actor else _resolve_default_actor_value()
    _require_profile()
    unit = _resolve_work_unit(
        work_unit_id=work_unit_id, modelo=modelo, year=year, period=period, revision=revision, bucket_id=bucket_id
    )
    snapshot = asyncio.run(
        capture_justificante_snapshot(
            bucket_id=unit.bucket_id, modelo=str(unit.modelo), year=unit.filing_year, period=unit.period
        )
    )
    report = reconcile_capture(work_unit_id=unit.work_unit_id, snapshot=snapshot, actor=resolved_actor)
    _render_reconciliation_report(ctx, report, command="modelo.reconcile.pull")


def reconcile_file_verb(
    ctx: typer.Context,
    file: Path,
    work_unit_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    revision: str | None = None,
    bucket_id: str | None = None,
    actor: str | None = None,
    kind: ModeloReconciliationEvidenceKind | None = None,
) -> None:
    """Reconcile a work unit against a local justificante or declaración PDF file."""
    from ...application.modelo import ModeloReconciliationCommand, modelo_reconcile

    resolved_actor = actor.strip() if actor else _resolve_default_actor_value()
    resolved_kind = kind if kind is not None else ModeloReconciliationEvidenceKind.JUSTIFICANTE
    _require_profile()
    unit = _resolve_work_unit(
        work_unit_id=work_unit_id, modelo=modelo, year=year, period=period, revision=revision, bucket_id=bucket_id
    )
    report = modelo_reconcile(
        ModeloReconciliationCommand(
            work_unit_id=unit.work_unit_id, source_kind=resolved_kind, source_path=file, actor=resolved_actor
        )
    )
    _render_reconciliation_report(ctx, report, command="modelo.reconcile.file")


def reconcile_history_verb(ctx: typer.Context, work_unit_id: str | None = None) -> None:
    """List past reconciliations recorded in the active profile."""
    from ...application.modelo import list_modelo_reconciliations
    from ._modelo_payloads_m036 import ModeloReconciliationHistoryResult, ModeloReconciliationHistoryRowPayload

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
    lines = ["operation\tmodelo.reconcile.history", f"bucket_id\t{bucket_id}", f"reconciliation_count\t{len(entries)}"]
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
        lines.append(tr("cli.app.modelo.reconcile.history_empty", default="No reconciliations recorded yet."))
    emit_envelope(ctx, command="modelo.reconcile.history", result=result, lines=lines)
