"""Typed payload schemas for modelo reconciliation and taxation comparison.

Every declared payload is an :class:`OutputSchema` subclass registered for
the modelo reconciliation and taxation-comparison JSON-contract surface.
"""

from __future__ import annotations

from ...core.identity import BucketId
from ...domain.modelos import WorkUnitId
from ._schemas import OutputSchema, register_schema


class ModeloReconciliationDiffPayload(OutputSchema):
    """One per-casilla disagreement surfaced in a reconciliation report."""

    field_name: str
    work_unit_value: str = ""
    evidence_value: str = ""
    kind: str


@register_schema("modelo.reconcile.pull")
@register_schema("modelo.reconcile.file")
class ModeloReconcileResult(OutputSchema):
    """Result payload for ``modelo reconcile file`` and ``modelo reconcile pull``.

    Both verbs share the :class:`ModeloReconciliationReport` shape from
    the application service: a work-unit-level verdict, the bucket
    scope, the external-evidence source kind and path, the per-casilla
    diff list, the reconciliation timestamp, and an optional narrative.
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

    Surfaces cuota resultante autoliquidacion (0595) and cuota
    diferencial / resultado (0610) for both conjunta and individual
    filing modes, plus the delta and recommendation.
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
