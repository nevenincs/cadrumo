"""Typed payload schemas for modelo reconciliation and taxation comparison.

Every declared payload is a
:class:`~aeat.entrypoints.cli._schemas.OutputSchema` subclass registered with
:func:`~aeat.entrypoints.cli._schemas.register_schema` for the modelo
reconciliation and taxation-comparison JSON-contract surface. The application
facade remains authoritative for
:class:`~aeat.application.modelo.ModeloReconciliationReport` and
:class:`~aeat.application.modelo.TaxationComparisonResult`; this module only
documents the CLI transport shape that enters
:class:`~aeat.entrypoints.cli._schemas.SchemaEnvelope` through
:func:`~aeat.entrypoints.cli._common._emit_envelope`. The parent
:mod:`aeat.entrypoints.cli._modelo_payloads` module re-exports these split
schemas so modelo emitters keep one payload import surface.
"""

from __future__ import annotations

from ...core.identity import BucketId
from ...domain.modelos import WorkUnitId
from ._schemas import OutputSchema, register_schema


class ModeloReconciliationDiffPayload(OutputSchema):
    """One disagreement surfaced in a reconciliation report.

    Nested in :class:`ModeloReconcileResult` and mirrors
    :class:`~aeat.application.modelo.ModeloReconciliationDiff`. Justificante
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


class ModeloReconciliationAdvisoryPayload(OutputSchema):
    """One non-blocking reconciliation advisory carried alongside the diffs.

    Mirrors :class:`~aeat.application.modelo.ModeloReconciliationAdvisory`. The
    CLI also folds each advisory into a typed
    :class:`~aeat.core.json_contract.Notice` on the envelope ``notices`` channel;
    this payload preserves the structured ``code`` / ``context`` in the result
    for machine consumers per ``cli-notices-are-the-only-diagnostic-channel``.
    """

    code: str
    message: str
    context: dict[str, str] = {}


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
    path/reference, :class:`ModeloReconciliationDiffPayload` list,
    reconciliation timestamp, and optional narrative.
    """

    work_unit_id: WorkUnitId
    bucket_id: BucketId
    source_kind: str
    source_path: str
    verdict: str
    diffs: tuple[ModeloReconciliationDiffPayload, ...] = ()
    advisories: tuple[ModeloReconciliationAdvisoryPayload, ...] = ()
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
