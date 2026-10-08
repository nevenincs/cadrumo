"""Reconciliation command group for ``aeat app modelo reconcile``.

``reconcile`` is a command group expressing the two CLI standards:

* ``reconcile pull <work-unit>`` fetches the justificante from AEAT (the
  ``pull`` standard) and reconciles against it in one flow.
* ``reconcile import <work-unit> --file PATH [--kind justificante|declaration]``
  reconciles against a local PDF (the ``--file`` standard); local-only, never
  contacts AEAT. ``--kind`` selects the evidence document's KIND, orthogonal to
  the pull/file transport axis: ``justificante`` (the default, every modelo) or
  ``declaration`` (a filed declaración PDF, casilla-level reconcile, enrolled
  modelos only -- see :data:`application.modelo.reconciliation._DECLARATION_CASILLA_RECONCILE_MODELOS`).
* ``reconcile list`` lists past reconciliations.
"""

from __future__ import annotations

from pathlib import Path

import typer

from ...application.modelo.reconciliation import ModeloReconciliationReport
from ...application.modelo.reconciliation_records import ModeloReconciliationEvidenceKind
from ...core.i18n.render import tr
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ._modelo_cli_support import resolve_default_actor
from .common import emit_envelope


def _resolve_default_actor_value() -> str:
    return resolve_default_actor()


def _render_reconciliation_report(ctx: typer.Context, report: ModeloReconciliationReport, *, command: str) -> None:
    """Render a :class:`~application.modelo.reconciliation.ModeloReconciliationReport` through the typed envelope.

    ``command`` is the registered leaf id (``modelo.reconcile.pull`` /
    ``modelo.reconcile.file``); reconciliation advisories ride the typed
    ``Notice`` channel (``aeat-cli-contract``) and are
    folded into the same text lines so JSON and text cannot drift.
    """
    from ...core.json_contract import Notice, NoticeSeverity
    from ._payloads_modelo_reconcile import ModeloReconcileResult, ModeloReconciliationDiffPayload

    result = ModeloReconcileResult(
        work_unit_id=report.work_unit_id,
        calculation_revision_id=report.calculation_revision_id,
        registry_snapshot_ref=report.registry_snapshot_ref,
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
        f"calculation_revision_id\t{report.calculation_revision_id or 'unknown'}",
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
    calculation_revision: str | None = None,
    source: ModeloReconciliationEvidenceKind = ModeloReconciliationEvidenceKind.JUSTIFICANTE,
) -> None:
    """Pull the AEAT justificante for a work unit and reconcile against it."""
    from .runtime_modelo_reconciliation_pull import pull_modelo_reconciliation

    resolved_actor = actor.strip() if actor else _resolve_default_actor_value()
    report = pull_modelo_reconciliation(
        ctx,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
        actor=resolved_actor,
        calculation_revision=calculation_revision,
        source=source,
    )
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
    calculation_revision: str | None = None,
    kind: ModeloReconciliationEvidenceKind | None = None,
) -> None:
    """Reconcile a work unit against a local justificante or declaración PDF file."""
    from .runtime_modelo_reconciliation_import import import_modelo_reconciliation

    resolved_actor = actor.strip() if actor else "operator"
    resolved_kind = kind if kind is not None else ModeloReconciliationEvidenceKind.JUSTIFICANTE
    report = import_modelo_reconciliation(
        ctx,
        file=file,
        source_kind=resolved_kind,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
        actor=resolved_actor,
        calculation_revision=calculation_revision,
    )
    _render_reconciliation_report(ctx, report, command="modelo.reconcile.import")


def reconcile_list_verb(ctx: typer.Context, work_unit_id: str | None = None) -> None:
    """List past reconciliations recorded in the active profile."""
    from ...application.modelo.reconciliation_records import ModeloReconciliationAdvisory
    from ._modelo_payloads_m036 import ModeloReconciliationHistoryResult, ModeloReconciliationHistoryRowPayload
    from .runtime_modelo_reconciliation_list import read_modelo_reconciliation_list

    work_unit_token = work_unit_id.strip() if work_unit_id else None
    projection = read_modelo_reconciliation_list(ctx, work_unit_id=work_unit_token)
    bucket_id = str(projection.profile_id)
    entries = projection.reconciliations
    result = ModeloReconciliationHistoryResult(
        bucket_id=bucket_id,
        work_unit_id=work_unit_token,
        reconciliation_count=projection.reconciliation_count,
        reconciliations=[
            ModeloReconciliationHistoryRowPayload(
                event_id=entry.event_id,
                calculation_revision_id=entry.calculation_revision_id,
                registry_snapshot_ref=(
                    RegistrySnapshotRef(**entry.registry_snapshot_ref.model_dump())
                    if entry.registry_snapshot_ref
                    else None
                ),
                bucket_id=entry.bucket_id,
                work_unit_id=entry.work_unit_id,
                source_kind=entry.source_kind,
                source_path=entry.source_path,
                verdict=entry.verdict,
                diff_count=entry.diff_count,
                advisory_count=entry.advisory_count,
                diffs=entry.diffs,
                advisories=tuple(
                    ModeloReconciliationAdvisory(code=item.code, message=item.message, context=dict(item.context))
                    for item in entry.advisories
                ),
                actor=entry.actor,
                reconciled_at=entry.reconciled_at,
            )
            for entry in entries
        ],
    )
    lines = [
        "operation\tmodelo.reconcile.list",
        f"bucket_id\t{bucket_id}",
        f"reconciliation_count\t{projection.reconciliation_count}",
    ]
    if entries:
        lines.append(
            "reconciled_at\twork_unit_id\tsource_kind\tverdict\tdiff_count\tadvisory_count\tactor\tcalculation_revision_id"
        )
        lines.extend(
            "\t".join(
                (
                    entry.reconciled_at.isoformat(),
                    entry.work_unit_id,
                    entry.source_kind.value,
                    entry.verdict.value,
                    str(entry.diff_count),
                    str(entry.advisory_count),
                    entry.actor,
                    entry.calculation_revision_id or "unknown",
                )
            )
            for entry in entries
        )
    else:
        lines.append(
            tr(
                "cli.app.modelo.reconcile.list_empty",
            )
        )
    for entry in entries:
        lines.extend(
            f"diff\t{entry.event_id}\t{diff.field_name}\twork_unit={diff.work_unit_value}\tevidence={diff.evidence_value}"
            for diff in entry.diffs
        )
        lines.extend(
            f"advisory\t{entry.event_id}\t{advisory.code}\t{advisory.message}" for advisory in entry.advisories
        )
    emit_envelope(ctx, command="modelo.reconcile.list", result=result, lines=lines)
