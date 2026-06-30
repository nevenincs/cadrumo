"""Typed payload schemas for modelo reconciliation and taxation comparison.

Every declared payload is a
:class:`~aeat.entrypoints.cli._schemas.OutputSchema` subclass registered with
:func:`~aeat.entrypoints.cli._schemas.register_schema` for the modelo
reconciliation and taxation-comparison JSON-contract surface. The application
facade remains authoritative for
:class:`~aeat.application.modelo.ModeloReconciliationReport` and
:class:`~aeat.application.modelo.TaxationComparisonResult`; this module only
documents the CLI transport shape that enters
:class:`~aeat.entrypoints.cli._schemas.SchemaEnvelope`.
"""

from __future__ import annotations

from ...core.identity import BucketId
from ...domain.modelos import WorkUnitId
from ._schemas import OutputSchema, register_schema


class ModeloReconciliationDiffPayload(OutputSchema):
    """One metadata disagreement surfaced in a reconciliation report.

    Mirrors :class:`~aeat.application.modelo.ModeloReconciliationDiff`. Current
    justificante reconciliation compares header evidence (modelo, period,
    ejercicio, tax id, and totals), not individual casilla values; casilla-level
    declaration diffs require a modelo-specific declaration parser.
    """

    field_name: str
    work_unit_value: str = ""
    evidence_value: str = ""
    kind: str


@register_schema("modelo.reconcile.pull")
@register_schema("modelo.reconcile.file")
class ModeloReconcileResult(OutputSchema):
    """Result payload for ``modelo reconcile file`` and ``modelo reconcile pull``.

    Both verbs share
    :class:`~aeat.application.modelo.ModeloReconciliationReport` from
    :func:`~aeat.application.modelo.modelo_reconcile` or
    :func:`~aeat.application.modelo.modelo_reconcile_bytes`: a work-unit-level
    :class:`~aeat.application.modelo.ModeloReconciliationVerdict`, bucket scope,
    :class:`~aeat.application.modelo.ModeloReconciliationEvidenceKind`, evidence
    path/reference, metadata diff list, reconciliation timestamp, and optional
    narrative.
    """

    work_unit_id: WorkUnitId
    bucket_id: BucketId
    source_kind: str
    source_path: str
    verdict: str
    diffs: tuple[ModeloReconciliationDiffPayload, ...] = ()
    reconciled_at: str
    narrative: str = ""


@register_schema("modelo.work.compare_taxation")
class WorkCompareTaxationResult(OutputSchema):
    """Result payload for ``aeat app modelo work compare-taxation``.

    Projects :class:`~aeat.application.modelo.TaxationComparisonResult` returned
    by :func:`~aeat.application.modelo.compare_taxation_for_work_address`.
    It surfaces the semantic-role-selected cuota resultante de la
    autoliquidación and cuota diferencial / resultado for both conjunta and
    individual filing modes, plus the signed delta and
    :class:`~aeat.application.modelo.TaxationRecommendation`.
    """

    operation: str = "modelo.work.compare_taxation"
    filing_year: int
    modelo: str
    revision: str
    conjunta_cuota_resultante: str
    individual_cuota_resultante: str
    conjunta_resultado: str
    individual_resultado: str
    delta_resultado: str
    recommendation: str
    recommendation_reason: str
