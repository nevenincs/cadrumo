"""Typed payload schemas for modelo reconciliation and taxation comparison.

Every declared payload is a
:class:`OutputSchema` subclass registered with
:func:`register_schema` for the modelo
reconciliation and taxation-comparison JSON-contract surface. The application
facade remains authoritative for
:class:`ModeloReconciliationReport` and
:class:`TaxationComparisonResult`; this module only
documents the CLI transport shape that enters
:class:`SchemaEnvelope` through
:func:`_emit_envelope`. The parent :mod:`_modelo_payloads` module re-exports
these split schemas so modelo emitters keep one payload import surface.
"""

from __future__ import annotations

from ...core.identity import BucketId
from ...domain.modelos import WorkUnitId
from ._schemas import OutputSchema, register_schema


class ModeloReconciliationDiffPayload(OutputSchema):
    """One disagreement surfaced in a reconciliation report.

    Nested in :class:`ModeloReconcileResult` and mirrors
    :class:`ModeloReconciliationDiff`. Justificante
    reconciliation compares header evidence (modelo, period, ejercicio, tax id)
    and, where the revision declares ``reconciliation_total_casilla_ids``, the
    filed total against the canonical computed result casilla. ``diff_kind`` is
    the closed category (``header_field`` / ``total``); a ``total`` diff carries
    the reconciling expectation's ``legal_refs`` / ``source_refs``. Individual
    casilla declaration diffs require the modelo-specific declaration parser
    (``diff_kind = casilla`` is reserved).
    """

    field_name: str
    work_unit_value: str = ""
    evidence_value: str = ""
    kind: str
    diff_kind: str = "header_field"
    legal_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()


@register_schema("modelo.reconcile.pull")
@register_schema("modelo.reconcile.file")
class ModeloReconcileResult(OutputSchema):
    """Result payload for ``modelo reconcile file`` and ``modelo reconcile pull``.

    Both verbs share
    :class:`ModeloReconciliationReport` from
    :func:`modelo_reconcile` or :func:`modelo_reconcile_bytes`: a work-unit-level
    :obj:`WorkUnitId`, :obj:`BucketId` scope, :class:`ModeloReconciliationVerdict`,
    :class:`ModeloReconciliationEvidenceKind`, evidence path/reference,
    :class:`ModeloReconciliationDiffPayload` list, reconciliation timestamp,
    and optional narrative. Non-blocking reconciliation advisories ride the
    shared envelope ``notices`` channel exclusively
    (``cli-notices-are-the-only-diagnostic-channel``); this result carries no
    bespoke advisory field.
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
    """Result payload for ``cadrumo app modelo work compare-taxation``.

    Projects :class:`TaxationComparisonResult` returned
    by :func:`compare_taxation_for_work_address`. It surfaces the
    semantic-role-selected cuota resultante de la autoliquidación and cuota
    diferencial / resultado for both conjunta and individual filing modes, plus
    the signed delta and
    :class:`TaxationRecommendation`.
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
